import hashlib
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.core.mail import send_mail
from django.db import models, transaction
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import FormView, TemplateView, UpdateView

from core.models import SiteSetting
from core.utils import log_admin_action

from .forms import (
    AccountDeletionVerifyForm,
    LoginForm,
    PasswordResetCompleteForm,
    PasswordResetRequestForm,
    PasswordResetVerifyForm,
    ProfileForm,
    RegisterForm,
)
from .models import AccountDeletionRequest, Ban, LoginAttempt, PasswordResetRequest


User = get_user_model()


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def login_is_rate_limited(email, ip_address):
    threshold = timezone.now() - timedelta(minutes=15)
    failed_attempts = LoginAttempt.objects.filter(
        created_at__gte=threshold,
        was_successful=False,
    ).filter(models.Q(email__iexact=email) | models.Q(ip_address=ip_address))
    return failed_attempts.count() >= 5


def build_public_url(request, path):
    public_base = getattr(settings, "SITE_PUBLIC_URL", "").strip().rstrip("/")
    current_host = request.get_host()

    if public_base and current_host in {"127.0.0.1:8000", "localhost:8000", "testserver"}:
        return f"{public_base}{path}"

    return request.build_absolute_uri(path)


def send_password_reset_code(request, reset_request, raw_token, code):
    site_settings = SiteSetting.load()
    verify_url = build_public_url(
        request,
        reverse("accounts:password_reset_verify", kwargs={"token": raw_token})
    )
    send_mail(
        subject=_("Codice recupero password %(site)s") % {"site": site_settings.site_name},
        message=_(
            "Hai richiesto il recupero della password.\n\n"
            "Codice di verifica: %(code)s\n"
            "Pagina di verifica: %(url)s\n\n"
            "Il codice scade alle %(date)s e dura 2 minuti."
        )
        % {
            "code": code,
            "url": verify_url,
            "date": timezone.localtime(reset_request.expires_at).strftime("%d/%m/%Y %H:%M"),
        },
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reset_request.user.email],
        fail_silently=False,
    )


def send_account_deletion_code(request, deletion_request, raw_token, code):
    site_settings = SiteSetting.load()
    verify_url = build_public_url(
        request,
        reverse("accounts:account_delete_verify", kwargs={"token": raw_token})
    )
    send_mail(
        subject=_("Codice eliminazione account %(site)s") % {"site": site_settings.site_name},
        message=_(
            "Hai richiesto l'eliminazione definitiva del tuo account.\n\n"
            "Codice di verifica: %(code)s\n"
            "Pagina di verifica: %(url)s\n\n"
            "Il codice scade alle %(date)s e dura 2 minuti.\n"
            "Se non sei stato tu, ignora questa email e cambia la password."
        )
        % {
            "code": code,
            "url": verify_url,
            "date": timezone.localtime(deletion_request.expires_at).strftime("%d/%m/%Y %H:%M"),
        },
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[deletion_request.user.email],
        fail_silently=False,
    )


