from django.test import TestCase
from wagtail.models import Page, Site

from home.models import ArticlePage, HomePage, SectionPage


class PageRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = Page.get_first_root_node()
        cls.home = cls.root.add_child(
            instance=HomePage(title="Demo home", slug="demo-home")
        )
        cls.site = Site.objects.get(is_default_site=True)
        cls.site.root_page = cls.home
        cls.site.hostname = "localhost"
        cls.site.port = 80
        cls.site.save()
        cls.home.save_revision().publish()

    def add_section(self, title, slug, *, show_in_menus=True, publish=True):
        section = self.home.add_child(
            instance=SectionPage(
                title=title,
                slug=slug,
                show_in_menus=show_in_menus,
            )
        )
        if publish:
            section.save_revision().publish()
        else:
            section.live = False
            section.save(update_fields=["live"])
        return section

    def add_article(self, parent, title, slug, *, body="<p>Article body</p>", publish=True):
        article = parent.add_child(
            instance=ArticlePage(title=title, slug=slug, body=body)
        )
        if publish:
            article.save_revision().publish()
        else:
            article.live = False
            article.save(update_fields=["live"])
        return article

    def test_home_shows_visible_sections_in_navbar(self):
        section = self.add_section("Foo", "foo")

        response = self.client.get(self.home.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, section.title)
        self.assertContains(response, section.url)

    def test_hidden_or_unpublished_section_is_not_in_navbar(self):
        self.add_section("Hidden", "hidden", show_in_menus=False)
        self.add_section("Draft", "draft", publish=False)

        response = self.client.get(self.home.url)

        self.assertNotContains(response, "Hidden")
        self.assertNotContains(response, "Draft")

    def test_section_lists_only_direct_published_articles(self):
        section = self.add_section("Foo", "foo")
        direct = self.add_article(section, "Direct article", "direct")
        self.add_article(section, "Draft article", "draft", publish=False)
        nested = self.add_article(direct, "Nested article", "nested")

        response = self.client.get(section.url)

        self.assertContains(response, direct.title)
        self.assertNotContains(response, "Draft article")
        self.assertNotContains(response, nested.title)

    def test_article_renders_rich_text(self):
        section = self.add_section("Foo", "foo")
        article = self.add_article(
            section,
            "Rich article",
            "rich",
            body="<p><strong>Rendered rich text</strong></p>",
        )

        response = self.client.get(article.url)

        self.assertContains(response, "Rendered rich text")
        self.assertContains(response, "<strong>Rendered rich text</strong>")

    def test_base_template_uses_local_bootstrap_assets(self):
        self.add_section("Foo", "foo")

        response = self.client.get(self.home.url)
        content = response.content.decode()

        self.assertContains(response, "/static/site/main.css")
        self.assertContains(response, "/static/site/main.js")
        self.assertNotIn("https://cdn", content)
        self.assertNotIn("http://cdn", content)
