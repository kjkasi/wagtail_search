from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from wagtail.documents import get_document_model
from wagtail.models import Page, PageViewRestriction, Site

from home.models import ArticlePage, HomePage

Document = get_document_model()


class SearchViewTests(TestCase):
    client: Client

    def setUp(self):
        root = Page.get_first_root_node()
        assert root is not None
        self.home = root.add_child(
            instance=HomePage(
                title="Demo Home",
                slug="demo-home",
                intro="<p>Welcome to the demo.</p>",
            )
        )
        self.site, _ = Site.objects.update_or_create(
            hostname="localhost",
            port=80,
            defaults={
                "site_name": "Demo",
                "root_page": self.home,
                "is_default_site": True,
            },
        )
        self.home.save_revision().publish()

        self.visible = self._add_article(
            "Visible page", "visible", "<p>Visible text.</p>"
        )
        self.attached_document = Document.objects.create(
            title="Visible guide",
            file=ContentFile(b"guide", name="visible-guide.pdf"),
        )
        self.unattached_document = Document.objects.create(
            title="Orphan guide",
            file=ContentFile(b"orphan", name="orphan-guide.pdf"),
        )
        self.visible.body = (
            f'<p>Visible text.</p><p><a linktype="document" '
            f'id="{self.attached_document.pk}">Visible guide</a></p>'
        )
        self.visible.save_revision().publish()
        self._add_article(
            "Hidden page",
            "hidden",
            "<p>Hidden text.</p>",
            show_in_menus=False,
        )
        self.home.add_child(
            instance=ArticlePage(
                title="Draft page",
                slug="draft",
                body="<p>Draft text.</p>",
                show_in_menus=True,
                live=False,
            )
        )
        self._add_article(
            "Body page",
            "body-page",
            "<p>body-only-term</p>",
        )
        call_command("update_index", verbosity=0)

    def _add_article(self, title, slug, body, **extra):
        article_data = {
            "title": title,
            "slug": slug,
            "body": body,
            "show_in_menus": True,
        }
        article_data.update(extra)
        article = self.home.add_child(instance=ArticlePage(**article_data))
        article.save_revision().publish()
        return article

    def test_search_returns_case_insensitive_live_page_title_and_url(self):
        response = self.client.get("/search/?q=VISIBLE")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            {"type": "page", "title": "Visible page", "url": self.visible.url},
            response.json()["results"],
        )

    def test_search_returns_attached_document_by_title(self):
        results = self.client.get("/search/?q=GUIDE").json()["results"]

        self.assertEqual(
            results,
            [
                {
                    "type": "document",
                    "title": "Visible guide",
                    "url": self.attached_document.url,
                }
            ],
        )

    def test_search_does_not_return_unattached_document(self):
        results = self.client.get("/search/?q=Orphan").json()["results"]

        self.assertEqual(results, [])

    def test_search_includes_page_and_document_results(self):
        results = self.client.get("/search/?q=Visible").json()["results"]

        self.assertEqual(
            {(item["type"], item["title"]) for item in results},
            {("page", "Visible page"), ("document", "Visible guide")},
        )

    def test_search_includes_hidden_live_page_but_excludes_draft(self):
        results = self.client.get("/search/?q=page").json()["results"]
        titles = [item["title"] for item in results]

        self.assertIn("Hidden page", titles)
        self.assertNotIn("Draft page", titles)

    def test_search_excludes_pages_under_view_restrictions(self):
        restricted = self._add_article(
            "Restricted page",
            "restricted",
            "<p>Restricted text.</p>",
        )
        PageViewRestriction.objects.create(
            page=restricted,
            restriction_type=PageViewRestriction.LOGIN,
        )
        call_command("update_index", verbosity=0)

        results = self.client.get("/search/?q=Restricted").json()["results"]

        self.assertNotIn(
            {"type": "page", "title": "Restricted page", "url": restricted.url},
            results,
        )

    def test_search_uses_document_titles_not_tags(self):
        self.attached_document.tags.add("secret")
        call_command("update_index", verbosity=0)

        results = self.client.get("/search/?q=secret").json()["results"]

        self.assertEqual(results, [])

    def test_search_works_with_search_results_without_get_queryset(self):
        with patch.object(
            type(Document.objects.all()),
            "search",
            return_value=[self.attached_document],
        ):
            results = self.client.get("/search/?q=Visible").json()["results"]

        self.assertIn(
            {
                "type": "document",
                "title": "Visible guide",
                "url": self.attached_document.url,
            },
            results,
        )

    def test_search_matches_outer_document_link_with_nested_anchor(self):
        outer_document = Document.objects.create(
            title="Outer file",
            file=ContentFile(b"outer", name="outer.pdf"),
        )
        inner_document = Document.objects.create(
            title="Inner file",
            file=ContentFile(b"inner", name="inner.pdf"),
        )
        self.visible.body = (
            f'<p><a linktype="document" id="{outer_document.pk}">Outer label '
            f'<a linktype="document" id="{inner_document.pk}">Inner label</a>'
            "</a></p>"
        )
        self.visible.save_revision().publish()

        results = self.client.get("/search/?q=Outer%20label").json()["results"]

        self.assertEqual(
            results,
            [
                {
                    "type": "document",
                    "title": "Outer file",
                    "url": outer_document.url,
                }
            ],
        )

    def test_search_includes_current_site_root_page(self):
        results = self.client.get("/search/?q=Demo%20Home").json()["results"]

        self.assertIn(
            {"type": "page", "title": "Demo Home", "url": self.home.url},
            results,
        )

    def test_search_returns_document_by_rich_text_link_name(self):
        document = Document.objects.create(
            title="Internal manual",
            file=ContentFile(b"manual", name="internal-manual.pdf"),
        )
        self.home.intro = (
            f'<p><a linktype="document" id="{document.pk}">'
            "Employee handbook"
            "</a></p>"
        )
        self.home.save_revision().publish()

        results = self.client.get("/search/?q=handbook").json()["results"]

        self.assertEqual(
            results,
            [
                {
                    "type": "document",
                    "title": "Internal manual",
                    "url": document.url,
                }
            ],
        )

    def test_search_finds_attached_document_after_unattached_title_matches(self):
        attached_document = Document.objects.create(
            title="Needle",
            file=ContentFile(b"attached", name="needle-attached.pdf"),
        )
        for index in range(2):
            Document.objects.create(
                title="Needle",
                file=ContentFile(
                    f"orphan-{index}".encode(), name=f"needle-orphan-{index}.pdf"
                ),
            )
        self.visible.body = (
            f'<p><a linktype="document" id="{attached_document.pk}">'
            "Download manual"
            "</a></p>"
        )
        self.visible.save_revision().publish()
        for index in range(9):
            self._add_article(
                f"Needle page {index}",
                f"needle-page-{index}",
                "<p>Page.</p>",
            )
        call_command("update_index", verbosity=0)

        results = self.client.get("/search/?q=Needle").json()["results"]

        self.assertIn(
            {
                "type": "document",
                "title": "Needle",
                "url": attached_document.url,
            },
            results,
        )

    def test_search_batches_specific_page_loading(self):
        for index in range(12):
            self._add_article(
                f"Extra page {index}",
                f"extra-page-{index}",
                f"<p>Extra page {index}.</p>",
            )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/search/?q=unknown")

        self.assertEqual(response.status_code, 200)
        self.assertLess(len(queries), 15)

    def test_search_fetches_link_matches_in_batches(self):
        links = []
        for index in range(3):
            document = Document.objects.create(
                title=f"Batch document {index}",
                file=ContentFile(
                    f"batch-{index}".encode(), name=f"batch-{index}.pdf"
                ),
            )
            links.append(
                f'<a linktype="document" id="{document.pk}">Batch download</a>'
            )
        self.visible.body = "<p>" + " ".join(links) + "</p>"
        self.visible.save_revision().publish()

        with (
            patch("home.views.DOCUMENT_BATCH_SIZE", 2),
            patch.object(
                Document.objects,
                "filter",
                wraps=Document.objects.filter,
            ) as document_filter,
        ):
            results = self.client.get("/search/?q=Batch%20download").json()[
                "results"
            ]

        filter_sizes = [
            len(call.kwargs["pk__in"])
            for call in document_filter.call_args_list
            if "pk__in" in call.kwargs
        ]
        self.assertIn(2, filter_sizes)
        self.assertEqual(
            {item["title"] for item in results},
            {"Batch document 0", "Batch document 1", "Batch document 2"},
        )

    def test_search_does_not_match_body_only(self):
        results = self.client.get("/search/?q=body-only-term").json()["results"]

        self.assertEqual(results, [])

    def test_search_trims_query_and_returns_empty_for_blank_or_unknown(self):
        trimmed = self.client.get("/search/?q=%20Visible%20").json()["results"]

        self.assertEqual(trimmed[0]["title"], "Visible page")
        self.assertEqual(self.client.get("/search/?q=%20%20").json(), {"results": []})
        self.assertEqual(self.client.get("/search/?q=unknown").json(), {"results": []})

    def test_search_rejects_queries_longer_than_two_hundred_characters(self):
        response = self.client.get("/search/", {"q": "x" * 201})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "query_too_long", "results": []})

    def test_search_limits_combined_page_and_document_results_to_ten(self):
        for index in range(9):
            self._add_article(
                f"Result {index}",
                f"result-{index}",
                "<p>Result body.</p>",
            )
        for index in range(3):
            document = Document.objects.create(
                title=f"Result document {index}",
                file=ContentFile(
                    f"document-{index}".encode(), name=f"result-{index}.pdf"
                ),
            )
            self._add_article(
                f"Document page {index}",
                f"document-page-{index}",
                (
                    f'<p><a linktype="document" id="{document.pk}">'
                    f"{document.title}</a></p>"
                ),
            )
        call_command("update_index", verbosity=0)

        results = self.client.get("/search/?q=Result").json()["results"]

        self.assertEqual(len(results), 10)
        self.assertEqual(
            sum(item["type"] == "document" for item in results),
            1,
        )

    def test_search_limits_results_to_ten(self):
        for index in range(12):
            self._add_article(
                f"Result {index}",
                f"result-{index}",
                "<p>Result body.</p>",
            )
        call_command("update_index", verbosity=0)

        results = self.client.get("/search/?q=Result").json()["results"]

        self.assertEqual(len(results), 10)

    def test_search_rejects_post(self):
        self.assertEqual(
            self.client.post("/search/", {"q": "Visible"}).status_code,
            405,
        )

    def test_search_returns_empty_results_when_site_is_missing(self):
        self.site.delete()

        self.assertEqual(self.client.get("/search/?q=Visible").json(), {"results": []})
