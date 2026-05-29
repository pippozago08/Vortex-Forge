from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import BuildPurchaseRequest, CustomBuildPayment, CustomBuildRequest


class CustomBuildRequestForm(forms.ModelForm):
    component_fields = (
        "cpu",
        "gpu",
        "power_supply",
        "ram",
        "cooling",
        "storage",
        "case",
        "motherboard",
        "extra_fans",
        "network_card",
    )

    class Meta:
        model = CustomBuildRequest
        fields = (
            "cpu",
            "gpu",
            "power_supply",
            "ram",
            "cooling",
            "storage",
            "case",
            "motherboard",
            "extra_fans",
            "network_card",
            "budget_min",
            "budget_max",
            "currency",
            "notes",
        )
        labels = {
            "cpu": _("CPU (Processore)"),
            "gpu": _("GPU (Scheda video/grafica)"),
            "power_supply": _("Alimentatore"),
            "ram": _("RAM"),
            "cooling": _("Dissipatore (Ad aria o liquido)"),
            "storage": _("Archiviazione (Consigliato SSD o HDD)"),
            "case": _("Case"),
            "motherboard": _("Scheda madre"),
            "extra_fans": _("Ventole aggiuntive"),
            "network_card": _("Scheda di rete aggiuntiva 2.5 Gb +"),
            "budget_min": _("Budget minimo"),
            "budget_max": _("Budget massimo"),
            "currency": _("Valuta"),
            "notes": _("Come vorresti usare il PC e altre richieste"),
        }
        widgets = {
            "cpu": forms.TextInput(attrs={"placeholder": _("Es. Ryzen 7 9800X3D")}),
            "gpu": forms.TextInput(attrs={"placeholder": _("Es. RTX 5080")}),
            "power_supply": forms.TextInput(attrs={"placeholder": _("Es. 850W 80+ Gold")}),
            "ram": forms.TextInput(attrs={"placeholder": _("Es. 32 GB DDR5")}),
            "cooling": forms.TextInput(attrs={"placeholder": _("Es. Dissipatore ad aria dual tower o AIO 360 mm")}),
            "storage": forms.TextInput(attrs={"placeholder": _("Es. 2 TB SSD NVMe o 4 TB HDD")}),
            "case": forms.TextInput(attrs={"placeholder": _("Es. Mid Tower airflow")}),
            "motherboard": forms.TextInput(attrs={"placeholder": _("Es. B650 / X870 / Z890")}),
            "extra_fans": forms.TextInput(attrs={"placeholder": _("Es. 3x 140 mm PWM")}),
            "network_card": forms.TextInput(attrs={"placeholder": _("Es. 2.5 GbE o Wi-Fi 7")}),
            "budget_min": forms.NumberInput(attrs={"placeholder": "1500", "min": "0", "step": "0.01"}),
            "budget_max": forms.NumberInput(attrs={"placeholder": "2500", "min": "0", "step": "0.01"}),
            "currency": forms.Select(choices=[("EUR", "EUR - Euro")]),
            "notes": forms.Textarea(
                attrs={"rows": 6, "placeholder": _("Uso previsto, stile del case, silenziosita, RGB, monitor, streaming...")}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.component_fields:
            self.fields[field_name].required = False
        self.fields["budget_min"].required = False
        self.fields["currency"].initial = "EUR"
        self.fields["budget_min"].help_text = _("Facoltativo. Inseriscilo solo se vuoi indicare una fascia minima di partenza.")
        self.fields["budget_max"].help_text = _("Obbligatorio. E il limite massimo di spesa che il team dovra rispettare.")
        self.fields["currency"].help_text = _("Per ora tutte le richieste personalizzate vengono gestite in euro.")
        self.fields["notes"].help_text = _("Usa questo spazio per spiegare meglio come userai il PC e quali priorita hai.")

    def clean_budget_max(self):
        budget_max = self.cleaned_data["budget_max"]
        if budget_max is None:
            return budget_max
        if budget_max <= Decimal("0"):
            raise forms.ValidationError(_("Inserisci un budget massimo maggiore di zero."))
        return budget_max

    def clean(self):
        cleaned_data = super().clean()
        if any((cleaned_data.get(field_name) or "").strip() for field_name in self.component_fields):
            pass
        else:
            notes = (cleaned_data.get("notes") or "").strip()
            if not notes:
                raise forms.ValidationError(
                    _("Inserisci almeno un componente richiesto oppure spiega la configurazione desiderata nelle note.")
                )

        budget_min = cleaned_data.get("budget_min")
        budget_max = cleaned_data.get("budget_max")
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            self.add_error("budget_min", _("Il budget minimo non puo superare il budget massimo."))

        return cleaned_data


class BuildPurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = BuildPurchaseRequest
        fields = ("full_name", "email", "phone", "message")
        labels = {
            "full_name": _("Nome e cognome"),
            "email": _("Email"),
            "phone": _("Telefono"),
            "message": _("Messaggio"),
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": _("Nome e cognome")}),
            "email": forms.EmailInput(attrs={"placeholder": _("nome@azienda.it")}),
            "phone": forms.TextInput(attrs={"placeholder": _("Numero di telefono")}),
            "message": forms.Textarea(
                attrs={"rows": 5, "placeholder": _("Inserisci richieste, tempi o preferenze di contatto")}
            ),
        }


class CheckoutStartForm(forms.Form):
    checkout_method = forms.ChoiceField(
        label=_("Metodo di pagamento"),
        choices=CustomBuildPayment.CheckoutMethod.choices,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["checkout_method"].initial = CustomBuildPayment.CheckoutMethod.PAYPAL
        self.fields["checkout_method"].help_text = _(
            "Per ora il sito non addebita denaro reale: il metodo scelto serve a simulare il checkout che in futuro aprira la destinazione corretta."
        )


class SimulatedCheckoutConfirmForm(forms.Form):
    simulation_result = forms.ChoiceField(
        label=_("Scenario test"),
        choices=(
            ("success", _("Autorizzazione riuscita")),
            ("failure", _("Autorizzazione rifiutata")),
        ),
        widget=forms.Select,
    )
    confirm_checkout = forms.BooleanField(
        label=_("Confermo di voler completare questo checkout di test"),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["simulation_result"].initial = "success"
        self.fields["simulation_result"].help_text = _(
            "Nel checkout reale questa scelta non comparira: l'esito arrivera direttamente dal provider selezionato."
        )
        self.fields["confirm_checkout"].help_text = _(
            "Questa conferma serve solo in ambiente di sviluppo e non addebita denaro reale."
        )
