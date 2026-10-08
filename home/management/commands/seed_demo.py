from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from home.models import ArticlePage, HomePage, SectionPage


HOME_SLUG = "demo-home"
SECTION_SLUGS = ("foo", "bar", "baz")


class Command(BaseCommand):
    help = "Create or reuse the Wagtail Bootstrap search demo content."

    def handle(self, *args, **options):
        root = Page.get_first_root_node()
        home = HomePage.objects.child_of(root).filter(slug=HOME_SLUG).first()
        if home is None:
            home = root.add_child(
                instance=HomePage(title="Demo home", slug=HOME_SLUG)
            )
            self.stdout.write(f"Created home page: {home.title}")
        else:
            self.stdout.write(f"Reusing home page: {home.title}")
        self._publish(home)

        for slug in SECTION_SLUGS:
            section = SectionPage.objects.child_of(home).filter(slug=slug).first()
            if section is None:
                section = home.add_child(
                    instance=SectionPage(
                        title=slug,
                        slug=slug,
                        show_in_menus=True,
                    )
                )
                self.stdout.write(f"Created section: {slug}")
            else:
                self.stdout.write(f"Reusing section: {slug}")
                section_updates = []
                if not section.show_in_menus:
                    section.show_in_menus = True
                    section_updates.append("show_in_menus")
                if section_updates:
                    section.save(update_fields=section_updates)
            self._publish(section)

            article = (
                ArticlePage.objects.child_of(section)
                .filter(slug="sample-article")
                .first()
            )
            if article is None:
                article = section.add_child(
                    instance=ArticlePage(
                        title=f"{slug.title()} sample article",
                        slug="sample-article",
                        body=f"<p>Welcome to the {slug} section.</p>",
                    )
                )
                self.stdout.write(f"Created article for: {slug}")
            else:
                self.stdout.write(f"Reusing article for: {slug}")
            self._publish(article)

        site = Site.objects.get(is_default_site=True)
        if site.root_page_id != home.id:
            site.root_page = home
            site.save(update_fields=["root_page"])
        self.stdout.write(self.style.SUCCESS("Demo data is ready."))

    @staticmethod
    def _publish(page):
        page.save_revision().publish()
