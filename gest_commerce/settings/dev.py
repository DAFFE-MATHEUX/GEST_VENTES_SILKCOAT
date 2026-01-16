# gest_commerce/settings/dev.py

from .base import *
import environ

# ----------------------------------------
# Initialisation django-environ
# ----------------------------------------
env = environ.Env()
environ.Env.read_env()  # Charge le fichier .env

# ----------------------------------------
# DEV SETTINGS
# ----------------------------------------
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# ----------------------------------------
# SÉCURITÉ (DEV)
# ----------------------------------------
# Dev = HTTP simple, pas de SSL
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ----------------------------------------
# BASE DE DONNÉES (DEV)
# ----------------------------------------
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': env('DB_NAME', default='gest_commerce_dev'),
    'USER': env('DB_USER', default='gest_user'),
    'PASSWORD': env('DB_PASSWORD', default='matheux'),
    'HOST': env('DB_HOST', default='localhost'),
    'PORT': env('DB_PORT', default='3306'),
    'OPTIONS': {
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    },
}

# ----------------------------------------
# EMAIL (DEV)
# ----------------------------------------
# Affichage console pour dev
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'admin@localhost'
ADMIN_EMAIL = 'admin@localhost'

# ----------------------------------------
# LOGGING (DEV)
# ----------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}

# ----------------------------------------
# MIDDLEWARE
# ----------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    
    # Middleware requis par allauth
    'allauth.account.middleware.AccountMiddleware',
    
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]



SITE_ID = 1
