import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.validators import validate_uploaded_image


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", _("Super admin")
        ADMIN = "admin", _("Admin autorizzato")
        USER = "user", _("Utente")

    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    phone = models.CharField(max_length=40, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_email_verified = models.BooleanField(default=False)
    can_manage_builds = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_manage_bans = models.BooleanField(default=False)
    can_view_contacts = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)

    class Meta:
        ordering = ["date_joined", "email"]

    def clean(self):
        super().clean()
        validate_uploaded_image(self.avatar)

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email

        if self.role == self.Role.SUPER_ADMIN:
            self.can_manage_builds = True
            self.can_manage_users = True
            self.can_manage_bans = True
            self.can_view_contacts = True
            self.can_manage_settings = True
            self.is_staff = True
            self.is_superuser = True
        elif self.role == self.Role.ADMIN:
            self.can_manage_builds = True
            self.can_manage_users = False
            self.can_manage_bans = True
            self.can_view_contacts = True
            self.can_manage_settings = False
            self.is_staff = True
            self.is_superuser = False
        else:
            self.is_staff = False
            self.is_superuser = False
            self.can_manage_builds = False
            self.can_manage_users = False
            self.can_manage_bans = False
            self.can_view_contacts = False
            self.can_manage_settings = False

        super().save(*args, **kwargs)

    def has_backoffice_access(self):
        return self.is_active and self.role in {self.Role.SUPER_ADMIN, self.Role.ADMIN}

    def can_access_builds(self):
        return self.role == self.Role.SUPER_ADMIN or self.can_manage_builds

    def can_access_users(self):
        return self.role == self.Role.SUPER_ADMIN or self.can_manage_users

    def can_access_bans(self):
        return self.role == self.Role.SUPER_ADMIN or self.can_manage_bans

    def can_access_requests(self):
        return self.is_active and self.role in {self.Role.SUPER_ADMIN, self.Role.ADMIN}

    def can_access_contacts(self):
        return self.role == self.Role.SUPER_ADMIN or self.can_view_contacts

    def can_access_settings(self):
        return self.role == self.Role.SUPER_ADMIN or self.can_manage_settings

    def can_manage_user_target(self, target_user):
        if not target_user or not self.can_access_users():
            return False
        if self.role == self.Role.SUPER_ADMIN:
            return True
        return target_user.role == self.Role.USER

    def can_ban_target(self, target_user):
        if not target_user or not self.can_access_bans():
            return False
        if target_user.role == self.Role.SUPER_ADMIN:
            return False
        if self.role == self.Role.SUPER_ADMIN:
            return target_user.role in {self.Role.ADMIN, self.Role.USER}
        return target_user.role == self.Role.USER

    def can_revoke_ban_target(self, ban):
        if not ban:
            return False
        return self.can_ban_target(ban.user)

    def get_active_ban(self):
        now = timezone.now()
        return (
            self.bans.filter(revoked_at__isnull=True, starts_at__lte=now)
            .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now))
            .order_by("-starts_at")
            .first()
        )

    @property
    def display_name(self):
        return self.username or self.email

    def __str__(self):
        return self.display_name


