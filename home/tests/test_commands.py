from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page, Site

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

    def test_seed_demo_ignores_nested_home_with_same_slug(self):
        root = Page.get_first_root_node()
        assert root is not None
        branch = root.add_child(instance=Page(title="Other branch", slug="other"))
        nested_home = branch.add_child(
            instance=HomePage(
                title="Nested demo home",
                slug="demo-home",
                intro="<p>Nested page.</p>",
            )
        )

        call_command("seed_demo", stdout=StringIO())

        direct_home = HomePage.objects.child_of(root).get(slug="demo-home")
        site = Site.objects.get(is_default_site=True)

        self.assertNotEqual(direct_home.id, nested_home.id)
        self.assertEqual(site.root_page_id, direct_home.id)

    def test_seed_demo_ignores_nested_article_with_same_slug(self):
        root = Page.get_first_root_node()
        assert root is not None
        home = root.add_child(
            instance=HomePage(
                title="Demo Home",
                slug="demo-home",
                intro="<p>Demo.</p>",
            )
        )
        parent = home.add_child(
            instance=ArticlePage(
                title="Existing parent",
                slug="parent",
                body="<p>Parent.</p>",
            )
        )
        nested_article = parent.add_child(
            instance=ArticlePage(
                title="Nested about",
                slug="about",
                body="<p>Keep this content.</p>",
            )
        )

        call_command("seed_demo", stdout=StringIO())

        direct_article = home.get_children().type(ArticlePage).get(slug="about")
        nested_article.refresh_from_db()

        self.assertNotEqual(direct_article.id, nested_article.id)
        self.assertEqual(nested_article.body, "<p>Keep this content.</p>")
