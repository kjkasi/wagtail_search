from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page, Site
from wagtail.search import index


class BasePage(Page):
    class Meta:
        abstract = True

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        site = Site.find_for_request(request)
        root_page = site.root_page if site else self.get_root()
        context["navigation_items"] = (
            root_page.get_children().live().public().in_menu()
        )
        return context


class HomePage(BasePage):
    max_count = 1
    subpage_types = ["home.SectionPage"]


class SectionPage(BasePage):
    parent_page_types = ["home.HomePage"]
    subpage_types = ["home.ArticlePage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["children"] = self.get_children().live().public()
        return context


class ArticlePage(BasePage):
    parent_page_types = ["home.SectionPage"]
    body = RichTextField(
        features=[
            "h2",
            "h3",
            "bold",
            "italic",
            "ol",
            "ul",
            "link",
            "image",
            "document-link",
        ]
    )

    content_panels = Page.content_panels + [FieldPanel("body")]
    search_fields = Page.search_fields + [index.SearchField("body")]
