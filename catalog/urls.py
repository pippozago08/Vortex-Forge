from django.urls import path

from .views import (
    BuildDetailView,
    BuildListView,
    BuildPurchaseRequestCreateView,
    CustomBuildRequestView,
    CustomBuildPaymentView,
)


app_name = "catalog"


urlpatterns = [
    path("", BuildListView.as_view(), name="build_list"),
    path("custom/", CustomBuildRequestView.as_view(), name="custom_request"),
    path("custom/<int:pk>/payment/", CustomBuildPaymentView.as_view(), name="custom_request_payment"),
    path("<slug:slug>/", BuildDetailView.as_view(), name="build_detail"),
    path("<slug:slug>/request/", BuildPurchaseRequestCreateView.as_view(), name="purchase_request"),
]
