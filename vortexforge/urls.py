from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve


urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("django-admin/", admin.site.urls),
    path("account/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("builds/", include(("catalog.urls", "catalog"), namespace="catalog")),
    path("contact/", include(("contacts.urls", "contacts"), namespace="contacts")),
    path("admin-panel/", include(("backoffice.urls", "backoffice"), namespace="backoffice")),
    path("", include(("core.urls", "core"), namespace="core")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA_FILES:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT, "show_indexes": False},
        )
    ]
