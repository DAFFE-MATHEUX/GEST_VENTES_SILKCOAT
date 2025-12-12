
from django.urls import path
from .views import *
app_name = 'rapports'

urlpatterns = [
    path('liste_rapports', liste_rapports, name='liste_rapports'),  
    path('generer_rapport/', generer_rapport, name='generer_rapport'),
    path('creer_rapport/', creer_rapport, name='creer_rapport'),
    path('suppression_rapport/', suppression_rapport, name='suppression_rapport'),
    
         
]
