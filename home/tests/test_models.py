from django.test import RequestFactory, TestCase
from wagtail.models import Page, Site

from home.models import ArticlePage, HomePage


class PageModelTests(TestCase):
    def setUp(self):
        self.root = Page.get_first_root_node()
        assert self.root is not None
        self.home = self.root.add_child(
            instance=HomePage(title="Home", slug="demo-home", intro="Welcome")
        )
        Site.objects.update_or_create(
            hostname="localhost",
            defaults={
                "port": 80,
                "site_name": "Demo",
                "root_page": self.home,
                "is_default_site": True,
            },
        )

    def test_home_page_allows_only_one_instance(self):
        self.assertEqual(HomePage.max_count, 1)

    def test_article_page_is_only_allowed_below_home_page(self):
        self.assertEqual(HomePage.subpage_types, ["home.ArticlePage"])
        self.assertEqual(ArticlePage.parent_page_types, ["home.HomePage"])

    def test_article_body_has_required_rich_text_features(self):
        self.assertEqual(
            ArticlePage._meta.get_field("body").features,
            [
                "h2",
                "h3",
                "bold",
                "italic",
                "ol",
                "ul",
                "link",
                "document-link",
                "image",
            ],
        )

    def test_navigation_context_contains_only_live_menu_children(self):
        visible = self.home.add_child(
            instance=ArticlePage(
                title="Visible",
                slug="visible",
                body="Visible",
                show_in_menus=True,
            )
        )
        visible.save_revision().publish()
        self.home.add_child(
            instance=ArticlePage(
                title="Hidden", slug="hidden", body="Hidden", show_in_menus=False
            )
        )
        self.home.add_child(
            instance=ArticlePage(title="Draft", slug="draft", body="Draft")
        )

        request = RequestFactory().get("/", HTTP_HOST="localhost")
        context = self.home.get_context(request)

        self.assertEqual(
            list(context["navigation_items"].values_list("pk", flat=True)),
            [visible.pk],
        )
