

from pathlib import Path
from pathlib import Path
from .info import *  # clés sensibles (EMAIL, SECRET_KEY...)
from django.contrib.messages import constants as messages
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
#SECRET_KEY = 'django-insecure-%=o3c3(8enkqm#0-(w*a^xx9p&oelo(@w^s(y^x7$g&q88sru^'

SECRET_KEY = SECRET_KEY

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# ==============================
# CRISPY FORM
# ==============================
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# ==============================
# MESSAGE TAGS
# ==============================
MESSAGE_TAGS = {
    messages.DEBUG: 'alert-secondary',
    messages.INFO: 'alert-info',
    messages.SUCCESS: 'alert-success',
    messages.WARNING: 'alert-warning',
    messages.ERROR: 'alert-danger'
}

# Application definition

INSTALLED_APPS = [
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'gestion_utilisateur',
    'gestion_audit',
    'gestion_notifications',
    'gestion_produits',
    'gest_entreprise',
    'gestion_rapports',
    
    # Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    # ⚠️ Provider Google → nécessite PyJWT (déjà corrigé)
    'allauth.socialaccount.providers.google',

    # ⚠️ Facebook → nécessite requests_oauthlib
    'allauth.socialaccount.providers.facebook',
    
    'social_django', # Pour l'authentification sociale
    
    # Librairies
    'rest_framework',
    #'import_export',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Correction : Obligatoire pour Django Allauth (nouvelle version)
    'allauth.account.middleware.AccountMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gest_commerce.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [ BASE_DIR / 'templates' ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'gestion_notifications.context_processors.notifications_context', 
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'gestion_notifications.context_processors.notifications_context',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'gest_commerce.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
"""
# ==============================
# BASE DE DONNÉES
# ==============================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'gest_commerce',
        'USER': 'root',
        'PASSWORD': '19014',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
"""


# ==============================
# EMAIL
# ==============================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = EMAIL_HOST
EMAIL_PORT = EMAIL_PORT
EMAIL_HOST_USER = EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = EMAIL_HOST_PASSWORD
EMAIL_USE_TLS = EMAIL_USE_TLS
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER



# ==============================
# AUTHENTIFICATION ALLAUTH
# ==============================
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.facebook.FacebookOAuth2',
]

# Site ID
SITE_ID = 1  # ⚠️ obligatoire pour Allauth


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ============================================================================

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# ======================================================================

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'gestion_utilisateur.Utilisateur'

# ==============================
# URL DE CONNEXION / DÉCONNEXION
# ==============================
LOGIN_URL = 'gestionUtilisateur:connexion_utilisateur'
LOGOUT_REDIRECT_URL = 'gestionUtilisateur:tableau_bord'
LOGOUT_URL = 'gestionUtilisateur:connexion_utilisateur'

# ==============================
# USER PERSONNALISÉ
# ==============================
AUTH_USER_MODEL = 'gestion_utilisateur.Utilisateur'
AUTH_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
ACCOUNT_SESSION_REMEMBER = True

