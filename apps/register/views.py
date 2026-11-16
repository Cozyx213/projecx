from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django.urls import reverse


def register(request):
    if request.user.is_authenticated:
        return redirect("home:home")
    form = UserCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(reverse("login:login") + "?registered=1")
    return render(request, "register/register.html", {"form": form})
