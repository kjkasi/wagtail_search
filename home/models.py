from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page, Site


class BasePage(Page):
    class Meta(Page.Meta):
        abstract = True

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        site = Site.find_for_request(request)
        root_page = site.root_page if site else self.get_root()
        context["navigation_items"] = root_page.get_children().live().in_menu()
        return context


class HomePage(BasePage):
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]  # noqa: RUF012
    subpage_types = ["home.ArticlePage"]  # noqa: RUF012

    intro = RichTextField(features=["bold", "italic", "link"])

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]


class ArticlePage(BasePage):
    parent_page_types = ["home.HomePage"]  # noqa: RUF012

    body = RichTextField(
        features=[
            "h2",
            "h3",
            "bold",
            "italic",
            "ol",
            "ul",
            "link",
            "document-link",
            "image",
        ]
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]
