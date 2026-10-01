from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page, Site

from home.models import ArticlePage, HomePage


class SearchViewTests(TestCase):
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
        self.assertEqual(
            response.json()["results"],
            [{"title": "Visible page", "url": self.visible.url}],
        )

    def test_search_includes_hidden_live_page_but_excludes_draft_and_root(self):
        results = self.client.get("/search/?q=page").json()["results"]
        titles = [item["title"] for item in results]

        self.assertIn("Hidden page", titles)
        self.assertNotIn("Draft page", titles)
        self.assertNotIn("Demo Home", titles)

    def test_search_does_not_match_body_only(self):
        results = self.client.get("/search/?q=body-only-term").json()["results"]

        self.assertEqual(results, [])

    def test_search_trims_query_and_returns_empty_for_blank_or_unknown(self):
        trimmed = self.client.get("/search/?q=%20Visible%20").json()["results"]

        self.assertEqual(trimmed[0]["title"], "Visible page")
        self.assertEqual(self.client.get("/search/?q=%20%20").json(), {"results": []})
        self.assertEqual(self.client.get("/search/?q=unknown").json(), {"results": []})

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
