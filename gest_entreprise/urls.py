from django.urls import path
from .views import *
urlpatterns = [
    
    path('liste_entreprise/', liste_entreprise, name='liste_entreprise'),
    path('nouvelle_saisie/', nouvelle_saisie, name='nouvelle_saisie'),
    path('modifier_entreprise/', modifier_entreprise, name='modifier_entreprise'),
    path('supprimer_entreprise/', supprimer_entreprise, name='supprimer_entreprise'),
    
    #=================================================================================================
    # Gestion des Dépenses
    #=================================================================================================

    path('liste_depense/', liste_depense, name="liste_depense"),
    path("nouvelle_depense/", nouvelle_depense, name="nouvelle_depense"),
    path("modifier_depense/", modifier_depense, name="modifier_depense"),
    path("supprimer_depense/", supprimer_depense, name="supprimer_depense"),
    path("filtrer_listes_depenses/", filtrer_listes_depenses, name="filtrer_listes_depenses"),

    #=================================================================================================
    path('recu_depense/<int:depense_id>/', recu_depense, name="recu_depense"),
    path('recu_depense_global_interval/', recu_depense_global_interval, name="recu_depense_global_interval"),
    
    #=================================================================================================
    # Gestion Exportation vers Excel
    #=================================================================================================

    #Fonction pour la confirmation exportation vers Excel
    path("modal_exportation_excel/", modal_exportation_excel, name="modal_exportation_excel"),

    #Fonction pour exporter tout les dépenses vers Excel
    path("export_depenses_excel/", export_depenses_excel, name="export_depenses_excel"),

    #=================================================================================================
    path("choix_listes_impression_depenses/", choix_listes_impression_depenses, name="choix_listes_impression_depenses"),
    path("liste_depenses_impression/", liste_depenses_impression, name="liste_depenses_impression"),
    
    #=================================================================================================

]