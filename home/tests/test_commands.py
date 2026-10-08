from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page, Site

from home.models import ArticlePage, HomePage, SectionPage


class SeedDemoCommandTests(TestCase):
    def run_seed(self):
        return call_command("seed_demo", stdout=StringIO())

    def test_seed_demo_creates_expected_tree(self):
        self.run_seed()

        home = HomePage.objects.get(slug="demo-home")
        sections = list(
            SectionPage.objects.child_of(home).order_by("slug")
        )

        self.assertEqual([section.slug for section in sections], ["bar", "baz", "foo"])
        self.assertEqual([section.title for section in sections], ["bar", "baz", "foo"])
        self.assertTrue(home.live)
        self.assertTrue(all(section.live for section in sections))
        self.assertTrue(all(section.show_in_menus for section in sections))
        self.assertEqual(
            [ArticlePage.objects.child_of(section).count() for section in sections],
            [1, 1, 1],
        )
        self.assertEqual(Site.objects.get(is_default_site=True).root_page_id, home.id)

    def test_seed_demo_is_idempotent_and_preserves_body(self):
        self.run_seed()
        home = HomePage.objects.get(slug="demo-home")
        article = ArticlePage.objects.child_of(home.get_children().first()).first()
        article.body = "<p>Editor content</p>"
        article.save_revision().publish()
        page_counts = {
            "home": HomePage.objects.count(),
            "sections": SectionPage.objects.count(),
            "articles": ArticlePage.objects.count(),
        }

        self.run_seed()

        self.assertEqual(
            page_counts,
            {
                "home": HomePage.objects.count(),
                "sections": SectionPage.objects.count(),
                "articles": ArticlePage.objects.count(),
            },
        )
        self.assertEqual(
            ArticlePage.objects.get(pk=article.pk).body,
            "<p>Editor content</p>",
        )
