# info.py
import environ
from pathlib import Path

# ----------------------------------------
# Initialisation django-environ
# ----------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env(
    DEBUG=(bool, False)
)

# Charger le fichier .env
environ.Env.read_env(BASE_DIR / '.env')

# ----------------------------------------
# SECRET KEY
# ----------------------------------------
SECRET_KEY = env('SECRET_KEY')

# ----------------------------------------
# DEBUG
# ----------------------------------------
DEBUG = env.bool('DEBUG')

# ----------------------------------------
# DATABASE
# ----------------------------------------
DB_NAME = env('DB_NAME')
DB_NAME_PROD = env('DB_NAME_PROD')
DB_USER = env('DB_USER')
DB_PASSWORD = env('DB_PASSWORD')
DB_HOST = env('DB_HOST')
DB_PORT = env('DB_PORT')

# ----------------------------------------
# EMAIL SMTP
# ----------------------------------------
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS')
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

# ----------------------------------------
# OAuth Google / Facebook
# ----------------------------------------
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', default='')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', default='')
SOCIAL_AUTH_FACEBOOK_KEY = env('SOCIAL_AUTH_FACEBOOK_KEY', default='')
SOCIAL_AUTH_FACEBOOK_SECRET = env('SOCIAL_AUTH_FACEBOOK_SECRET', default='')

# ----------------------------------------
# HTTPS / SÉCURITÉ (prod)
# ----------------------------------------
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)
