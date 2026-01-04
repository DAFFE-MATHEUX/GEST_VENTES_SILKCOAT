from .base import *
from .info import *

# ==================================================
# MODE DÉVELOPPEMENT
# ==================================================
DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
]

# ==================================================
# CLÉ SECRÈTE DEV (DIFFÉRENTE DE PROD)
# ==================================================
SECRET_KEY = "dev-secret-key-unsafe-but-ok-for-dev"

# ==================================================
# HTTPS & COOKIES (DÉSACTIVÉS EN DEV)
# ==================================================
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

SESSION_COOKIE_HTTPONLY = False
CSRF_COOKIE_HTTPONLY = False

# ==================================================
# DÉSACTIVER LES BLOQUAGES DE SÉCURITÉ EN DEV
# ==================================================
AXES_ENABLED = False

# ==================================================
# BASE DE DONNÉES DEV
# ==================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'gest_commerce_dev',
        'USER': 'gest_user',
        'PASSWORD': DB_PASSWORD,
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        }
    }
}

# ==================================================
# EMAIL (CONSOLE EN DEV)
# ==================================================
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ==================================================
# LOGS (AFFICHAGE CONSOLE)
# ==================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