class Ban(models.Model):
    class BanType(models.TextChoices):
        TEMPORARY = "temporary", _("Temporaneo")
        PERMANENT = "permanent", _("Permanente")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bans")
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_bans",
    )
    ban_type = models.CharField(max_length=20, choices=BanType.choices)
    reason = models.TextField()
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_bans",
    )
    revocation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Ban")
        verbose_name_plural = _("Ban")

    def clean(self):
        if self.user_id and self.user.role == User.Role.SUPER_ADMIN:
            raise ValidationError(_("Il super admin non puo essere bannato."))
        if self.ban_type == self.BanType.TEMPORARY and not self.ends_at:
            raise ValidationError(_("Un ban temporaneo richiede una data di fine."))
        if self.ban_type == self.BanType.PERMANENT:
            self.ends_at = None

    @property
    def is_active(self):
        if self.revoked_at:
            return False
        now = timezone.now()
        if self.starts_at > now:
            return False
        if self.ends_at and self.ends_at <= now:
            return False
        return True

    @property
    def status(self):
        if self.revoked_at:
            return "revoked"
        if self.ends_at and self.ends_at <= timezone.now():
            return "expired"
        if self.is_active:
            return "active"
        return "scheduled"

    @property
    def summary_message(self):
        if self.ban_type == self.BanType.PERMANENT:
            return _("Il tuo account e stato bannato in modo permanente. Motivo: %(reason)s") % {
                "reason": self.reason
            }
        return _(
            "Il tuo account e stato bannato fino al %(date)s. Motivo: %(reason)s"
        ) % {
            "date": timezone.localtime(self.ends_at).strftime("%d/%m/%Y %H:%M"),
            "reason": self.reason,
        }

    @property
    def translated_status(self):
        status_map = {
            "revoked": _("Revocato"),
            "expired": _("Scaduto"),
            "active": _("Attivo"),
            "scheduled": _("Programmato"),
        }
        return status_map[self.status]

    def revoke(self, actor, reason=""):
        self.revoked_at = timezone.now()
        self.revoked_by = actor
        self.revocation_reason = reason
        self.save(update_fields=["revoked_at", "revoked_by", "revocation_reason", "updated_at"])

    def __str__(self):
        return f"{self.user.display_name} - {self.get_ban_type_display()}"


class PasswordResetRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_resets")
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(blank=True, null=True)
    used_at = models.DateTimeField(blank=True, null=True)
    requested_from_ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Richiesta reset password")
        verbose_name_plural = _("Richieste reset password")

    @classmethod
    def build_request(cls, user, ip_address=None):
        raw_token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(10**6):06d}"
        reset = cls(
            user=user,
            email=user.email,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=2),
            requested_from_ip=ip_address,
        )
        return reset, raw_token, code

    def refresh_code(self):
        code = f"{secrets.randbelow(10**6):06d}"
        self.code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        self.expires_at = timezone.now() + timedelta(minutes=2)
        self.verified_at = None
        self.save(update_fields=["code_hash", "expires_at", "verified_at"])
        return code

    def matches_token(self, raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest() == self.token_hash

    def matches_code(self, code):
        return hashlib.sha256(code.encode("utf-8")).hexdigest() == self.code_hash

    @property
    def is_valid(self):
        return not self.used_at and self.expires_at > timezone.now()

    def mark_verified(self):
        self.verified_at = timezone.now()
        self.save(update_fields=["verified_at"])

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self):
        return f"Reset {self.email} - {self.created_at:%d/%m/%Y %H:%M}"


class AccountDeletionRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account_deletion_requests")
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(blank=True, null=True)
    used_at = models.DateTimeField(blank=True, null=True)
    requested_from_ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Richiesta eliminazione account")
        verbose_name_plural = _("Richieste eliminazione account")

    @classmethod
    def build_request(cls, user, ip_address=None):
        raw_token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(10**6):06d}"
        deletion = cls(
            user=user,
            email=user.email,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
            expires_at=timezone.now() + timedelta(minutes=2),
            requested_from_ip=ip_address,
        )
        return deletion, raw_token, code

    def refresh_code(self):
        code = f"{secrets.randbelow(10**6):06d}"
        self.code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        self.expires_at = timezone.now() + timedelta(minutes=2)
        self.verified_at = None
        self.save(update_fields=["code_hash", "expires_at", "verified_at"])
        return code

    def matches_code(self, code):
        return hashlib.sha256(code.encode("utf-8")).hexdigest() == self.code_hash

    @property
    def is_valid(self):
        return not self.used_at and self.expires_at > timezone.now()

    def mark_verified(self):
        self.verified_at = timezone.now()
        self.save(update_fields=["verified_at"])

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self):
        return f"Eliminazione {self.email} - {self.created_at:%d/%m/%Y %H:%M}"


class LoginAttempt(models.Model):
    email = models.EmailField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    was_successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Tentativo login")
        verbose_name_plural = _("Tentativi login")

    def __str__(self):
        return f"{self.email} - {'OK' if self.was_successful else 'FAIL'}"
