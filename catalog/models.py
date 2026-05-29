from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import get_language, gettext_lazy as _

from core.validators import validate_uploaded_image


class Build(models.Model):
    RAM_GB_MIN = 4
    RAM_GB_MAX = 128
    VRAM_GB_MIN = 4
    VRAM_GB_MAX = 64

    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "available", _("Disponibile")
        PREORDER = "preorder", _("Preordine")
        UNAVAILABLE = "unavailable", _("Non disponibile")

    class HighlightBadge(models.TextChoices):
        NONE = "none", _("Nessuna")
        RECOMMENDED = "recommended", _("Consigliata")
        ON_SALE = "on_sale", _("In offerta")
        BEST_SELLER = "best_seller", _("Piu venduta")

    class CpuBrand(models.TextChoices):
        INTEL = "intel", _("Intel")
        AMD = "amd", _("AMD")

    class GpuBrand(models.TextChoices):
        INTEGRATED = "integrated", _("Integrata (predefinita)")
        NVIDIA = "nvidia", _("NVIDIA")
        RADEON = "radeon", _("Radeon AMD")
        INTEL_ARC = "intel_arc", _("Intel Arc")

    class CaseBrand(models.TextChoices):
        CORSAIR = "corsair", "Corsair"
        NZXT = "nzxt", "NZXT"
        LIAN_LI = "lian_li", "Lian Li"
        FRACTAL_DESIGN = "fractal_design", "Fractal Design"
        COOLER_MASTER = "cooler_master", "Cooler Master"
        PHANTEKS = "phanteks", "Phanteks"
        BE_QUIET = "be_quiet", "be quiet!"
        HYTE = "hyte", "HYTE"
        THERMALTAKE = "thermaltake", "Thermaltake"
        DEEPCOOL = "deepcool", "DeepCool"
        ASUS = "asus", "ASUS"
        MSI = "msi", "MSI"
        ANTEC = "antec", "Antec"
        MONTECH = "montech", "Montech"
        SILVERSTONE = "silverstone", "SilverStone"

    name = models.CharField(max_length=160)
    name_en = models.CharField(max_length=160, blank=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    release_date = models.DateField(default=timezone.localdate, verbose_name=_("Data uscita"))
    cpu_brand = models.CharField(
        max_length=20,
        choices=CpuBrand.choices,
        default=CpuBrand.INTEL,
        verbose_name=_("Marca processore"),
    )
    gpu_brand = models.CharField(
        max_length=20,
        choices=GpuBrand.choices,
        default=GpuBrand.INTEGRATED,
        verbose_name=_("Marca scheda video"),
    )
    case_brand = models.CharField(
        max_length=30,
        choices=CaseBrand.choices,
        default=CaseBrand.CORSAIR,
        verbose_name=_("Marca case"),
    )
    ram_gb = models.PositiveSmallIntegerField(
        default=RAM_GB_MIN,
        validators=[MinValueValidator(RAM_GB_MIN), MaxValueValidator(RAM_GB_MAX)],
        verbose_name=_("RAM installata (GB)"),
    )
    vram_gb = models.PositiveSmallIntegerField(
        default=VRAM_GB_MIN,
        validators=[MinValueValidator(VRAM_GB_MIN), MaxValueValidator(VRAM_GB_MAX)],
        verbose_name=_("VRAM scheda video (GB)"),
    )
    sold_count = models.PositiveIntegerField(default=0, editable=False, verbose_name=_("Vendite registrate"))
    short_description = models.CharField(max_length=220)
    short_description_en = models.CharField(max_length=220, blank=True)
    description = models.TextField()
    description_en = models.TextField(blank=True)
    components = models.TextField(help_text=_("Una componente per riga"))
    components_en = models.TextField(blank=True, help_text=_("Una componente per riga in inglese"))
    category = models.CharField(max_length=120)
    category_en = models.CharField(max_length=120, blank=True)
    primary_image = models.ImageField(upload_to="builds/primary/")
    availability_status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
    )
    highlight_badge = models.CharField(
        max_length=20,
        choices=HighlightBadge.choices,
        default=HighlightBadge.NONE,
    )
    is_featured = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_builds",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_builds",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at", "name"]
        verbose_name = _("Build")
        verbose_name_plural = _("Build")

    def save(self, *args, **kwargs):
        base_slug = slugify(self.name) or "build"
        slug = self.slug or base_slug
        counter = 2
        while Build.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        validate_uploaded_image(self.primary_image)

    def component_list(self):
        return [line.strip() for line in self.components.splitlines() if line.strip()]

    def localized_component_list(self):
        source = self.components_en if (get_language() or "").startswith("en") and self.components_en else self.components
        return [line.strip() for line in source.splitlines() if line.strip()]

    def card_component_list(self):
        hidden_labels = {
            "ventole aggiuntive",
            "additional fans",
            "scheda di rete aggiuntiva 2.5 gb +",
            "additional network card 2.5 gb +",
        }
        visible_components = []
        for line in self.localized_component_list():
            label = line.split(":", 1)[0].strip().casefold()
            if label in hidden_labels:
                continue
            visible_components.append(line)
        return visible_components

    @property
    def localized_name(self):
        if (get_language() or "").startswith("en") and self.name_en:
            return self.name_en
        return self.name

    @property
    def localized_short_description(self):
        if (get_language() or "").startswith("en") and self.short_description_en:
            return self.short_description_en
        return self.short_description

    @property
    def localized_description(self):
        if (get_language() or "").startswith("en") and self.description_en:
            return self.description_en
        return self.description

    @property
    def localized_category(self):
        if (get_language() or "").startswith("en") and self.category_en:
            return self.category_en
        return self.category

    def __str__(self):
        return self.name


