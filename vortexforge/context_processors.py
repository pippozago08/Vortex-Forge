from datetime import date

from core.models import SiteSetting


def site_context(request):
    return {
        "current_year": date.today().year,
        "site_settings": SiteSetting.load(),
    }
