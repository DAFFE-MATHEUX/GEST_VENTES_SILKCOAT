from .base import *
from .info import *
import os
from pathlib import Path

# ==================================================
# MODE PRODUCTION
# ==================================================
DEBUG = False

ALLOWED_HOSTS = [
    'monsite.com',
    'www.monsite.com',
]

# ==================================================
# CLÉ SECRÈTE (OBLIGATOIRE EN PROD)
# ==================================================
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

if not SECRET_KEY:
    raise Exception("DJANGO_SECRET_KEY non définie")

# ==================================================
# BASE DE DONNÉES PROD
# ==================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'gest_commerce',
        'USER': 'gest_user',
        'PASSWORD': DB_PASSWORD,
        'HOST': 'localhost',  # ou IP serveur MySQL
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        }
    }
}

# ==================================================
# HTTPS & COOKIES (CRITIQUE)
# ==================================================
SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# ==================================================
# HEADERS DE SÉCURITÉ
# ==================================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = 'DENY'
REFERRER_POLICY = 'same-origin'

# ==================================================
# HSTS (HTTPS RENFORCÉ)
# ⚠️ À activer seulement après HTTPS validé
# ==================================================
SECURE_HSTS_SECONDS = 31536000  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ==================================================
# CSRF PROTECTION AVANCÉE
# ==================================================
CSRF_TRUSTED_ORIGINS = [
    'https://monsite.com',
    'https://www.monsite.com',
]

# ==================================================
# DJANGO AXES (ANTI BRUTE FORCE)
# ==================================================
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = 1  # heure
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = None

# Middleware Axes obligatoire
MIDDLEWARE += [
    'axes.middleware.AxesMiddleware',
]

# ==================================================
# EMAIL PROD (ERREURS, ALERTES)
# ==================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = EMAIL_HOST
EMAIL_PORT = EMAIL_PORT
EMAIL_HOST_USER = EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = EMAIL_HOST_PASSWORD
EMAIL_USE_TLS = EMAIL_USE_TLS

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER
ADMINS = [('Admin', EMAIL_HOST_USER)]

# ==================================================
# LOGS DE SÉCURITÉ
# ==================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'security_file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'security.log',
            'level': 'ERROR',
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['security_file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'axes.watch_login': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
# ==================================================
# FIN DU FICHIER DE CONFIGURATION PROD
# ==================================================