class BuildImage(models.Model):
    build = models.ForeignKey(Build, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="builds/gallery/")
    alt_text = models.CharField(max_length=160, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = _("Immagine build")
        verbose_name_plural = _("Immagini build")

    def __str__(self):
        return f"{self.build.name} - immagine"

    def clean(self):
        super().clean()
        validate_uploaded_image(self.image)


class CustomBuildRequest(models.Model):
    class Origin(models.TextChoices):
        CUSTOM = "custom", _("Richiesta personalizzata")
        CATALOG_BUILD = "catalog_build", _("Build del catalogo")

    COMPONENT_FIELDS = (
        ("cpu", _("CPU (Processore)")),
        ("gpu", _("GPU (Scheda video/grafica)")),
        ("power_supply", _("Alimentatore")),
        ("ram", _("RAM")),
        ("cooling", _("Dissipatore (Ad aria o liquido)")),
        ("storage", _("Archiviazione (Consigliato SSD o HDD)")),
        ("case", _("Case")),
        ("motherboard", _("Scheda madre")),
        ("extra_fans", _("Ventole aggiuntive")),
        ("network_card", _("Scheda di rete aggiuntiva 2.5 Gb +")),
    )

    class Status(models.TextChoices):
        IN_APPROVAL = "in_approval", _("In fase di approvazione")
        APPROVED = "approved", _("Approvata")
        PAYMENT_PENDING = "payment_pending", _("Pagamento in attesa")
        PAID = "paid", _("Pagata")
        PAYMENT_FAILED = "payment_failed", _("Pagamento fallito")
        REJECTED = "rejected", _("Rifiutata")
        CANCELLED = "cancelled", _("Annullata")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custom_build_requests",
    )
    request_origin = models.CharField(max_length=20, choices=Origin.choices, default=Origin.CUSTOM)
    requested_build = models.ForeignKey(
        Build,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_custom_requests",
    )
    cpu = models.CharField(max_length=120, blank=True)
    gpu = models.CharField(max_length=120, blank=True)
    power_supply = models.CharField(max_length=120, blank=True)
    ram = models.CharField(max_length=120, blank=True)
    storage = models.CharField(max_length=120, blank=True)
    cooling = models.CharField(max_length=120, blank=True)
    case = models.CharField(max_length=120, blank=True)
    motherboard = models.CharField(max_length=120, blank=True)
    extra_fans = models.CharField(max_length=120, blank=True)
    network_card = models.CharField(max_length=120, blank=True)
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default="EUR")
    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    approved_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_APPROVAL)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_custom_requests",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Richiesta build personalizzata")
        verbose_name_plural = _("Richieste build personalizzate")

    def clean(self):
        if self.request_origin == self.Origin.CUSTOM and self.budget_max is None:
            raise ValidationError(_("Inserisci un budget massimo per la richiesta personalizzata."))
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValidationError(_("Il budget minimo non puo superare il budget massimo."))
        if self.status in {self.Status.APPROVED, self.Status.PAYMENT_PENDING, self.Status.PAID, self.Status.PAYMENT_FAILED} and self.approved_price is None:
            raise ValidationError(_("Inserisci il prezzo finale prima di approvare o rendere pagabile la richiesta."))

    @classmethod
    def approval_queue_statuses(cls):
        return (cls.Status.IN_APPROVAL,)

    @classmethod
    def approved_queue_statuses(cls):
        return (cls.Status.APPROVED, cls.Status.PAYMENT_PENDING, cls.Status.PAYMENT_FAILED)

    @classmethod
    def paid_queue_statuses(cls):
        return (cls.Status.PAID,)

    @classmethod
    def closed_queue_statuses(cls):
        return (cls.Status.REJECTED, cls.Status.CANCELLED)

    @property
    def reference_code(self):
        if not self.pk:
            return _("Nuova richiesta")
        return f"CFG-{self.pk:05d}"

    @property
    def configuration_summary(self):
        summary = " / ".join(filter(None, [self.cpu, self.gpu, self.ram]))
        if summary:
            return summary
        if self.requested_build_id and self.requested_build:
            return _("%(build)s (richiesta da catalogo)") % {"build": self.requested_build.localized_name}
        if self.request_origin == self.Origin.CATALOG_BUILD:
            return str(_("Build da catalogo"))
        return summary or str(_("Configurazione da definire"))

    @property
    def budget_range_display(self):
        if self.request_origin == self.Origin.CATALOG_BUILD:
            return _("Prezzo finale da confermare dopo l'approvazione")
        if self.budget_min is not None:
            return _("%(min)s - %(max)s %(currency)s") % {
                "min": f"{self.budget_min:.2f}",
                "max": f"{self.budget_max:.2f}",
                "currency": self.currency,
            }
        return _("%(max)s %(currency)s massimo") % {
            "max": f"{self.budget_max:.2f}",
            "currency": self.currency,
        }

    @property
    def approved_price_display(self):
        if self.approved_price is None:
            return _("Da definire")
        return f"{self.approved_price:.2f} {self.currency}"

    @property
    def status_tone(self):
        mapping = {
            self.Status.IN_APPROVAL: "warning",
            self.Status.APPROVED: "info",
            self.Status.PAYMENT_PENDING: "info",
            self.Status.PAID: "success",
            self.Status.PAYMENT_FAILED: "danger",
            self.Status.REJECTED: "danger",
            self.Status.CANCELLED: "warning",
        }
        return mapping.get(self.status, "info")

    @property
    def user_status_message(self):
        mapping = {
            self.Status.IN_APPROVAL: _("Il team sta controllando componenti, budget e fattibilita. Per ora non devi fare nulla."),
            self.Status.APPROVED: _("La richiesta e pronta: ora puoi aprire il riepilogo e procedere con il pagamento."),
            self.Status.PAYMENT_PENDING: _("Hai gia avviato il pagamento. Apri il riepilogo per completarlo."),
            self.Status.PAID: _("Pagamento confermato. La tua build personalizzata e stata registrata come pagata."),
            self.Status.PAYMENT_FAILED: _("L'ultimo tentativo non e andato a buon fine. Puoi riprovare dal riepilogo pagamento."),
            self.Status.REJECTED: _("La richiesta non e stata approvata. Controlla le note del team per capire il motivo."),
            self.Status.CANCELLED: _("La richiesta e stata chiusa e non e piu pagabile."),
        }
        return mapping.get(self.status, "")

    @property
    def ui_status_label(self):
        mapping = {
            self.Status.IN_APPROVAL: _("In approvazione"),
            self.Status.APPROVED: _("Approvata"),
            self.Status.PAYMENT_PENDING: _("Pagamento da completare"),
            self.Status.PAID: _("Pagata"),
            self.Status.PAYMENT_FAILED: _("Pagamento da ripetere"),
            self.Status.REJECTED: _("Rifiutata"),
            self.Status.CANCELLED: _("Annullata"),
        }
        return mapping.get(self.status, self.get_status_display())

    @property
    def admin_status_message(self):
        mapping = {
            self.Status.IN_APPROVAL: _("Questa richiesta richiede un tuo intervento: controlla i componenti, definisci il prezzo finale e poi approva o rifiuta."),
            self.Status.APPROVED: _("Preventivo inviato. Il cliente vede il prezzo finale e puo pagare."),
            self.Status.PAYMENT_PENDING: _("Il cliente ha gia iniziato il pagamento. Attendi l'esito finale o controlla lo storico."),
            self.Status.PAID: _("Pagamento confermato. La richiesta e conclusa dal lato economico."),
            self.Status.PAYMENT_FAILED: _("Il cliente non ha completato il pagamento. Puoi lasciare il preventivo attivo oppure aggiornarlo."),
            self.Status.REJECTED: _("La richiesta e stata rifiutata. Puoi comunque riaprirla se necessario."),
            self.Status.CANCELLED: _("La richiesta e stata annullata. Puoi riaprirla se serve una nuova valutazione."),
        }
        return mapping.get(self.status, "")

    @property
    def requires_admin_attention(self):
        return self.status in {self.Status.IN_APPROVAL, self.Status.PAYMENT_FAILED}

    @property
    def is_payment_available(self):
        return self.status in {self.Status.APPROVED, self.Status.PAYMENT_FAILED}

    def payments_queryset(self):
        return CustomBuildPayment.objects.filter(custom_request=self).order_by("-initiated_at")

    @property
    def latest_payment(self):
        return self.payments_queryset().first()

    @property
    def active_payment(self):
        return self.payments_queryset().filter(
            status__in=[CustomBuildPayment.Status.CREATED, CustomBuildPayment.Status.PENDING]
        ).first()

    @property
    def latest_payment_reference(self):
        payment = self.latest_payment
        return payment.reference_code if payment else _("Nessun pagamento")

    @property
    def origin_label(self):
        if self.request_origin == self.Origin.CATALOG_BUILD:
            return _("Build del catalogo")
        return _("Richiesta personalizzata")

    def component_items(self):
        items = []
        for field_name, label in self.COMPONENT_FIELDS:
            value = getattr(self, field_name, "")
            if value:
                items.append((label, value))
        if not items and self.requested_build_id and self.requested_build:
            items.append((_("Build richiesta"), self.requested_build.localized_name))
        return items

    def component_lines(self):
        return [f"{label}: {value}" for label, value in self.component_items()]

    def __str__(self):
        return f"{self.reference_code} - {self.user.email}"


