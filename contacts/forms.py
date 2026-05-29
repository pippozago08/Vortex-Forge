from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("name", "email", "phone", "subject", "message")
        labels = {
            "name": _("Nome"),
            "email": _("Email"),
            "phone": _("Telefono"),
            "subject": _("Oggetto"),
            "message": _("Messaggio"),
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Il tuo nome")}),
            "email": forms.EmailInput(attrs={"placeholder": _("nome@azienda.it")}),
            "phone": forms.TextInput(attrs={"placeholder": _("Telefono")}),
            "subject": forms.TextInput(attrs={"placeholder": _("Oggetto della richiesta")}),
            "message": forms.Textarea(attrs={"rows": 7, "placeholder": _("Spiega come possiamo aiutarti")}),
        }
