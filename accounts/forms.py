from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.validators import validate_uploaded_image


User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"placeholder": _("nome@azienda.it")}))
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"placeholder": _("Inserisci la password")}),
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"placeholder": _("Minimo 10 caratteri"), "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")
        labels = {
            "username": _("Nome utente"),
            "first_name": _("Nome"),
            "last_name": _("Cognome"),
            "email": _("Email"),
            "phone": _("Telefono"),
        }
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": _("Es. marco.rossi")}),
            "first_name": forms.TextInput(attrs={"placeholder": _("Nome")}),
            "last_name": forms.TextInput(attrs={"placeholder": _("Cognome")}),
            "email": forms.EmailInput(attrs={"placeholder": _("nome@azienda.it")}),
            "phone": forms.TextInput(attrs={"placeholder": _("Numero di telefono")}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("Esiste gia un account con questa email."))
        return email

    def clean_username(self):
        username = " ".join((self.cleaned_data["username"] or "").split()).strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(_("Esiste gia un account con questo nome utente."))
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        password_validation.validate_password(password)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        user.role = User.Role.USER
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "avatar")
        labels = {
            "first_name": _("Nome"),
            "last_name": _("Cognome"),
            "phone": _("Telefono"),
            "avatar": _("Immagine profilo"),
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": _("Nome")}),
            "last_name": forms.TextInput(attrs={"placeholder": _("Cognome")}),
            "phone": forms.TextInput(attrs={"placeholder": _("Numero di telefono")}),
            "avatar": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        validate_uploaded_image(avatar)
        return avatar


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label=_("Email account"), widget=forms.EmailInput(attrs={"placeholder": _("nome@azienda.it")}))


class PasswordResetVerifyForm(forms.Form):
    verification_code = forms.CharField(
        label=_("Codice di verifica"),
        max_length=6,
        widget=forms.TextInput(attrs={"placeholder": _("Inserisci il codice a 6 cifre")}),
    )

    def clean_verification_code(self):
        code = "".join((self.cleaned_data["verification_code"] or "").split())
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError(_("Inserisci il codice a 6 cifre ricevuto via email."))
        return code


class AccountDeletionVerifyForm(PasswordResetVerifyForm):
    pass


class PasswordResetCompleteForm(forms.Form):
    password1 = forms.CharField(
        label=_("Nuova password"),
        widget=forms.PasswordInput(attrs={"placeholder": _("Nuova password sicura")}),
    )
    password2 = forms.CharField(
        label=_("Conferma nuova password"),
        widget=forms.PasswordInput(attrs={"placeholder": _("Ripeti la nuova password")}),
    )

    def clean_password1(self):
        password = self.cleaned_data["password1"]
        password_validation.validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") and cleaned_data.get("password2") and cleaned_data.get("password1") != cleaned_data.get("password2"):
            self.add_error("password2", _("Le password non coincidono."))
        return cleaned_data
