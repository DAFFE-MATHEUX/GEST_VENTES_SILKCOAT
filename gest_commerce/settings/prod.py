from .base import *
import environ

# ----------------------------------------
# ENVIRONNEMENT PROD
# ----------------------------------------
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')  # Lit le fichier .env

DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = [
    'itracopaint.com',
    'www.itracopaint.com',
]

# ----------------------------------------
# DATABASES PROD
# ----------------------------------------
DATABASES['default'].update({
    'NAME': env('DB_NAME_PROD'),
})

# ----------------------------------------
# HTTPS & SÉCURITÉ
# ----------------------------------------
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)

CSRF_TRUSTED_ORIGINS = [
    'https://itracopaint.com',
    'https://www.itracopaint.com',
]

SECURE_HSTS_SECONDS = 31536000  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ----------------------------------------
# EMAIL PROD
# ----------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
ADMIN_EMAIL = EMAIL_HOST_USER
EMAIL_FAIL_SILENTLY = False

# ----------------------------------------
# AXES (ANTI-BRUTE FORCE)
# ----------------------------------------
AXES_FAILURE_LIMIT = env.int('AXES_FAILURE_LIMIT', default=5)
AXES_LOCK_OUT_AT_FAILURE = env.bool('AXES_LOCK_OUT_AT_FAILURE', default=True)
AXES_COOLOFF_TIME = env.int('AXES_COOLOFF_TIME', default=1)  # heures
AXES_RESET_ON_SUCCESS = env.bool('AXES_RESET_ON_SUCCESS', default=True)

# ----------------------------------------
# LOGGING PROD
# ----------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'prod.log',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'WARNING',
    },
}
