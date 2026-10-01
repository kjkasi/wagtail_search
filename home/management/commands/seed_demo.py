from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from home.models import ArticlePage, HomePage

DEMO_ARTICLES = (
    {
        "slug": "about",
        "title": "О проекте",
        "body": "<p>Это демонстрационная дочерняя страница Wagtail.</p>",
    },
    {
        "slug": "services",
        "title": "Разделы",
        "body": "<p>Здесь можно разместить описание раздела и полезные материалы.</p>",
    },
    {
        "slug": "contacts",
        "title": "Контакты",
        "body": "<p>На этой странице можно оставить контактную информацию.</p>",
    },
)


class Command(BaseCommand):
    help = "Create the demo home page and its article pages."

    def handle(self, *args, **options):
        root_page = Page.get_first_root_node()
        if root_page is None:
            raise RuntimeError("Wagtail root page does not exist")

        home_page = HomePage.objects.filter(slug="demo-home").first()
        created_home = False

        if home_page is None:
            home_page = root_page.add_child(
                instance=HomePage(
                    title="Wagtail Bootstrap Demo",
                    slug="demo-home",
                    intro="<p>Учебный сайт на Wagtail и Bootstrap.</p>",
                )
            )
            home_page.save_revision().publish()
            created_home = True
        elif not home_page.live:
            home_page.save_revision().publish()

        created_articles = 0
        for article_data in DEMO_ARTICLES:
            article = ArticlePage.objects.filter(
                slug=article_data["slug"],
                path__startswith=home_page.path,
            ).first()
            if article is None:
                article = home_page.add_child(
                    instance=ArticlePage(
                        title=article_data["title"],
                        slug=article_data["slug"],
                        body=article_data["body"],
                        show_in_menus=True,
                    )
                )
                article.save_revision().publish()
                created_articles += 1
            elif not article.live:
                article.save_revision().publish()

        site, _ = Site.objects.get_or_create(
            is_default_site=True,
            defaults={
                "hostname": "localhost",
                "port": 80,
                "site_name": "Wagtail Bootstrap Demo",
                "root_page": home_page,
            },
        )
        if site.root_page_id != home_page.id:
            site.root_page = home_page
            site.save(update_fields=["root_page"])

        self.stdout.write(
            f"Demo ready: {'created' if created_home else 'reused'} home page, "
            f"{created_articles} article pages created."
        )
