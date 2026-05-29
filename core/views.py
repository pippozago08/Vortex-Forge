from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic import TemplateView

from catalog.forms import CustomBuildRequestForm
from catalog.models import Build, CustomBuildRequest
from catalog.notifications import notify_custom_request_submitted
from contacts.forms import ContactMessageForm


def legal_content():
    return {
        "privacy": {
            "title": _("Privacy Policy"),
            "intro": _(
                "Informativa strutturata per una piattaforma professionale, pronta per essere rifinita con i dati legali definitivi del titolare."
            ),
            "sections": [
                (
                    _("Titolare del trattamento"),
                    _("Il titolare del trattamento e il gestore del sito Vortex Forge. I dati aziendali aggiornati sono riportati nel footer e nelle impostazioni del sito."),
                ),
                (
                    _("Dati raccolti"),
                    _("Raccogliamo dati di registrazione, richieste build, messaggi di contatto, log di sicurezza e informazioni tecniche necessarie al corretto funzionamento della piattaforma."),
                ),
                (
                    _("Finalita del trattamento"),
                    _("I dati vengono trattati per gestione account, richieste commerciali, assistenza clienti, sicurezza del sito, adempimenti amministrativi e miglioramento del servizio."),
                ),
                (
                    _("Conservazione"),
                    _("I dati vengono conservati per il tempo necessario a fornire il servizio, tutelare la sicurezza e rispettare eventuali obblighi di legge."),
                ),
                (
                    _("Diritti dell'utente"),
                    _("L'utente puo richiedere accesso, rettifica, cancellazione, limitazione, opposizione e portabilita nei limiti previsti dalla normativa applicabile."),
                ),
            ],
        },
        "terms": {
            "title": _("Termini e Condizioni"),
            "intro": _("Condizioni generali iniziali per uso del sito, richieste commerciali e accesso alle aree riservate."),
            "sections": [
                (
                    _("Oggetto del servizio"),
                    _("Il sito presenta configurazioni PC, raccoglie richieste personalizzate, richieste di acquisto e comunicazioni commerciali verso il gestore."),
                ),
                (
                    _("Account"),
                    _("L'utente e responsabile delle credenziali, delle informazioni inserite e dell'uso lecito del proprio account."),
                ),
                (
                    _("Catalogo e disponibilita"),
                    _("Prezzi, disponibilita, immagini e componenti possono variare e restano soggetti a conferma commerciale prima della conclusione della vendita."),
                ),
                (
                    _("Limitazioni di responsabilita"),
                    _("Il gestore adotta misure ragionevoli per mantenere accuratezza e continuita del servizio, ma non garantisce assenza assoluta di interruzioni o errori."),
                ),
                (
                    _("Legge applicabile"),
                    _("Il servizio e regolato dalla legge italiana, salvo norme imperative di tutela del consumatore eventualmente applicabili."),
                ),
            ],
        },
        "cookies": {
            "title": _("Cookie Policy"),
            "intro": _("Informativa iniziale dedicata ai cookie tecnici e funzionali presenti nella piattaforma."),
            "sections": [
                (
                    _("Cookie tecnici"),
                    _("Il sito utilizza cookie tecnici e di sessione per autenticazione, sicurezza, preferenze di interfaccia e funzionamento delle aree riservate."),
                ),
                (
                    _("Preferenze utente"),
                    _("La modalita dark o light e la lingua selezionata vengono salvate per offrire una navigazione coerente tra una visita e l'altra."),
                ),
                (
                    _("Cookie di sicurezza"),
                    _("Alcuni cookie servono a proteggere login, sessioni e richieste sensibili tramite le funzionalita native del framework."),
                ),
                (
                    _("Gestione del consenso"),
                    _("Se in futuro verranno introdotti cookie statistici o marketing, sara necessario integrare una gestione consenso conforme."),
                ),
                (
                    _("Disattivazione"),
                    _("L'utente puo gestire i cookie tramite le impostazioni del browser, tenendo conto che alcune funzioni protette potrebbero non operare correttamente."),
                ),
            ],
        },
    }


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_visible_builds(self):
        return Build.objects.filter(is_visible=True, is_archived=False).order_by("-is_featured", "sort_order", "-created_at")

    def get_context_data(self, custom_request_form=None, contact_form=None, active_home_form="", **kwargs):
        context = super().get_context_data(**kwargs)
        visible_builds = self.get_visible_builds()
        clients_served_count = (
            CustomBuildRequest.objects.filter(status=CustomBuildRequest.Status.PAID)
            .values("user_id")
            .distinct()
            .count()
        )
        context.update(
            {
                "builds": visible_builds,
                "build_count": visible_builds.count(),
                "custom_request_form": custom_request_form or CustomBuildRequestForm(),
                "contact_form": contact_form or ContactMessageForm(),
                "active_home_form": active_home_form,
                "clients_served_count": clients_served_count,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        form_type = request.POST.get("form_type")

        if form_type == "custom_request":
            if not request.user.is_authenticated:
                messages.error(request, _("Devi accedere per inviare una richiesta personalizzata."))
                return redirect(f"{reverse('accounts:login')}?next={reverse('core:home')}")

            custom_request_form = CustomBuildRequestForm(request.POST)
            if custom_request_form.is_valid():
                request_obj = custom_request_form.save(commit=False)
                request_obj.user = request.user
                request_obj.save()
                notify_custom_request_submitted(request_obj, request=request)
                messages.success(
                    request,
                    _("Richiesta inviata correttamente. Ora la trovi nel tuo account con stato In approvazione."),
                )
                return redirect("accounts:dashboard")

            context = self.get_context_data(
                custom_request_form=custom_request_form,
                contact_form=ContactMessageForm(),
                active_home_form="custom_request",
            )
            return self.render_to_response(context)

        if form_type == "contact":
            contact_form = ContactMessageForm(request.POST)
            if contact_form.is_valid():
                contact_form.save()
                messages.success(request, _("Messaggio inviato correttamente. Ti ricontatteremo al piu presto."))
                return redirect(f"{reverse('core:home')}#contacts-section")

            context = self.get_context_data(
                custom_request_form=CustomBuildRequestForm() if request.user.is_authenticated else CustomBuildRequestForm(),
                contact_form=contact_form,
                active_home_form="contact",
            )
            return self.render_to_response(context)

        return redirect("core:home")


class LegalPageView(TemplateView):
    template_name = "core/legal_page.html"
    page_key = "privacy"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page"] = legal_content()[self.page_key]
        return context


def get_public_base_url(request):
    configured_url = (settings.SITE_PUBLIC_URL or "").strip().rstrip("/")
    if configured_url:
        return configured_url
    return request.build_absolute_uri("/").rstrip("/")


def robots_txt(request):
    base_url = get_public_base_url(request)
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {base_url}{reverse('core:sitemap')}",
            "",
        ]
    )
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    base_url = get_public_base_url(request)
    today = timezone.now().date().isoformat()
    urls = [
        (reverse("core:home"), "1.0", "daily"),
        (reverse("core:privacy"), "0.3", "monthly"),
        (reverse("core:terms"), "0.3", "monthly"),
        (reverse("core:cookies"), "0.3", "monthly"),
    ]

    for build in Build.objects.filter(is_visible=True, is_archived=False).only("slug", "updated_at").order_by("slug"):
        urls.append((reverse("catalog:build_detail", kwargs={"slug": build.slug}), "0.8", "weekly"))

    entries = []
    for path, priority, changefreq in urls:
        entries.append(
            "  <url>\n"
            f"    <loc>{escape(base_url + path)}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")
