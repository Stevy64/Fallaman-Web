from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError

from .models import User
from .phone import normalize_phone


class PhoneModelBackend(ModelBackend):
    """Authentifie avec un numéro gabonais, même mal formaté (+241, 06…, espaces)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        raw = username or kwargs.get(User.USERNAME_FIELD)
        if not raw or password is None:
            return None
        try:
            phone = normalize_phone(raw)
        except ValidationError:
            return None
        try:
            user = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
