from cryptography.fernet import Fernet
from django.conf import settings


def _fernet():
    if not settings.API_CLIENT_ENC_KEY:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "API_CLIENT_ENC_KEY must be set to encrypt/decrypt ApiClient secrets."
        )
    return Fernet(settings.API_CLIENT_ENC_KEY.encode())


def encrypt_secret(raw):
    return _fernet().encrypt(raw.encode())


def decrypt_secret(token):
    return _fernet().decrypt(bytes(token)).decode()
