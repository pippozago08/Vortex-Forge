from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get("email")
        if username is None or password is None:
            return None

        UserModel = get_user_model()
        user = UserModel.objects.filter(Q(email__iexact=username) | Q(username__iexact=username)).first()

        if user is not None and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
