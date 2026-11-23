from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase


class StaticFilesTest(SimpleTestCase):
    def test_each_feature_owns_real_templates_and_assets(self):
        pages = {"login": "login", "register": "register", "home": "home", "projects": "projects", "explore": "explore", "similarity": "checks", "profile": "profile", "user_settings": "settings"}
        for feature, page in pages.items():
            with self.subTest(feature=feature):
                self.assertTrue((settings.BASE_DIR / "templates" / feature / f"{page}.html").is_file())
                for kind, extension in (("css", "css"), ("js", "js")):
                    self.assertIsNotNone(finders.find(f"{kind}/{feature}/{page}.{extension}"))
                images = list((settings.BASE_DIR / "static/images" / feature).glob("*.svg"))
                self.assertTrue(images)
                for image in images:
                    self.assertIsNotNone(finders.find(str(image.relative_to(settings.BASE_DIR / "static"))))
        self.assertIsNotNone(finders.find("css/shared/base.css"))


class FormSecurityTest(TestCase):
    def test_post_requires_csrf_and_private_screens_require_login(self):
        user = get_user_model().objects.create_user("owner")
        for path in ("/", "/projects/new/", "/checks/run/1/", "/profile/", "/settings/", "/settings/toggle-theme/"):
            self.assertEqual(self.client.post(path, {}).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        for path in ("/login/", "/register/"):
            self.assertEqual(client.post(path, {}).status_code, 403)
        client.force_login(user)
        for path in ("/", "/projects/new/", "/checks/run/1/", "/profile/", "/settings/", "/settings/toggle-theme/", "/logout/"):
            self.assertEqual(client.post(path, {}).status_code, 403)
