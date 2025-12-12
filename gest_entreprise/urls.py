from django.urls import path
from .views import *
urlpatterns = [
    
    path('liste_entreprise/', liste_entreprise, name='liste_entreprise'),
    path('nouvelle_saisie/', nouvelle_saisie, name='nouvelle_saisie'),
    path('modifier_entreprise/', modifier_entreprise, name='modifier_entreprise'),
    path('supprimer_entreprise/', supprimer_entreprise, name='supprimer_entreprise'),
    
]