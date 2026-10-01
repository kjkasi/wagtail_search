from django.test import TestCase


class ProjectSmokeTests(TestCase):
    def test_wagtail_admin_login_is_available(self):
        response = self.client.get("/admin/login/")

        self.assertEqual(getattr(response, "status_code", None), 200)
