from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Site

from home.models import ArticlePage, HomePage


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_creates_home_and_three_articles(self):
        call_command("seed_demo", stdout=StringIO())

        home = HomePage.objects.get(slug="demo-home")
        articles = list(home.get_children().specific())
        site = Site.objects.get(is_default_site=True)

        self.assertEqual(len(articles), 3)
        self.assertEqual(
            {article.slug for article in articles},
            {"about", "services", "contacts"},
        )
        self.assertTrue(home.live)
        self.assertTrue(all(article.live for article in articles))
        self.assertEqual(site.root_page_id, home.id)

    def test_seed_demo_is_idempotent_and_preserves_body(self):
        call_command("seed_demo", stdout=StringIO())
        article = ArticlePage.objects.get(slug="about")
        article.body = "<p>Custom editor content</p>"
        article.save_revision().publish()

        call_command("seed_demo", stdout=StringIO())

        self.assertEqual(HomePage.objects.filter(slug="demo-home").count(), 1)
        self.assertEqual(
            ArticlePage.objects.filter(slug__in=["about", "services", "contacts"])
            .count(),
            3,
        )
        article.refresh_from_db()
        self.assertEqual(article.body, "<p>Custom editor content</p>")