class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("accounts:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        log_admin_action(None, "create_user", _("Nuovo utente creato %(username)s") % {"username": user.display_name}, user)
        login(self.request, user, backend="accounts.backends.EmailOrUsernameBackend")
        messages.success(self.request, _("Account creato correttamente."))
        return super().form_valid(form)


class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("accounts:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data["email"].lower()
        password = form.cleaned_data["password"]
        ip_address = get_client_ip(self.request)

        if login_is_rate_limited(email, ip_address):
            messages.error(self.request, _("Troppi tentativi di accesso. Riprova tra qualche minuto."))
            return self.form_invalid(form)

        user = authenticate(self.request, username=email, password=password)
        LoginAttempt.objects.create(email=email, ip_address=ip_address, was_successful=bool(user))

        if user is None:
            messages.error(self.request, _("Credenziali non valide."))
            return self.form_invalid(form)

        active_ban = user.get_active_ban()
        if active_ban:
            self.request.session["ban_notice_id"] = active_ban.pk
            messages.error(self.request, active_ban.summary_message)
            return redirect("accounts:banned")

        login(self.request, user)
        messages.success(self.request, _("Accesso effettuato con successo."))
        return super().form_valid(form)


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        custom_requests = self.request.user.custom_build_requests.select_related("reviewed_by").order_by("-created_at")
        payments = self.request.user.custom_build_payments.select_related("custom_request").order_by("-initiated_at")
        context["custom_requests"] = custom_requests[:10]
        context["custom_request_total"] = custom_requests.count()
        context["custom_request_approval_total"] = custom_requests.filter(status="in_approval").count()
        context["custom_request_payable_total"] = custom_requests.filter(status__in=["approved", "payment_failed", "payment_pending"]).count()
        context["custom_request_paid_total"] = custom_requests.filter(status="paid").count()
        context["payment_success_total"] = payments.filter(status="succeeded").count()
        context["payment_failed_total"] = payments.filter(status="failed").count()
        context["payment_pending_total"] = payments.filter(status__in=["created", "pending"]).count()
        context["recent_payments"] = payments[:10]
        context["purchase_requests"] = self.request.user.build_purchase_requests.filter(custom_request__isnull=True)[:10]
        context["active_ban"] = self.request.user.get_active_ban()
        return context


DashboardView = method_decorator(never_cache, name="dispatch")(DashboardView)


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, _("Profilo aggiornato correttamente."))
        return super().form_valid(form)


class PasswordResetRequestView(FormView):
    template_name = "accounts/password_reset_request.html"
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy("accounts:password_reset_request")

    def form_valid(self, form):
        email = form.cleaned_data["email"].lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user:
            reset, raw_token, code = PasswordResetRequest.build_request(user, get_client_ip(self.request))
            reset.save()
            send_password_reset_code(self.request, reset, raw_token, code)
            self.request.session["password_reset_email"] = user.email

            messages.success(self.request, _("Ti abbiamo inviato un codice di verifica via email."))
            return redirect("accounts:password_reset_verify", token=raw_token)

        messages.success(self.request, _("Se l'indirizzo esiste, invieremo un codice di recupero via email."))
        return super().form_valid(form)


class PasswordResetVerifyView(FormView):
    template_name = "accounts/password_reset_verify.html"
    form_class = PasswordResetVerifyForm

    def dispatch(self, request, *args, **kwargs):
        self.reset_request = PasswordResetRequest.objects.filter(
            token_hash=hashlib.sha256(kwargs["token"].encode("utf-8")).hexdigest()
        ).first()
        if not self.reset_request or self.reset_request.used_at:
            messages.error(request, _("La richiesta di reset non e valida. Ripeti la procedura."))
            return redirect("accounts:password_reset_request")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if not self.reset_request.is_valid:
            messages.error(self.request, _("Il codice e scaduto. Premi Reinvia codice per riceverne uno nuovo."))
            return self.form_invalid(form)

        code = form.cleaned_data["verification_code"]
        if not self.reset_request.matches_code(code):
            messages.error(self.request, _("Codice di verifica non corretto."))
            return self.form_invalid(form)

        self.reset_request.mark_verified()
        self.request.session["verified_reset_id"] = self.reset_request.pk
        return redirect("accounts:password_reset_complete", token=self.kwargs["token"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reset_request"] = self.reset_request
        context["reset_token"] = self.kwargs["token"]
        context["code_expired"] = not self.reset_request.is_valid
        return context


class PasswordResetResendView(View):
    def post(self, request, *args, **kwargs):
        reset_request = PasswordResetRequest.objects.filter(
            token_hash=hashlib.sha256(kwargs["token"].encode("utf-8")).hexdigest(),
            used_at__isnull=True,
        ).select_related("user").first()

        if not reset_request or not reset_request.user.is_active:
            messages.error(request, _("La richiesta di reset non e valida. Ripeti la procedura."))
            return redirect("accounts:password_reset_request")

        code = reset_request.refresh_code()
        send_password_reset_code(request, reset_request, kwargs["token"], code)
        request.session.pop("verified_reset_id", None)
        request.session["password_reset_email"] = reset_request.user.email
        messages.success(request, _("Ti abbiamo inviato un nuovo codice. Il precedente non e piu valido."))
        return redirect("accounts:password_reset_verify", token=kwargs["token"])


class PasswordResetCompleteView(FormView):
    template_name = "accounts/password_reset_complete.html"
    form_class = PasswordResetCompleteForm
    success_url = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        self.reset_request = PasswordResetRequest.objects.filter(
            token_hash=hashlib.sha256(kwargs["token"].encode("utf-8")).hexdigest()
        ).first()
        verified_id = request.session.get("verified_reset_id")
        if (
            not self.reset_request
            or not self.reset_request.is_valid
            or not self.reset_request.verified_at
            or verified_id != self.reset_request.pk
        ):
            messages.error(request, _("Verifica reset non valida. Ripeti la procedura."))
            return redirect("accounts:password_reset_request")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.reset_request.user
        user.set_password(form.cleaned_data["password1"])
        user.save(update_fields=["password"])
        self.reset_request.mark_used()
        self.request.session.pop("verified_reset_id", None)
        messages.success(self.request, _("Password aggiornata correttamente. Ora puoi accedere."))
        return super().form_valid(form)


class AccountDeleteRequestView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.role == User.Role.SUPER_ADMIN:
            messages.error(request, _("Il super admin non puo eliminare il proprio account da questa sezione."))
            return redirect("accounts:dashboard")

        deletion_request, raw_token, code = AccountDeletionRequest.build_request(
            request.user,
            get_client_ip(request),
        )
        deletion_request.save()
        send_account_deletion_code(request, deletion_request, raw_token, code)
        request.session["account_deletion_email"] = request.user.email
        messages.success(request, _("Ti abbiamo inviato un codice di conferma per eliminare l'account."))
        return redirect("accounts:account_delete_verify", token=raw_token)


class AccountDeleteVerifyView(LoginRequiredMixin, FormView):
    template_name = "accounts/account_delete_verify.html"
    form_class = AccountDeletionVerifyForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.role == User.Role.SUPER_ADMIN:
            messages.error(request, _("Il super admin non puo eliminare il proprio account da questa sezione."))
            return redirect("accounts:dashboard")

        self.deletion_request = AccountDeletionRequest.objects.filter(
            token_hash=hashlib.sha256(kwargs["token"].encode("utf-8")).hexdigest(),
            user=request.user,
        ).first()
        if not self.deletion_request or self.deletion_request.used_at:
            messages.error(request, _("La richiesta di eliminazione non e valida. Ripeti la procedura."))
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if not self.deletion_request.is_valid:
            messages.error(self.request, _("Il codice e scaduto. Premi Reinvia codice per riceverne uno nuovo."))
            return self.form_invalid(form)

        code = form.cleaned_data["verification_code"]
        if not self.deletion_request.matches_code(code):
            messages.error(self.request, _("Codice di verifica non corretto."))
            return self.form_invalid(form)

        user = self.request.user
        username = user.display_name
        with transaction.atomic():
            self.deletion_request.mark_verified()
            self.deletion_request.mark_used()
            log_admin_action(user, "delete_account", _("Eliminato account %(username)s") % {"username": username}, user)
            logout(self.request)
            user.delete()

        self.request.session.pop("account_deletion_email", None)
        messages.success(self.request, _("Account %(username)s eliminato definitivamente.") % {"username": username})
        return redirect("core:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["deletion_request"] = self.deletion_request
        context["deletion_token"] = self.kwargs["token"]
        context["code_expired"] = not self.deletion_request.is_valid
        return context


class AccountDeleteResendView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.role == User.Role.SUPER_ADMIN:
            messages.error(request, _("Il super admin non puo eliminare il proprio account da questa sezione."))
            return redirect("accounts:dashboard")

        deletion_request = AccountDeletionRequest.objects.filter(
            token_hash=hashlib.sha256(kwargs["token"].encode("utf-8")).hexdigest(),
            user=request.user,
            used_at__isnull=True,
        ).first()

        if not deletion_request:
            messages.error(request, _("La richiesta di eliminazione non e valida. Ripeti la procedura."))
            return redirect("accounts:dashboard")

        code = deletion_request.refresh_code()
        send_account_deletion_code(request, deletion_request, kwargs["token"], code)
        request.session["account_deletion_email"] = deletion_request.user.email
        messages.success(request, _("Ti abbiamo inviato un nuovo codice. Il precedente non e piu valido."))
        return redirect("accounts:account_delete_verify", token=kwargs["token"])


class BannedView(TemplateView):
    template_name = "accounts/banned.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ban = None
        ban_id = self.request.session.get("ban_notice_id")
        if ban_id:
            ban = Ban.objects.filter(pk=ban_id).first()
        if self.request.user.is_authenticated:
            ban = self.request.user.get_active_ban() or ban
        context["ban"] = ban
        return context
