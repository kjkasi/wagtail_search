from io import BytesIO

from django.core.files.base import ContentFile
from django.test import TestCase
from PIL import Image as PillowImage
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import Page, Site

from home.models import ArticlePage, HomePage

Document = get_document_model()
Image = get_image_model()


class PublicPageTests(TestCase):
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
        Site.objects.update_or_create(
            hostname="localhost",
            defaults={
                "port": 80,
                "site_name": "Demo",
                "root_page": self.home,
                "is_default_site": True,
            },
        )
        self.home.save_revision().publish()

        self.visible = self._add_article(
            "Visible page", "visible", "<h2>Visible heading</h2><p>Visible text.</p>"
        )
        self.hidden = self._add_article(
            "Hidden page",
            "hidden",
            "<p>Hidden text.</p>",
            show_in_menus=False,
        )
        self.draft = self.home.add_child(
            instance=ArticlePage(
                title="Draft page",
                slug="draft",
                body="<p>Draft text.</p>",
                show_in_menus=True,
                live=False,
            )
        )

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

    def _add_image(self, title, filename):
        image_file = BytesIO()
        PillowImage.new("RGB", (4, 4), color="#336699").save(image_file, format="JPEG")
        return Image.objects.create(
            title=title,
            file=ContentFile(image_file.getvalue(), name=filename),
        )

    def test_home_page_renders_nav_items(self):
        response = self.client.get("/")

        self.assertEqual(getattr(response, "status_code", None), 200)
        self.assertContains(response, "Visible page")
        self.assertContains(response, self.visible.url)

    def test_nav_excludes_hidden_page(self):
        response = self.client.get("/")

        self.assertNotContains(response, "Hidden page")

    def test_nav_excludes_unpublished_page(self):
        response = self.client.get("/")

        self.assertNotContains(response, "Draft page")

    def test_article_renders_rich_text(self):
        response = self.client.get(self.visible.url)

        self.assertEqual(getattr(response, "status_code", None), 200)
        self.assertContains(response, "<h2>Visible heading</h2>")
        self.assertContains(response, "<p>Visible text.</p>")

    def test_article_renders_multiple_images_and_documents(self):
        first_image = self._add_image("First image", "first.jpg")
        second_image = self._add_image("Second image", "second.jpg")
        first_document = Document.objects.create(
            title="First document",
            file=ContentFile(b"first document", name="first.txt"),
        )
        second_document = Document.objects.create(
            title="Second document",
            file=ContentFile(b"second document", name="second.txt"),
        )
        body = (
            f'<embed embedtype="image" id="{first_image.pk}" alt="First image" '
            f'format="fullwidth" /><embed embedtype="image" id="{second_image.pk}" '
            f'alt="Second image" format="fullwidth" />'
            f'<p><a linktype="document" id="{first_document.pk}">First document</a></p>'
            f'<p><a linktype="document" id="{second_document.pk}">Second document</a></p>'
        )
        self.visible.body = body
        self.visible.save_revision().publish()

        response = self.client.get(self.visible.url)
        html = getattr(response, "content", b"").decode()

        self.assertEqual(getattr(response, "status_code", None), 200)
        self.assertEqual(html.count("<img"), 2)
        self.assertEqual(html.count("/documents/"), 2)
        self.assertContains(response, "First document")
        self.assertContains(response, "Second document")

    def test_base_template_contains_bootstrap_toggler_and_assets(self):
        response = self.client.get("/")

        self.assertContains(response, "navbar-toggler")
        self.assertContains(response, 'data-bs-toggle="collapse"')
        self.assertContains(response, "/static/site/main.css")
        self.assertContains(response, "/static/site/main.js")

    def test_base_template_contains_page_search_form_and_dropdown(self):
        response = self.client.get("/")

        self.assertContains(response, '<form id="pageSearchForm"')
        self.assertContains(response, 'action="/search/"')
        self.assertContains(response, 'role="search"')
        self.assertContains(response, 'id="pageSearchInput"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'aria-controls="pageSearchResults"')
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, 'id="pageSearchResults"')
        self.assertContains(response, 'role="listbox"')
