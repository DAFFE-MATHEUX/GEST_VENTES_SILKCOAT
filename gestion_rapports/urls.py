
from django.urls import path
from .views import *
app_name = 'rapports'

urlpatterns = [
    # Listes des Rapports
    path('liste_rapports', liste_rapports, name='liste_rapports'),  
    # Generer les rapports de l'admin
    path('generer_rapport_admin/', generer_rapport_admin, name='generer_rapport_admin'),
    # Choix de la création du rapport de l'admin 
    path('creer_rapports_admin/', creer_rapport_admin, name='creer_rapport_admin'),
    # Générer les rapports de la Gerante
    path('generer_rapport/', generer_rapport, name='generer_rapport'),
    # Choix de la création des rapports de la Gérante
    path('creer_rapport/', creer_rapport, name='creer_rapport'),

    # Suppression des rapports
    path('suppression_rapport/', suppression_rapport, name='suppression_rapport'),
    
         
]