class CustomBuildPayment(models.Model):
    class Provider(models.TextChoices):
        SIMULATED = "simulated", _("Simulato / sviluppo")
        PAYPAL = "paypal", _("PayPal Business")

    class CheckoutMethod(models.TextChoices):
        PAYPAL = "paypal", _("PayPal")
        MASTERCARD = "mastercard", _("Mastercard")
        VISA = "visa", _("Visa")
        AMEX = "amex", _("American Express")

    class Status(models.TextChoices):
        CREATED = "created", _("Creato")
        PENDING = "pending", _("In attesa")
        SUCCEEDED = "succeeded", _("Riuscito")
        FAILED = "failed", _("Fallito")
        CANCELLED = "cancelled", _("Annullato")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custom_build_payments",
    )
    custom_request = models.ForeignKey(
        CustomBuildRequest,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.SIMULATED)
    checkout_method = models.CharField(
        max_length=20,
        choices=CheckoutMethod.choices,
        default=CheckoutMethod.PAYPAL,
    )
    environment = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    external_order_id = models.CharField(max_length=120, blank=True)
    external_transaction_id = models.CharField(max_length=120, blank=True)
    admin_notes = models.TextField(blank=True)
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-initiated_at"]
        verbose_name = _("Pagamento build personalizzata")
        verbose_name_plural = _("Pagamenti build personalizzate")

    @property
    def reference_code(self):
        if not self.pk:
            return _("Nuovo pagamento")
        return f"PAY-{self.pk:06d}"

    @property
    def status_tone(self):
        mapping = {
            self.Status.CREATED: "warning",
            self.Status.PENDING: "info",
            self.Status.SUCCEEDED: "success",
            self.Status.FAILED: "danger",
            self.Status.CANCELLED: "warning",
        }
        return mapping.get(self.status, "info")

    @property
    def is_open(self):
        return self.status in {self.Status.CREATED, self.Status.PENDING}

    @property
    def provider_environment_display(self):
        if self.environment:
            return f"{self.get_provider_display()} / {self.environment}"
        return self.get_provider_display()

    @property
    def checkout_method_destination_label(self):
        if self.checkout_method == self.CheckoutMethod.PAYPAL:
            return _("In futuro aprira il checkout ufficiale PayPal Business.")
        return _("In futuro verra aperto il gateway carta corretto per il circuito selezionato.")

    @property
    def checkout_authorization_label(self):
        if self.checkout_method == self.CheckoutMethod.PAYPAL:
            return _("Autorizza con PayPal")
        return _("Autorizza pagamento con carta")

    @property
    def checkout_result_message(self):
        mapping = {
            self.Status.CREATED: _("Checkout creato ma non ancora avviato."),
            self.Status.PENDING: _("Checkout avviato. Attende la conferma finale del pagamento."),
            self.Status.SUCCEEDED: _("Pagamento registrato con successo."),
            self.Status.FAILED: _("Il tentativo di pagamento non e andato a buon fine."),
            self.Status.CANCELLED: _("Il tentativo di pagamento e stato annullato."),
        }
        return mapping.get(self.status, "")

    @property
    def completed_or_updated_at(self):
        return self.completed_at or self.updated_at

    def mark_pending(self):
        self.status = self.Status.PENDING
        self.save(update_fields=["status", "updated_at", "external_order_id", "environment"])

    def mark_succeeded(self, transaction_id=""):
        self.status = self.Status.SUCCEEDED
        self.external_transaction_id = transaction_id
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "external_transaction_id", "completed_at", "updated_at"])

    def mark_failed(self, admin_notes=""):
        self.status = self.Status.FAILED
        self.admin_notes = admin_notes
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "admin_notes", "completed_at", "updated_at"])

    def __str__(self):
        return f"{self.custom_request.reference_code} - {self.amount:.2f} {self.currency}"


class BuildPurchaseRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", _("Nuova")
        IN_PROGRESS = "in_progress", _("In gestione")
        READY = "ready", _("Pronta")
        CLOSED = "closed", _("Chiusa")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="build_purchase_requests",
    )
    custom_request = models.OneToOneField(
        CustomBuildRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_purchase_request",
    )
    build = models.ForeignKey(Build, on_delete=models.CASCADE, related_name="purchase_requests")
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Richiesta acquisto build")
        verbose_name_plural = _("Richieste acquisto build")

    def __str__(self):
        return f"{self.build.name} - {self.email}"
