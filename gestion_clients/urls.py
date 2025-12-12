from django.contrib.auth import urls
from django.urls import path
from .views import *
urlpatterns = [
    path('client/listes_clients/', listes_clients, name='listes_clients'),
    path('client/nouveau_client/', nouveau_client, name='nouveau_client'),
    path('client/supprimer_client/', supprimer_client, name='supprimer_client'),
    
]
