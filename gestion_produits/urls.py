from django.urls import path
from .views import *
app_name = 'produits'

urlpatterns = [
    #==========================================================================
    # Gestion des produits
    #==========================================================================
    
    path('listes_produits/', listes_produits, name='listes_produits'),
    path('nouveau_produit/', nouveau_produit, name='nouveau_produit'),    
    path('supprimer_produits/', supprimer_produits, name='supprimer_produits'),    
    path('produits/editer_produit/<int:id>/', editer_produit, name="editer_produit"),
    path('produits/modifier/<int:id>/', modifier_produit, name="modifier_produit"),
    path('produits/consulter_produit/<int:id>/', consulter_produit, name="consulter_produit"),

    
    #==========================================================================
    # Gestion des Ventes 
    #==========================================================================
    path('vente/listes_des_ventes/', listes_des_ventes, name='listes_des_ventes'),
    path('vente/filtrer_listes_ventes/', filtrer_listes_ventes, name='filtrer_listes_ventes'),
    path('vente/supprimer_ventes/', supprimer_ventes, name='supprimer_ventes'),
    path('vente/vendre_produit/', vendre_produit, name='vendre_produit'),
    path('vente/details_vente/<int:id>/', details_vente, name='details_vente'),
    path('vente/imprimer_ticket/<int:id>/ticket/', imprimer_ticket, name='imprimer_ticket'),
    path('vente/recu_vente_global/<str:vente_code>/', recu_vente_global, name='recu_vente_global'),
        
    #=============================================================================
    # Gestion des Commandes
    path('commandes/listes_des_commandes/', listes_des_commandes, name='listes_des_commandes'),
    path('commandes/nouvelle_commande/', nouvelle_commande, name='nouvelle_commande'),
    path('commandes/supprimer_commandes/', supprimer_commandes, name='supprimer_commandes'),
    
    #=============================================================================
    path('approv/approvisionner_produit/<int:id>/', approvisionner_produit, name='approvisionner_produit'),
    
    
    #==========================================================================
    # Gestion des catégories de produits
    #==========================================================================
    path('ajouter_categorie/', ajouter_categorie, name='ajouter_categorie'),
    path('supprimer_categorie/', supprimer_categorie, name='supprimer_categorie'), 
    path('listes_categorie/', listes_categorie, name='listes_categorie'), 
    path('modifier_categorie/', modifier_categorie, name='modifier_categorie'), 
    #==========================================================================
    # Impression 
    #==========================================================================
    
    path('produits/choix_par_dates_produit_impression/', choix_par_dates_produit_impression, name="choix_par_dates_produit_impression"),
    path('produits/listes_produits_impression/', listes_produits_impression, name="listes_produits_impression"),

    path('ventes/choix_par_dates_ventes_impression/', choix_par_dates_ventes_impression, name="choix_par_dates_ventes_impression"),
    path('ventes/listes_ventes_impression/', listes_ventes_impression, name="listes_ventes_impression"),

    #==========================================================================
    # Exportation des données vers Excel 
    #==========================================================================
    path('exportation_donnees_excel/', exportation_donnees_excel, name='exportation_donnees_excel'),
    path('export_ventes_excel/', export_ventes_excel, name='export_ventes_excel'),
]
