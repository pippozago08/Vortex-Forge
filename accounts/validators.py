import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class StrongPasswordValidator:
    def validate(self, password, user=None):
        errors = []
        if len(password) < 10:
            errors.append(_("La password deve contenere almeno 10 caratteri."))
        if not re.search(r"[A-Za-z]", password):
            errors.append(_("La password deve contenere almeno una lettera."))
        if not re.search(r"\d", password):
            errors.append(_("La password deve contenere almeno un numero."))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _("Minimo 10 caratteri con almeno una lettera e un numero.")
