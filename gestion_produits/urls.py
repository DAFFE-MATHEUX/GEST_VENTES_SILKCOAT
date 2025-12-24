from django.urls import path
from .views import *
app_name = 'produits'

urlpatterns = [
    #=================================================================================================================================================
    # Gestion des produits
    #=================================================================================================================================================
    
    path('produits/listes_produits/', listes_produits, name='listes_produits'),
    path('produits/nouveau_produit/', nouveau_produit, name='nouveau_produit'),    
    path('produits/supprimer_produits/', supprimer_produits, name='supprimer_produits'),    
    path('produits/editer_produit/<int:id>/', editer_produit, name="editer_produit"),
    path('produits/modifier/<int:id>/', modifier_produit, name="modifier_produit"),
    path('produits/consulter_produit/<int:id>/', consulter_produit, name="consulter_produit"),

    #=================================================================================================================================================
    # Gestion des produits en Stocks
    #==================================================================================================================================================
    
    path('listes_produits_stock/', listes_produits_stock, name='listes_produits_stock'),
    path('filtrer_listes_produits_stock/', filtrer_listes_produits_stock, name='filtrer_listes_produits_stock'),
    path('ajouter_stock_multiple/', ajouter_stock_multiple, name='ajouter_stock_multiple'),  
    path('supprimer_produits_stock/', supprimer_produits_stock, name='supprimer_produits_stock'),
     
    #=================================================================================================================================================
    # Gestion des Ventes 
    #=================================================================================================================================================
    
    path('vente/listes_des_ventes/', listes_des_ventes, name='listes_des_ventes'),
    path('vente/filtrer_listes_ventes/', filtrer_listes_ventes, name='filtrer_listes_ventes'),
    path('vente/supprimer_ventes/', supprimer_ventes, name='supprimer_ventes'),
    path('vente/vendre_produit/', vendre_produit, name='vendre_produit'),
    path('vente/historique_ventes_par_date/', historique_ventes, name='historique_ventes_par_date'),
    path('vente/recu_vente_global/<str:vente_code>/', recu_vente_global, name='recu_vente_global'),
        
    #====================================================================================================================================================
    # Gestion des Commandes
    #====================================================================================================================================================

    path('commandes/listes_des_commandes/', listes_des_commandes, name='listes_des_commandes'),
    path('vente/filtrer_listes_commandes/', filtrer_listes_commandes, name='filtrer_listes_commandes'),
    path('commandes/nouvelle_commande/', nouvelle_commande, name='nouvelle_commande'),
    path('commandes/supprimer_commandes/', supprimer_commandes, name='supprimer_commandes'),
    #====================================================================================================================================================
    # Gestion des Livraisons 
    #====================================================================================================================================================

    path('livraions/reception_livraison/', reception_livraison, name='reception_livraison'),
    path('livraions/listes_des_livraisons/', listes_des_livraisons, name='listes_des_livraisons'),
    path('livraions/filtrer_listes_livraisons/', filtrer_listes_livraisons, name='filtrer_listes_livraisons'),
    path('supprimer_livraisons/', supprimer_livraisons, name='supprimer_livraisons'),
    path('historique_commandes_livraisons/', historique_commandes_livraisons, name='historique_commandes_livraisons'),
    
    #====================================================================================================================================================
    # Gestion des Approvisionnements
    #====================================================================================================================================================

    path('approv/approvisionner_produits/', approvisionner_produits, name='approvisionner_produits'),
    
    #=================================================================================================================================================
    # Gestion des catégories de produits
    #=================================================================================================================================================
    
    path('ajouter_categorie/', ajouter_categorie, name='ajouter_categorie'),
    path('supprimer_categorie/', supprimer_categorie, name='supprimer_categorie'), 
    path('listes_categorie/', listes_categorie, name='listes_categorie'), 
    path('modifier_categorie/', modifier_categorie, name='modifier_categorie'), 
    
    #=================================================================================================================================================
    # Impression listes
    #=================================================================================================================================================
    
    path('produits/listes_produits_impression/', listes_produits_impression, name="listes_produits_impression"),
    
    path('listes_categorie_produits_impression/', listes_categorie_produits_impression, name="listes_categorie_produits_impression"),
    
    path('commandes/listes_commandes_impression/', listes_commandes_impression, name="listes_commandes_impression"),
    path('commandes/choix_par_dates_commandes_impression/', choix_par_dates_commandes_impression, name="choix_par_dates_commandes_impression"),
    
    path('stocks/listes_stocks_impression/', listes_stocks_impression, name="listes_stocks_impression"),
    
    path('livraisons/listes_livraisons_impression/', listes_livraisons_impression, name="listes_livraisons_impression"),
    path('livraisons/choix_par_dates_livraisons_impression/', choix_par_dates_livraisons_impression, name="choix_par_dates_livraisons_impression"),
    
    path('ventes/choix_par_dates_ventes_impression/', choix_par_dates_ventes_impression, name="choix_par_dates_ventes_impression"),
    path('ventes/listes_ventes_impression/', listes_ventes_impression, name="listes_ventes_impression"),

    #=================================================================================================================================================
    # Exportation des données vers Excel 
    #=================================================================================================================================================
    path('confirmation_exportation_vente/', confirmation_exportation_vente, name='confirmation_exportation_vente'),
    path('confirmation_exportation_produits/', confirmation_exportation_produits, name='confirmation_exportation_produits'),
    path('confirmation_exportation_categorie/', confirmation_exportation_categorie, name='confirmation_exportation_categorie'),
    path('confirmation_exportation_livraison/', confirmation_exportation_livraison, name='confirmation_exportation_livraison'),
    path('confirmation_exportation_commande/', confirmation_exportation_commande, name='confirmation_exportation_commande'),
    
    
    path('export_ventes_excel/', export_ventes_excel, name='export_ventes_excel'),
    path('export_produits_excel/', export_produits_excel, name='export_produits_excel'),
    path('export_categories_excel/', export_categories_excel, name='export_categories_excel'),
    path('export_commandes_excel/', export_commandes_excel, name='export_commandes_excel'),
    path('export_livraisons_excel/', export_livraisons_excel, name='export_livraisons_excel'),
    
    #=================================================================================================================================================
    
]
