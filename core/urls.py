from django.urls import path

from .views import HomeView, LegalPageView, robots_txt, sitemap_xml


app_name = "core"


urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap_xml, name="sitemap"),
    path("privacy-policy/", LegalPageView.as_view(page_key="privacy"), name="privacy"),
    path("termini-condizioni/", LegalPageView.as_view(page_key="terms"), name="terms"),
    path("cookie-policy/", LegalPageView.as_view(page_key="cookies"), name="cookies"),
]
