
""" Admin configuration for the gestion_produits app.

from django.contrib import admin
from .models import (
    CategorieProduit, Produits, StockProduit,
    VenteProduit, LigneVente, Commandes, LivraisonsProduits
)

# ==========================
# CATEGORIE PRODUIT
# ==========================
@admin.register(CategorieProduit)
class AdminCategorie(admin.ModelAdmin):
    list_display = ('id', 'desgcategorie', 'date_maj')
    list_editable = ('desgcategorie',)
    search_fields = ('desgcategorie',)
    ordering = ('-date_maj',)

# ==========================
# PRODUITS
# ==========================
@admin.register(Produits)
class AdminProduits(admin.ModelAdmin):
    list_display = ('id', 'refprod', 'desgprod', 'pu', 'categorie', 'date_maj')
    list_editable = ('pu',)
    list_filter = ('categorie',)
    search_fields = ('refprod', 'desgprod')
    ordering = ('-date_maj',)

# ==========================
# STOCK PRODUIT
# ==========================

@admin.register(StockProduit)
class AdminStock(admin.ModelAdmin):
    list_display = (
        'produit',
        'lieu_stockage',
        'qtestock',
        'seuil',
        'date_maj'
    )

    list_editable = ('qtestock', 'seuil')

    list_filter = ('entrepot', 'magasin')
    search_fields = ('produit__refprod',)

    def lieu_stockage(self, obj):
        return obj.entrepot if obj.entrepot else obj.magasin

    lieu_stockage.short_description = "Lieu de stockage"


# ==========================
# VENTE PRODUIT
# ==========================
@admin.register(VenteProduit)
class AdminVenteProduit(admin.ModelAdmin):
    list_display = ('code', 'total', 'nom_complet_client', 'telclt_client', 'utilisateur', 'date_vente')
    search_fields = ('code', 'nom_complet_client', 'telclt_client')
    ordering = ('-date_vente',)

# ==========================
# LIGNE DE VENTE
# ==========================
@admin.register(LigneVente)
class AdminLigneVente(admin.ModelAdmin):
    list_display = ('vente', 'produit', 'quantite', 'prix', 'montant_reduction', 'sous_total')
    list_editable = ('quantite', 'prix', 'montant_reduction')

# ==========================
# COMMANDES
# ==========================
@admin.register(Commandes)
class AdminCommande(admin.ModelAdmin):
    list_display = ('numcmd', 'produits', 'qtecmd', 'statuts', 'datecmd')
    list_editable = ('statuts',)
    search_fields = ('numcmd', 'produits__desgprod')
    ordering = ('-datecmd',)

# ==========================
# LIVRAISONS
# ==========================
@admin.register(LivraisonsProduits)
class AdminLivraison(admin.ModelAdmin):
    list_display = ('numlivrer', 'commande', 'produits', 'qtelivrer', 'statuts', 'datelivrer')
    list_editable = ('qtelivrer', 'statuts')
    search_fields = ('numlivrer', 'produits__desgprod')
    ordering = ('-datelivrer',)

    """
    
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import (
    CategorieProduit, Produits, StockProduit,
    VenteProduit, LigneVente, Commandes, LivraisonsProduits
)

# ==========================
# CATEGORIE PRODUIT
# ==========================
@admin.register(CategorieProduit)
class AdminCategorie(SimpleHistoryAdmin):
    list_display = ('id', 'desgcategorie', 'date_maj')
    list_editable = ('desgcategorie',)
    search_fields = ('desgcategorie',)
    ordering = ('-date_maj',)

# ==========================
# PRODUITS
# ==========================
@admin.register(Produits)
class AdminProduits(SimpleHistoryAdmin):
    list_display = ('id', 'refprod', 'desgprod', 'pu', 'categorie', 'date_maj')
    list_editable = ('pu',)
    list_filter = ('categorie',)
    search_fields = ('refprod', 'desgprod')
    ordering = ('-date_maj',)

# ==========================
# STOCK PRODUIT
# ==========================
@admin.register(StockProduit)
class AdminStock(SimpleHistoryAdmin):
    list_display = ('produit', 'lieu_stockage', 'qtestock', 'seuil', 'date_maj')
    list_editable = ('qtestock', 'seuil')
    list_filter = ('entrepot', 'magasin')
    search_fields = ('produit__refprod',)

    def lieu_stockage(self, obj):
        return obj.entrepot if obj.entrepot else obj.magasin
    lieu_stockage.short_description = "Lieu de stockage"

# ==========================
# VENTE PRODUIT
# ==========================
@admin.register(VenteProduit)
class AdminVenteProduit(SimpleHistoryAdmin):
    list_display = ('code', 'total', 'nom_complet_client', 'telclt_client', 'utilisateur', 'date_vente')
    search_fields = ('code', 'nom_complet_client', 'telclt_client')
    ordering = ('-date_vente',)

# ==========================
# LIGNE DE VENTE
# ==========================
@admin.register(LigneVente)
class AdminLigneVente(SimpleHistoryAdmin):
    list_display = ('vente', 'produit', 'quantite', 'prix', 'montant_reduction', 'sous_total')
    list_editable = ('quantite', 'prix', 'montant_reduction')

# ==========================
# COMMANDES
# ==========================
@admin.register(Commandes)
class AdminCommande(SimpleHistoryAdmin):
    list_display = ('numcmd', 'produits', 'qtecmd', 'statuts', 'datecmd')
    list_editable = ('statuts',)
    search_fields = ('numcmd', 'produits__desgprod')
    ordering = ('-datecmd',)

# ==========================
# LIVRAISONS
# ==========================
@admin.register(LivraisonsProduits)
class AdminLivraison(SimpleHistoryAdmin):
    list_display = ('numlivrer', 'commande', 'produits', 'qtelivrer', 'statuts', 'datelivrer')
    list_editable = ('qtelivrer', 'statuts')
    search_fields = ('numlivrer', 'produits__desgprod')
    ordering = ('-datelivrer',)
