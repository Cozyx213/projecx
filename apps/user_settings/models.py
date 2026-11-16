from django.conf import settings
from django.db import models


class UserSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dark_mode = models.BooleanField(default=False)
    show_home_tips = models.BooleanField(default=True)

    def __str__(self):
        return f"Settings for {self.user.username}"
