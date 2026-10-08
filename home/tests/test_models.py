from django.test import SimpleTestCase
from wagtail.fields import RichTextField

from home.models import ArticlePage, HomePage, SectionPage


class PageModelTests(SimpleTestCase):
    def test_home_page_allows_only_one_instance(self):
        self.assertEqual(HomePage.max_count, 1)
        self.assertEqual(HomePage.subpage_types, ["home.SectionPage"])

    def test_page_type_relationships_are_restricted(self):
        self.assertEqual(SectionPage.parent_page_types, ["home.HomePage"])
        self.assertEqual(SectionPage.subpage_types, ["home.ArticlePage"])
        self.assertEqual(ArticlePage.parent_page_types, ["home.SectionPage"])

    def test_article_body_has_required_rich_text_features(self):
        self.assertIsInstance(ArticlePage.body.field, RichTextField)
        self.assertEqual(
            set(ArticlePage.body.field.features),
            {"h2", "h3", "bold", "italic", "ol", "ul", "link", "image", "document-link"},
        )
