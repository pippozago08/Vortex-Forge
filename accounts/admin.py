from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AccountDeletionRequest, Ban, LoginAttempt, PasswordResetRequest, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("email",)
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Ruoli e permessi backoffice",
            {
                "fields": (
                    "role",
                    "phone",
                    "avatar",
                    "is_email_verified",
                    "can_manage_builds",
                    "can_manage_users",
                    "can_manage_bans",
                    "can_view_contacts",
                    "can_manage_settings",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            None,
            {
                "fields": (
                    "email",
                    "role",
                )
            },
        ),
    )


@admin.register(Ban)
class BanAdmin(admin.ModelAdmin):
    list_display = ("user", "ban_type", "starts_at", "ends_at", "revoked_at")
    list_filter = ("ban_type", "starts_at", "revoked_at")
    search_fields = ("user__email", "reason")


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at", "expires_at", "verified_at", "used_at")
    search_fields = ("email",)
    readonly_fields = ("token_hash", "code_hash")


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at", "expires_at", "verified_at", "used_at")
    search_fields = ("email",)
    readonly_fields = ("token_hash", "code_hash")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("email", "ip_address", "was_successful", "created_at")
    list_filter = ("was_successful", "created_at")
    search_fields = ("email", "ip_address")
