from .views import *
from django.urls import path

urlpatterns = [
    path('listes_des_fournisseurs/', listes_des_fournisseurs, name='listes_des_fournisseurs'),
    path('supprimer_fournisseur/', supprimer_fournisseur, name='supprimer_fournisseur'),
    path('modifier_fournisseur/', modifier_fournisseur, name='modifier_fournisseur'),
    path('ajouter_fournisseur/', ajouter_fournisseur, name='ajouter_fournisseur'),
    path('listes_fournisseurs_impression/', listes_fournisseurs_impression, name='listes_fournisseurs_impression'),
    
]
