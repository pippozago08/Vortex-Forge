from django.urls import path

from .views import (
    AccountDeleteRequestView,
    AccountDeleteResendView,
    AccountDeleteVerifyView,
    BannedView,
    DashboardView,
    LoginView,
    PasswordResetCompleteView,
    PasswordResetRequestView,
    PasswordResetResendView,
    PasswordResetVerifyView,
    ProfileUpdateView,
    RegisterView,
    UserLogoutView,
)


app_name = "accounts"


urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("register/", RegisterView.as_view(), name="register"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("", DashboardView.as_view(), name="dashboard"),
    path("profile/", ProfileUpdateView.as_view(), name="profile"),
    path("banned/", BannedView.as_view(), name="banned"),
    path("password/forgot/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("password/reset/<str:token>/verify/", PasswordResetVerifyView.as_view(), name="password_reset_verify"),
    path("password/reset/<str:token>/resend/", PasswordResetResendView.as_view(), name="password_reset_resend"),
    path("password/reset/<str:token>/new/", PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("delete/", AccountDeleteRequestView.as_view(), name="account_delete_request"),
    path("delete/<str:token>/verify/", AccountDeleteVerifyView.as_view(), name="account_delete_verify"),
    path("delete/<str:token>/resend/", AccountDeleteResendView.as_view(), name="account_delete_resend"),
]
