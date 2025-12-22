from .base import *
from .info import *
DEBUG = False
ALLOWED_HOSTS = ['monsite.com', 'www.monsite.com']

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
