from django.core.files.uploadedfile import SimpleUploadedFile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from wagtail.documents.models import Document
from wagtail.models import Page, PageViewRestriction, Site

from home.models import ArticlePage, HomePage, SectionPage


@override_settings(ALLOWED_HOSTS=["*"])
class SearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = Page.get_first_root_node()
        cls.home = root.add_child(
            instance=HomePage(title="Local home", slug="local-home")
        )
        cls.home.save_revision().publish()
        default_site = Site.objects.get(is_default_site=True)
        default_site.root_page = cls.home
        default_site.hostname = "localhost"
        default_site.port = 80
        default_site.save()

        cls.other_home = root.add_child(
            instance=HomePage(title="Other home", slug="other-home")
        )
        cls.other_home.save_revision().publish()
        Site.objects.create(
            hostname="other.test",
            port=80,
            root_page=cls.other_home,
            is_default_site=False,
        )

    def add_section(self, home=None, *, title="Section", slug="section", publish=True):
        section = (home or self.home).add_child(
            instance=SectionPage(title=title, slug=slug)
        )
        if publish:
            section.save_revision().publish()
        else:
            section.live = False
            section.save(update_fields=["live"])
        return section

    def add_article(
        self,
        section,
        *,
        title="Article",
        slug="article",
        body="<p>Article</p>",
        publish=True,
    ):
        article = section.add_child(
            instance=ArticlePage(title=title, slug=slug, body=body)
        )
        if publish:
            article.save_revision().publish()
        else:
            article.live = False
            article.save(update_fields=["live"])
        return article

    def add_document(self, title, filename="sample.pdf"):
        return Document.objects.create(
            title=title,
            file=SimpleUploadedFile(filename, b"document data", content_type="application/pdf"),
        )

    def search_results(self, query, *, host="localhost"):
        response = self.client.get("/search/", {"q": query}, HTTP_HOST=host)
        self.assertEqual(response.status_code, 200)
        return response.json()["results"]

    def test_search_finds_article_title_and_rich_text(self):
        section = self.add_section()
        title_article = self.add_article(
            section, title="Unique title phrase", slug="title"
        )
        body_article = self.add_article(
            section,
            title="Body article",
            slug="body",
            body="<p>Unusual body phrase appears here.</p>",
        )

        title_results = self.search_results("Unique title")
        body_results = self.search_results("Unusual body")

        self.assertTrue(any(result["title"] == title_article.title for result in title_results))
        self.assertTrue(any(result["title"] == body_article.title for result in body_results))
        self.assertTrue(all(result["type"] == "page" for result in body_results))

    def test_search_finds_linked_document_title(self):
        document = self.add_document("Searchable document title")
        section = self.add_section()
        self.add_article(
            section,
            body=f'<p><a linktype="document" id="{document.id}">Download</a></p>',
        )

        results = self.search_results("Searchable document")

        document_results = [result for result in results if result["type"] == "document"]
        self.assertEqual([result["title"] for result in document_results], [document.title])
        self.assertTrue(document_results[0]["url"].endswith(document.url))

    def test_search_ignores_rich_text_markup(self):
        section = self.add_section()
        self.add_article(
            section,
            body='<p><a linktype="document" id="123">Download</a></p>',
        )

        self.assertEqual(self.search_results("document"), [])

    def test_search_finds_document_link_text(self):
        document = self.add_document("Unrelated stored filename")
        section = self.add_section()
        self.add_article(
            section,
            body=(
                f'<p><a linktype="document" id="{document.id}">'
                "<strong>Special</strong> handbook</a></p>"
            ),
        )

        results = self.search_results("special handbook")

        self.assertEqual(
            [result["title"] for result in results if result["type"] == "document"],
            [document.title],
        )

    def test_search_ignores_invalid_and_missing_document_links(self):
        unrelated = self.add_document("Unrelated document")
        section = self.add_section()
        self.add_article(
            section,
            body=(
                '<a linktype="document" id="not-a-number">Unrelated document</a>'
                '<a linktype="document" id>Missing document</a>'
                f'<a linktype="document" id="{"9" * 5000}">Huge document</a>'
                '<a linktype="document" id="999999999">Missing document</a>'
                f'<a linktype="image" id="{unrelated.id}">Unrelated document</a>'
            ),
        )

        response = self.client.get("/search/", {"q": "Unrelated document"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            any(result["type"] == "document" for result in response.json()["results"])
        )

    def test_search_finds_document_link_text_across_batches(self):
        first = self.add_document("Stored first", "first.pdf")
        second = self.add_document("Stored second", "second.pdf")
        section = self.add_section()
        self.add_article(
            section,
            body=(
                f'<a linktype="document" id="{first.id}">Special handbook</a>'
                f'<a linktype="document" id="{second.id}">Other file</a>'
            ),
        )

        with patch("home.views.DOCUMENT_BATCH_SIZE", 1):
            results = self.search_results("special handbook")

        self.assertIn(first.title, [result["title"] for result in results])

    def test_document_title_relevance_beats_link_order(self):
        first = self.add_document("Handbook notes", "first.pdf")
        exact = self.add_document("Handbook handbook", "exact.pdf")
        section = self.add_section()
        self.add_article(
            section,
            body=(
                f'<a linktype="document" id="{first.id}">First file</a>'
                f'<a linktype="document" id="{exact.id}">Second file</a>'
            ),
        )

        call_command("update_index", stdout=StringIO())
        with patch("home.views.DOCUMENT_BATCH_SIZE", 1):
            results = self.search_results("handbook")

        document_titles = [
            result["title"] for result in results if result["type"] == "document"
        ]
        self.assertEqual(document_titles[:2], [exact.title, first.title])

    def test_search_excludes_unlinked_document(self):
        self.add_document("Unlinked document title")
        section = self.add_section()
        self.add_article(section, body="<p>No document is linked here.</p>")

        results = self.search_results("Unlinked document")

        self.assertEqual(results, [])

    def test_search_is_scoped_to_current_site(self):
        local_section = self.add_section(title="Local section", slug="local")
        local_article = self.add_article(
            local_section, title="Local needle", slug="local-needle"
        )
        hidden = self.add_article(
            local_section,
            title="Hidden needle",
            slug="hidden-needle",
            publish=False,
        )
        PageViewRestriction.objects.create(
            page=hidden,
            restriction_type=PageViewRestriction.PASSWORD,
            password="secret",
        )
        private = self.add_article(
            local_section,
            title="Private needle",
            slug="private-needle",
        )
        PageViewRestriction.objects.create(
            page=private,
            restriction_type=PageViewRestriction.PASSWORD,
            password="secret",
        )
        other_section = self.add_section(
            self.other_home, title="Other section", slug="other"
        )
        other_document = self.add_document("Other site document", "other.pdf")
        other_article = self.add_article(
            other_section,
            title="Other needle",
            slug="other-needle",
            body=f'<a linktype="document" id="{other_document.id}">Other file</a>',
        )

        local_results = self.search_results("needle")
        other_results = self.search_results("needle", host="other.test")

        self.assertIn(local_article.title, [result["title"] for result in local_results])
        self.assertNotIn(other_article.title, [result["title"] for result in local_results])
        self.assertNotIn(hidden.title, [result["title"] for result in local_results])
        self.assertNotIn(private.title, [result["title"] for result in local_results])
        self.assertEqual([result["title"] for result in other_results], [other_article.title])
        self.assertFalse(
            any(
                result["type"] == "document"
                for result in self.search_results("Other site document")
            )
        )
        self.assertEqual(
            [result["title"] for result in self.search_results("Other site document", host="other.test")],
            [other_document.title],
        )

    def test_search_ignores_nested_articles(self):
        section = self.add_section()
        direct = self.add_article(section, title="Direct article", slug="direct")
        self.add_article(
            direct,
            title="Nested secret article",
            slug="nested",
            body="<p>Nested secret term.</p>",
        )

        results = self.search_results("Nested secret")

        self.assertEqual(results, [])

    def test_empty_query_returns_no_results(self):
        response = self.client.get("/search/", {"q": "   "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": []})

    def test_long_query_returns_400(self):
        response = self.client.get("/search/", {"q": "x" * 201})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"error": "query_too_long", "results": []},
        )

    def test_search_returns_at_most_10_results(self):
        for index in range(12):
            section = self.add_section(slug=f"section-{index}", title=f"Section {index}")
            self.add_article(
                section,
                slug=f"article-{index}",
                title=f"Common result {index}",
                body="<p>common result body</p>",
            )

        results = self.search_results("common")

        self.assertLessEqual(len(results), 10)
