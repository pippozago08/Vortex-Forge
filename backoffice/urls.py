from django.urls import path

from . import views


app_name = "backoffice"


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("builds/", views.build_list, name="build_list"),
    path("builds/new/", views.build_create, name="build_create"),
    path("builds/<int:pk>/", views.build_edit, name="build_edit"),
    path("builds/<int:pk>/toggle-visibility/", views.build_toggle_visibility, name="build_toggle_visibility"),
    path("builds/<int:pk>/toggle-archive/", views.build_toggle_archive, name="build_toggle_archive"),
    path("builds/<int:pk>/delete/", views.build_delete, name="build_delete"),
    path("builds/images/<int:image_id>/delete/", views.build_delete_image, name="build_delete_image"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:pk>/", views.user_edit, name="user_edit"),
    path("bans/", views.ban_list, name="ban_list"),
    path("bans/new/", views.ban_create, name="ban_create"),
    path("bans/<int:pk>/revoke/", views.ban_revoke, name="ban_revoke"),
    path("requests/", views.requests_overview, name="requests"),
    path("requests/custom/<int:pk>/", views.custom_request_review, name="custom_request_review"),
    path("settings/", views.settings_view, name="settings"),
]
