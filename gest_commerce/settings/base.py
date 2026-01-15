from pathlib import Path
import environ
from django.contrib.messages import constants as messages

# ----------------------------------------
# BASE DIR
# ----------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ----------------------------------------
# ENVIRONNEMENT
# ----------------------------------------
env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(BASE_DIR / '.env')  # Lit le fichier .env

# ----------------------------------------
# SECRET & DEBUG
# ----------------------------------------
SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)

# ----------------------------------------
# APPLICATIONS
# ----------------------------------------
INSTALLED_APPS = [
    # Django
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

    # Allauth
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',

    # Social auth
    'social_django',

    # API & outils
    'rest_framework',
    'import_export',

    # Sécurité brute force
    'axes',
]

SITE_ID = 1

# ----------------------------------------
# MIDDLEWARE
# ----------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

# ----------------------------------------
# URLS / TEMPLATES
# ----------------------------------------
ROOT_URLCONF = 'gest_commerce.urls'

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

WSGI_APPLICATION = 'gest_commerce.wsgi.application'

# ----------------------------------------
# AUTHENTIFICATION
# ----------------------------------------
AUTH_USER_MODEL = 'gestion_utilisateur.Utilisateur'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.facebook.FacebookOAuth2',
    'axes.backends.AxesStandaloneBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'gestion_utilisateur.validators.StrongPasswordValidator'},
]

LOGIN_URL = 'gestionUtilisateur:connexion_utilisateur'
LOGOUT_REDIRECT_URL = 'gestionUtilisateur:tableau_bord'
LOGOUT_URL = '/'

# ----------------------------------------
# AXES (BRUTE FORCE)
# ----------------------------------------
AXES_FAILURE_LIMIT = 5
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = 1

# ----------------------------------------
# INTERNATIONALISATION
# ----------------------------------------
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Conakry'
USE_I18N = True
USE_TZ = True

# ----------------------------------------
# STATIC & MEDIA
# ----------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ----------------------------------------
# LOGS SÉCURITÉ
# ----------------------------------------
LOGGING = {
    'version': 1,
    'handlers': {
        'security_file': {'class': 'logging.FileHandler', 'filename': BASE_DIR / 'security.log'},
    },
    'loggers': {
        'django.security': {'handlers': ['security_file'], 'level': 'WARNING', 'propagate': True},
    },
}

# ----------------------------------------
# DJANGO CORE
# ----------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ----------------------------------------
# SÉCURITÉ
# ----------------------------------------
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ----------------------------------------
# MESSAGE FRAMEWORK
# ----------------------------------------
MESSAGE_TAGS = {
    messages.DEBUG: 'debug',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# ----------------------------------------
# DATABASES
# ----------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
    }
}

# ----------------------------------------
# EMAIL
# ----------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
ADMIN_EMAIL = EMAIL_HOST_USER

# ----------------------------------------
# OAuth
# ----------------------------------------
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET')
SOCIAL_AUTH_FACEBOOK_KEY = env('SOCIAL_AUTH_FACEBOOK_KEY')
SOCIAL_AUTH_FACEBOOK_SECRET = env('SOCIAL_AUTH_FACEBOOK_SECRET')

SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'