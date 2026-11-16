from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Profile


class ProfileTest(TestCase):
    def test_profile_validation_persistence_and_account_isolation(self):
        self.assertRedirects(self.client.get("/profile/"), "/login/?next=/profile/")
        owner = get_user_model().objects.create_user("owner")
        other = get_user_model().objects.create_user("other")
        self.client.force_login(owner)
        self.assertContains(self.client.get("/profile/"), "Edit your profile")
        self.assertFalse(Profile.objects.exists())
        invalid = self.client.post("/profile/", {"full_name": "Student", "bio": "x" * 501})
        self.assertIn("bio", invalid.context["form"].errors)
        self.assertFalse(Profile.objects.exists())
        data = {"full_name": "Project Student", "bio": "I enjoy building useful campus tools."}
        self.assertRedirects(self.client.post("/profile/", {**data, "user": other.pk}), "/profile/")
        profile = Profile.objects.get(user=owner)
        self.assertEqual(profile.bio, data["bio"])
        self.assertRedirects(self.client.post("/profile/", {**data, "full_name": "Updated Student"}), "/profile/")
        profile.refresh_from_db()
        self.assertEqual(profile.full_name, "Updated Student")
        self.assertEqual(Profile.objects.count(), 1)
        self.client.force_login(other)
        self.assertNotContains(self.client.get("/profile/"), data["bio"])
        self.assertRedirects(self.client.post("/profile/", {**data, "user": owner.pk}), "/profile/")
        profile.refresh_from_db()
        self.assertEqual(profile.full_name, "Updated Student")

    def test_profile_bio_is_escaped(self):
        owner = get_user_model().objects.create_user("owner")
        Profile.objects.create(user=owner, full_name="<script>alert(1)</script>", bio="</textarea><script>alert(1)</script>")
        self.client.force_login(owner)
        response = self.client.get("/profile/")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")
