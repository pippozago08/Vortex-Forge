from django.conf import settings
from django.db import models
from django.utils.translation import get_language, gettext_lazy as _

DEFAULT_HERO_TITLE = "PC per gaming, editing, rendering e workstation."
LEGACY_HERO_TITLE = "Gaming PC, configurazioni custom e supporto professionale."
LEGACY_HERO_TITLE_2 = "PC gaming, configurazioni custom e supporto professionale."
DEFAULT_HERO_SUBTITLE = (
    "Una piattaforma professionale per presentare build curate, raccogliere richieste "
    "personalizzate e gestire tutto da un pannello amministrativo reale."
)
DEFAULT_TRUST_NOTE = "Sito protetto, assistenza dedicata, richieste tracciate e gestione sicura account."
ENGLISH_DEFAULT_HERO_TITLE = "PCs for gaming, editing, rendering, and workstations."
ENGLISH_DEFAULT_HERO_SUBTITLE = (
    "A professional platform to showcase curated builds, collect custom requests, "
    "and manage everything from a real administrative panel."
)
ENGLISH_DEFAULT_TRUST_NOTE = "Protected site, dedicated support, tracked requests, and secure account management."
LEGACY_SUPPORT_EMAIL = "support@vortexforge.local"


class SiteSetting(models.Model):
    site_name = models.CharField(max_length=120, default="Vortex Forge")
    company_name = models.CharField(max_length=160, default="Vortex Forge S.r.l.")
    support_email = models.EmailField(default="support@vortexforge.local")
    support_phone = models.CharField(max_length=40, default="+39 351 984 4148")
    company_address = models.CharField(
        max_length=255,
        default="Via Magellano 27, Busa di Vigonza, Padova, Veneto, Italia",
    )
    vat_number = models.CharField(max_length=40, default="P. IVA da inserire")
    hero_title = models.CharField(
        max_length=180,
        default=DEFAULT_HERO_TITLE,
    )
    hero_title_en = models.CharField(max_length=180, blank=True)
    hero_subtitle = models.TextField(
        default=DEFAULT_HERO_SUBTITLE
    )
    hero_subtitle_en = models.TextField(blank=True)
    trust_note = models.CharField(
        max_length=180,
        default=DEFAULT_TRUST_NOTE,
    )
    trust_note_en = models.CharField(max_length=180, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Impostazione sito")
        verbose_name_plural = _("Impostazioni sito")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        updated_fields = []
        configured_support_email = getattr(settings, "SITE_SUPPORT_EMAIL", "").strip()

        if configured_support_email and (not obj.support_email or obj.support_email == LEGACY_SUPPORT_EMAIL):
            obj.support_email = configured_support_email
            updated_fields.append("support_email")

        if obj.hero_title in {LEGACY_HERO_TITLE, LEGACY_HERO_TITLE_2}:
            obj.hero_title = DEFAULT_HERO_TITLE
            updated_fields.append("hero_title")

        if updated_fields:
            obj.save(update_fields=updated_fields)

        return obj

    def __str__(self):
        return self.site_name

    @property
    def localized_hero_title(self):
        if (get_language() or "").startswith("en") and self.hero_title_en:
            return self.hero_title_en
        if (get_language() or "").startswith("en") and self.hero_title in {DEFAULT_HERO_TITLE, LEGACY_HERO_TITLE, LEGACY_HERO_TITLE_2}:
            return ENGLISH_DEFAULT_HERO_TITLE
        return self.hero_title

    @property
    def localized_hero_subtitle(self):
        if (get_language() or "").startswith("en") and self.hero_subtitle_en:
            return self.hero_subtitle_en
        if (get_language() or "").startswith("en") and self.hero_subtitle == DEFAULT_HERO_SUBTITLE:
            return ENGLISH_DEFAULT_HERO_SUBTITLE
        return self.hero_subtitle

    @property
    def localized_trust_note(self):
        if (get_language() or "").startswith("en") and self.trust_note_en:
            return self.trust_note_en
        if (get_language() or "").startswith("en") and self.trust_note == DEFAULT_TRUST_NOTE:
            return ENGLISH_DEFAULT_TRUST_NOTE
        return self.trust_note


class AdminActivityLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=120)
    description = models.TextField()
    object_type = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Log amministrativo")
        verbose_name_plural = _("Log amministrativi")

    def __str__(self):
        return f"{self.action} - {self.created_at:%d/%m/%Y %H:%M}"
