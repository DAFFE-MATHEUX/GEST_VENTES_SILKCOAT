from pathlib import Path
from .info import *
from django.contrib.messages import constants as messages

# ==================================================
# BASE COMMUNE
# ==================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ==================================================
# PARAMÈTRES PAR DÉFAUT (SURCHARGÉS EN DEV / PROD)
# ==================================================
DEBUG = False
ALLOWED_HOSTS = []

SECRET_KEY = None  # défini dans dev.py ou prod.py

# ==================================================
# APPLICATIONS
# ==================================================
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps métier
    'gestion_utilisateur',
    'gestion_audit',
    'gestion_notifications',
    'gestion_produits',
    'gest_entreprise',
    'gestion_rapports',
    'simple_history',

    # Auth
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'social_django',

    # API
    'rest_framework',
    'import_export',

    # Sécurité
    'axes',
]

SITE_ID = 1

# ==================================================
# MIDDLEWARE
# ==================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

# ==================================================
# URL / WSGI
# ==================================================
ROOT_URLCONF = 'gest_commerce.urls'
WSGI_APPLICATION = 'gest_commerce.wsgi.application'

# ==================================================
# TEMPLATES
# ==================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
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

# ==================================================
# AUTH
# ==================================================
AUTH_USER_MODEL = 'gestion_utilisateur.Utilisateur'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.facebook.FacebookOAuth2',
]

LOGIN_URL = 'gestionUtilisateur:connexion_utilisateur'
LOGOUT_REDIRECT_URL = 'gestionUtilisateur:tableau_bord'
LOGOUT_URL = '/'

# ==================================================
# MOTS DE PASSE
# ==================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'gestion_utilisateur.validators.StrongPasswordValidator'},
]

# ==================================================
# INTERNATIONALISATION
# ==================================================
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==================================================
# STATIC & MEDIA
# ==================================================
STATIC_URL = '/static/'
MEDIA_URL = '/media/'

# ==================================================
# HEADERS DE BASE
# ==================================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ==================================================
# DIVERS
# ==================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}
