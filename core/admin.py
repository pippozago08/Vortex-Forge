from django.contrib import admin

from .models import AdminActivityLog, SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("site_name", "support_email", "support_phone", "updated_at")


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "object_type", "created_at")
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("description", "object_type", "object_id")
