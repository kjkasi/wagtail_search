from django.conf import settings
from django.test import SimpleTestCase


class ProjectScaffoldTests(SimpleTestCase):
    def test_required_apps_are_installed(self):
        self.assertIn("home", settings.INSTALLED_APPS)
        self.assertIn("wagtail", settings.INSTALLED_APPS)
        self.assertIn("wagtail.admin", settings.INSTALLED_APPS)

    def test_static_and_media_urls_are_configured(self):
        self.assertTrue(settings.STATIC_URL)
        self.assertTrue(settings.MEDIA_URL)
