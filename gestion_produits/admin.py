from django.contrib import admin
from gest_entreprise.models import Entreprise

from .models import *
# from .models import Order:
#from import_export.admin import ImportExportModelAdmin

# ====================================================================================

""" 
class AdminProduits(ImportExportModelAdmin): #class AdminProducts(admin.ModelAdmin):
    list_display = '__all__'
    search_fields = ('refprod','categorie', 'desgprod') # Permet une zone de recherche par categorie
    
    list_editable = ('refprod',) # Donner la possibilité de modifier dans la partie administration
    
    list_filter = (
        'refprod','categorie', 'date_inscription' , 'desgprod'
                   ) # Donner la possibilité de filtrer partie administration

class AdminLigneVente(ImportExportModelAdmin): #class AdminProducts(admin.ModelAdmin):
    list_display = '__all__'
    
    search_fields = ('vente','produit') # Permet une zone de recherche par designation
    
    list_editable = ('quantite',) # Donner la possibilité de modifier dans la partie administration
    
    list_filter = (
        'vente','produit',
                   ) # Donner la possibilité de filtrer partie administration

class AdminVenteProduit(ImportExportModelAdmin): #class AdminProducts(admin.ModelAdmin):
    list_display ='__all__'
    
    search_fields = ('code','date_vente', 'utilisateur') # Permet une zone de recherche
    
    list_editable = ('code',) # Donner la possibilité de modifier dans la partie administration
    
    list_filter = (
        'code','date_vente', 'utilisateur') # Donner la possibilité de filtrer partie administration
    

class AdminCategorie(ImportExportModelAdmin): #class AdminProducts(admin.ModelAdmin):
    list_display ='__all__'
    
    search_fields = ('desgcategorie','description') # Permet une zone de recherche
    
    list_editable = ('desgcategorie',) # Donner la possibilité de modifier dans la partie administration
    
    list_filter = (
        'desgcategorie','description',) # Donner la possibilité de filtrer partie administration

class AdminCommande(ImportExportModelAdmin): #class AdminProducts(admin.ModelAdmin):
    list_display ='__all__'
    
    search_fields = ('numcmd','produits') # Permet une zone de recherche
    
    list_editable = ('numcmd','produits', ) # Donner la possibilité de modifier dans la partie administration
    
    list_filter = (
        'numcmd','produits', 'datecmd',) # Donner la possibilité de filtrer partie administration

class AdminLivraisons(ImportExportModelAdmin): #class AdminProducts(admin.ModelAdmin):
    list_display ='__all__'
    
    search_fields = ('fournisseur','produits', 'datelivrer') # Permet une zone de recherche
    
    list_editable = ('numcmd','qtelivrer', ) # Donner la possibilité de modifier dans la partie administration
    
    list_filter = (
        'fournisseur','qtelivrer', 'produits', 'datelivrer') # Donner la possibilité de filtrer partie administration

"""  
# =========================================================================================
""" 
admin.register(Produits, AdminProduits)
admin.register(CategorieProduit, AdminCategorie)
admin.register(Commandes, AdminCommande)
admin.register(Livraisons, AdminLivraisons)
admin.register(VenteProduit, AdminVenteProduit)
admin.register(LigneVente, AdminLigneVente)

"""
# =========================================================================================
admin.register(Produits)
admin.register(VenteProduit)
admin.register(LigneVente)