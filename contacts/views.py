from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import FormView

from .forms import ContactMessageForm


class ContactView(FormView):
    template_name = "contacts/contact.html"
    form_class = ContactMessageForm
    success_url = reverse_lazy("contacts:contact")

    def get(self, request, *args, **kwargs):
        return redirect(f"{reverse_lazy('core:home')}#contacts-section")

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Messaggio inviato correttamente. Ti ricontatteremo al piu presto."))
        self.success_url = f"{reverse_lazy('core:home')}#contacts-section"
        return super().form_valid(form)
