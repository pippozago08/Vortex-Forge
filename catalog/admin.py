from django.contrib import admin

from .models import Build, BuildImage, BuildPurchaseRequest, CustomBuildPayment, CustomBuildRequest


class BuildImageInline(admin.TabularInline):
    model = BuildImage
    extra = 1


@admin.register(Build)
class BuildAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "release_date", "cpu_brand", "gpu_brand", "case_brand", "ram_gb", "vram_gb", "sold_count", "availability_status", "is_visible", "is_archived")
    list_filter = ("cpu_brand", "gpu_brand", "case_brand", "release_date", "availability_status", "is_visible", "is_archived")
    exclude = ("highlight_badge",)
    readonly_fields = ("sold_count",)
    search_fields = ("name", "category", "short_description", "components")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BuildImageInline]


@admin.register(CustomBuildRequest)
class CustomBuildRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "configuration_summary", "budget_range_display", "status", "approved_price", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__email", "cpu", "gpu", "power_supply", "ram", "storage", "notes")


@admin.register(BuildPurchaseRequest)
class BuildPurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("build", "email", "phone", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("build__name", "email", "full_name", "phone")


@admin.register(CustomBuildPayment)
class CustomBuildPaymentAdmin(admin.ModelAdmin):
    list_display = ("custom_request", "provider", "amount", "currency", "status", "initiated_at", "completed_at")
    list_filter = ("provider", "status", "currency", "initiated_at")
    search_fields = ("custom_request__user__email", "custom_request__id", "external_order_id", "external_transaction_id")
