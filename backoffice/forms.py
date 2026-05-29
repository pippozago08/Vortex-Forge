from textwrap import shorten

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Ban, User
from catalog.models import Build, CustomBuildRequest
from core.models import SiteSetting
from core.validators import validate_uploaded_image


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        if not data:
            return []

        files = data if isinstance(data, (list, tuple)) else [data]
        cleaned_files = []
        errors = []

        for uploaded_file in files:
            try:
                cleaned_file = super().clean(uploaded_file, initial)
                validate_uploaded_image(cleaned_file)
                cleaned_files.append(cleaned_file)
            except forms.ValidationError as exc:
                errors.extend(exc.error_list)

        if errors:
            raise forms.ValidationError(errors)

        return cleaned_files


class BuildForm(forms.ModelForm):
    COMPONENT_FIELDS = (
        ("cpu", _("CPU (Processore)"), _("CPU (Processor)")),
        ("gpu", _("GPU (Scheda video/grafica)"), _("GPU (Graphics card)")),
        ("power_supply", _("Alimentatore"), _("Power supply")),
        ("ram", _("RAM"), _("RAM")),
        ("cooler", _("Dissipatore (Ad aria o liquido)"), _("Cooler (Air or liquid)")),
        ("storage", _("Archiviazione (Consigliato SSD o HDD)"), _("Storage (Recommended SSD or HDD)")),
        ("case", _("Case"), _("Case")),
        ("motherboard", _("Scheda madre"), _("Motherboard")),
        ("extra_fans", _("Ventole aggiuntive"), _("Additional fans")),
        ("network_card", _("Scheda di rete aggiuntiva 2.5 Gb +"), _("Additional network card 2.5 Gb +")),
    )

    cpu = forms.CharField(required=False)
    gpu = forms.CharField(required=False)
    power_supply = forms.CharField(required=False)
    ram = forms.CharField(required=False)
    cooler = forms.CharField(required=False)
    storage = forms.CharField(required=False)
    case = forms.CharField(required=False)
    motherboard = forms.CharField(required=False)
    extra_fans = forms.CharField(required=False)
    network_card = forms.CharField(required=False)

    class Meta:
        model = Build
        fields = (
            "name",
            "price",
            "release_date",
            "cpu_brand",
            "gpu_brand",
            "case_brand",
            "ram_gb",
            "vram_gb",
            "description",
            "primary_image",
        )
        labels = {
            "name": _("Nome build"),
            "price": _("Prezzo"),
            "release_date": _("Data uscita"),
            "cpu_brand": _("Marca processore"),
            "gpu_brand": _("Marca scheda video"),
            "case_brand": _("Marca case"),
            "ram_gb": _("RAM installata (GB)"),
            "vram_gb": _("VRAM scheda video (GB)"),
            "description": _("Note aggiuntive"),
            "primary_image": _("Immagine principale"),
        }
        widgets = {
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.01", "placeholder": "2499.00"}),
            "release_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "ram_gb": forms.NumberInput(attrs={"min": Build.RAM_GB_MIN, "max": Build.RAM_GB_MAX, "step": "1", "placeholder": "32"}),
            "vram_gb": forms.NumberInput(attrs={"min": Build.VRAM_GB_MIN, "max": Build.VRAM_GB_MAX, "step": "1", "placeholder": "12"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"placeholder": _("Nome build")})
        self.fields["price"].help_text = _("Inserisci il prezzo finale della build in euro.")
        self.fields["release_date"].input_formats = ["%Y-%m-%d"]
        self.fields["release_date"].help_text = _("Questa data alimenta l'ordinamento per uscita nel catalogo.")
        self.fields["cpu_brand"].help_text = _("Questo valore alimenta il filtro Processore nel catalogo.")
        self.fields["gpu_brand"].help_text = _("Questo valore alimenta il filtro Scheda video nel catalogo.")
        self.fields["case_brand"].help_text = _("Questo valore alimenta il filtro Marca case nel catalogo.")
        self.fields["ram_gb"].help_text = _("Inserisci quanta RAM ha il PC: minimo 4 GB, massimo 128 GB.")
        self.fields["vram_gb"].help_text = _("Inserisci quanta VRAM ha la scheda video: minimo 4 GB, massimo 64 GB.")
        self.fields["description"].widget.attrs.update({"rows": 6, "placeholder": _("Note aggiuntive sulla build")})
        self.fields["primary_image"].widget.attrs.update({"accept": "image/*"})

        parsed_components = self.parse_component_text(self.instance.components) if self.instance.pk else {}
        for field_name, label_it, _label_en in self.COMPONENT_FIELDS:
            self.fields[field_name].label = label_it
            self.fields[field_name].widget.attrs.update({"placeholder": label_it})
            if parsed_components.get(field_name):
                self.fields[field_name].initial = parsed_components[field_name]

    @classmethod
    def parse_component_text(cls, raw_text):
        lookup = {}
        for field_name, label_it, label_en in cls.COMPONENT_FIELDS:
            lookup[str(label_it).lower()] = field_name
            lookup[str(label_en).lower()] = field_name

        parsed = {}
        for line in (raw_text or "").splitlines():
            if ":" not in line:
                continue
            raw_label, raw_value = line.split(":", 1)
            field_name = lookup.get(raw_label.strip().lower())
            if field_name:
                parsed[field_name] = raw_value.strip()
        return parsed

    def build_component_lines(self, language="it"):
        lines = []
        for field_name, label_it, label_en in self.COMPONENT_FIELDS:
            value = (self.cleaned_data.get(field_name) or "").strip()
            if not value:
                continue
            label = label_it if language == "it" else label_en
            lines.append(f"{label}: {value}")
        return lines

    def save(self, commit=True):
        build = super().save(commit=False)
        description = " ".join((self.cleaned_data.get("description") or "").split())
        component_summary = " | ".join(
            filter(
                None,
                [
                    (self.cleaned_data.get("cpu") or "").strip(),
                    (self.cleaned_data.get("gpu") or "").strip(),
                    (self.cleaned_data.get("ram") or "").strip(),
                ],
            )
        )
        summary_source = description or component_summary or build.name
        build.short_description = shorten(summary_source, width=220, placeholder="...") if summary_source else build.name
        build.short_description_en = ""
        build.description_en = ""
        build.components = "\n".join(self.build_component_lines(language="it"))
        build.components_en = "\n".join(self.build_component_lines(language="en"))
        build.category = "Specifiche Build"
        build.category_en = "Build Specs"
        if not build.pk:
            build.availability_status = Build.AvailabilityStatus.AVAILABLE
            build.is_featured = False
            build.is_visible = True
            build.is_archived = False
            build.sort_order = 0
        if commit:
            build.save()
        return build

    def clean_primary_image(self):
        primary_image = self.cleaned_data.get("primary_image")
        validate_uploaded_image(primary_image)
        return primary_image


class BuildGalleryUploadForm(forms.Form):
    gallery_images = MultipleImageField(
        label=_("Immagini aggiuntive"),
        required=False,
        widget=MultipleImageInput(attrs={"accept": "image/*", "multiple": True}),
    )


class UserRoleForm(forms.ModelForm):
    def __init__(self, *args, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.role == User.Role.SUPER_ADMIN:
            self.fields["role"].choices = [(User.Role.SUPER_ADMIN, _("Super admin"))]
            self.fields["role"].disabled = True
        else:
            self.fields["role"].choices = [
                (User.Role.ADMIN, _("Admin autorizzato")),
                (User.Role.USER, _("Utente")),
            ]
            if actor and actor.role != User.Role.SUPER_ADMIN:
                self.fields["role"].disabled = True

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone",
            "role",
            "is_active",
        )
        labels = {
            "first_name": _("Nome"),
            "last_name": _("Cognome"),
            "phone": _("Telefono"),
            "role": _("Ruolo"),
            "is_active": _("Utente attivo"),
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": _("Nome")}),
            "last_name": forms.TextInput(attrs={"placeholder": _("Cognome")}),
            "phone": forms.TextInput(attrs={"placeholder": _("Telefono")}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role == User.Role.ADMIN:
            user.can_manage_builds = True
            user.can_manage_users = False
            user.can_manage_bans = True
            user.can_view_contacts = True
            user.can_manage_settings = False
        elif user.role == User.Role.USER:
            user.can_manage_builds = False
            user.can_manage_users = False
            user.can_manage_bans = False
            user.can_view_contacts = False
            user.can_manage_settings = False
        if commit:
            user.save()
        return user


class BanForm(forms.ModelForm):
    def __init__(self, *args, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        queryset = User.objects.exclude(role=User.Role.SUPER_ADMIN)
        if actor and actor.role != User.Role.SUPER_ADMIN:
            queryset = queryset.filter(role=User.Role.USER)
        self.fields["user"].queryset = queryset.order_by("username")
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["starts_at"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

    def clean_user(self):
        user = self.cleaned_data["user"]
        if self.actor and not self.actor.can_ban_target(user):
            raise forms.ValidationError(_("Non puoi applicare un ban a questo account."))
        return user

    class Meta:
        model = Ban
        fields = ("user", "ban_type", "reason", "starts_at", "ends_at")
        labels = {
            "user": _("Utente"),
            "ban_type": _("Tipo di ban"),
            "reason": _("Motivo"),
            "starts_at": _("Inizio ban"),
            "ends_at": _("Fine ban"),
        }
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 6, "placeholder": _("Motivo dettagliato del ban")}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TargetUserBanForm(BanForm):
    def __init__(self, *args, target_user=None, actor=None, **kwargs):
        self.target_user = target_user
        super().__init__(*args, actor=actor, **kwargs)
        if target_user:
            self.fields["user"].initial = target_user.pk
            self.fields["user"].queryset = User.objects.filter(pk=target_user.pk)
            self.fields["user"].widget = forms.HiddenInput()

    def clean_user(self):
        if not self.target_user:
            return super().clean_user()
        if self.actor and not self.actor.can_ban_target(self.target_user):
            raise forms.ValidationError(_("Non puoi applicare un ban a questo account."))
        return self.target_user


class SiteSettingForm(forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = (
            "site_name",
            "company_name",
            "support_email",
            "support_phone",
            "company_address",
            "vat_number",
            "hero_title",
            "hero_title_en",
            "hero_subtitle",
            "hero_subtitle_en",
            "trust_note",
            "trust_note_en",
        )
        labels = {
            "site_name": _("Nome sito"),
            "company_name": _("Nome azienda"),
            "support_email": _("Email assistenza"),
            "support_phone": _("Telefono assistenza"),
            "company_address": _("Indirizzo azienda"),
            "vat_number": _("Partita IVA"),
            "hero_title": _("Titolo hero IT"),
            "hero_title_en": _("Titolo hero EN"),
            "hero_subtitle": _("Sottotitolo hero IT"),
            "hero_subtitle_en": _("Sottotitolo hero EN"),
            "trust_note": _("Messaggio fiducia IT"),
            "trust_note_en": _("Messaggio fiducia EN"),
        }
        widgets = {
            "company_address": forms.Textarea(attrs={"rows": 3}),
            "hero_subtitle": forms.Textarea(attrs={"rows": 4}),
            "hero_subtitle_en": forms.Textarea(attrs={"rows": 4}),
            "trust_note": forms.TextInput(attrs={"placeholder": _("Messaggio fiducia in italiano")}),
            "trust_note_en": forms.TextInput(attrs={"placeholder": _("Trust message in English")}),
        }


class CustomBuildReviewForm(forms.ModelForm):
    class Meta:
        model = CustomBuildRequest
        fields = ("approved_price", "admin_notes")
        labels = {
            "approved_price": _("Prezzo finale da mostrare al cliente"),
            "admin_notes": _("Messaggio per il cliente e note del preventivo"),
        }
        widgets = {
            "approved_price": forms.NumberInput(attrs={"min": "0", "step": "0.01", "placeholder": "2499.00"}),
            "admin_notes": forms.Textarea(
                attrs={"rows": 8, "placeholder": _("Spiega il preventivo, eventuali limiti, tempi o motivi del rifiuto")}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["approved_price"].help_text = _("Questo importo comparira al cliente quando approvi la richiesta.")
        self.fields["admin_notes"].help_text = _("Questo messaggio viene mostrato al cliente nella scheda richiesta e nella pagina pagamento.")

    def clean_approved_price(self):
        price = self.cleaned_data.get("approved_price")
        if price is not None and price <= 0:
            raise forms.ValidationError(_("Inserisci un prezzo finale maggiore di zero."))
        return price
