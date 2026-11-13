"""Activation links for new end-user accounts: signed, time-limited, and valid once."""
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing

SALT = "pms.activate"


def activation_token(user) -> str:
    return signing.dumps(user.pk, salt=SALT)


def user_for_token(token: str):
    """The inactive account a valid, unexpired token names, else None."""
    try:
        pk = signing.loads(token, salt=SALT,
                           max_age=settings.QMS_PMS_ACTIVATION_DAYS * 24 * 3600)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    return User.objects.filter(pk=pk, is_active=False).first()
