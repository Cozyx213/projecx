from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountFlowTest(TestCase):
    def test_exam_navigation_and_validation(self):
        self.assertRedirects(self.client.get("/"), "/login/?next=/")
        self.assertContains(self.client.get(reverse("login:login")), 'href="/register/"')
        self.assertContains(self.client.get(reverse("register:register")), 'href="/login/"')
        credentials = {"username": "student", "password": "Demo-ProjectX-739!"}
        registration = {
            "username": credentials["username"],
            "password1": credentials["password"],
            "password2": credentials["password"],
        }
        invalid = self.client.post(reverse("register:register"), {**registration, "password2": "wrong"})
        self.assertTrue(invalid.context["form"].errors)
        self.assertFalse(get_user_model().objects.exists())
        self.assertRedirects(self.client.post(reverse("register:register"), registration), "/login/?registered=1")
        self.assertTrue(get_user_model().objects.get().check_password(credentials["password"]))
        duplicate = self.client.post(reverse("register:register"), registration)
        self.assertIn("username", duplicate.context["form"].errors)
        failed_login = self.client.post(reverse("login:login"), {**credentials, "password": "wrong"})
        self.assertTrue(failed_login.context["form"].errors)
        self.assertRedirects(self.client.post(reverse("login:login"), credentials), "/")
        self.assertContains(self.client.get("/"), "Welcome, student!")
        self.assertContains(self.client.get("/"), "Your project draft")
        self.assertEqual(self.client.get(reverse("login:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("login:logout")), "/login/")
        self.assertRedirects(self.client.get("/"), "/login/?next=/")
