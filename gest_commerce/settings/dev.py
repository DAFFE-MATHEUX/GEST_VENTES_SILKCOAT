from .base import *
from .info import *

# ----------------------------------------
# Dev settings
# ----------------------------------------
# DEBUG = False # Pour masquer les erreur sur le navigateur
DEBUG = True # Pour afficher les erreur sur le navigateur

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Désactiver HTTPS et cookies sécurisés pour dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ----------------------------------------
# Base de données dev
# ----------------------------------------
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
