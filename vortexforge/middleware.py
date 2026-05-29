from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        return response


class BanEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed_paths = {
            reverse("accounts:login"),
            reverse("accounts:logout"),
            reverse("accounts:banned"),
            reverse("accounts:password_reset_request"),
        }

        if request.user.is_authenticated:
            active_ban = request.user.get_active_ban()
            if active_ban and request.path not in allowed_paths:
                logout(request)
                request.session["ban_notice_id"] = active_ban.pk
                messages.error(request, active_ban.summary_message)
                return redirect("accounts:banned")

        return self.get_response(request)
