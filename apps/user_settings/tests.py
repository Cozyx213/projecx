from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import UserSettings


class UserSettingsTest(TestCase):
    def test_preferences_persist_and_apply_across_the_workspace(self):
        self.assertRedirects(self.client.get("/settings/"), "/login/?next=/settings/")
        owner = get_user_model().objects.create_user("owner")
        other = get_user_model().objects.create_user("other")
        self.client.force_login(owner)
        self.assertContains(self.client.get("/"), 'id="home-tips"')
        self.assertContains(self.client.get("/settings/"), 'data-theme="light"')
        self.assertFalse(UserSettings.objects.exists())
        self.assertRedirects(self.client.post("/settings/", {"dark_mode": "on", "user": other.pk}), "/settings/")
        saved = UserSettings.objects.get(user=owner)
        self.assertTrue(saved.dark_mode)
        self.assertFalse(saved.show_home_tips)
        self.assertNotContains(self.client.get("/"), 'id="home-tips"')
        for page in ("/", "/profile/", "/settings/"):
            self.assertContains(self.client.get(page), 'data-theme="dark"')
        self.client.force_login(other)
        self.assertContains(self.client.get("/"), 'data-theme="light"')
        self.assertContains(self.client.get("/"), 'id="home-tips"')
        self.client.post("/settings/", {"show_home_tips": "on", "user": owner.pk})
        saved.refresh_from_db()
        self.assertTrue(saved.dark_mode)
        self.client.force_login(owner)
        self.assertRedirects(self.client.post("/settings/", {"show_home_tips": "on"}), "/settings/")
        saved.refresh_from_db()
        self.assertFalse(saved.dark_mode)
        self.assertTrue(saved.show_home_tips)
