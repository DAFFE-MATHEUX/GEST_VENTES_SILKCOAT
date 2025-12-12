from django.db import models
from gestion_fournisseurs.models import Fournisseurs
from gestion_clients.models import Clients 

#==================================================================================
# Classe Categorie Produit
#==================================================================================

class CategorieProduit(models.Model):
    desgcategorie = models.CharField(max_length=65)
    description = models.TextField(null = True, blank = True)
    date_maj = models.DateField(auto_now = True)
    
    def __str__(self):
        return f"Catégorie : {self.desgcategorie}"
  
#==================================================================================
# Classe Produits
#==================================================================================
    
class Produits(models.Model):
    refprod = models.CharField(max_length = 50)
    desgprod = models.TextField(null=True, blank = True)
    qtestock = models.IntegerField(default = 0)
    seuil = models.IntegerField(default = 0)
    pu = models.IntegerField(default = 0)
    photoprod = models.ImageField(upload_to = 'Produits/', null = True, blank = True)
    date_maj = models.DateField(auto_now = True)
    categorie = models.ForeignKey(CategorieProduit, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['refprod', 'categorie']
        
    def __str__(self):
        return f"Références : {self.refprod} Catégorie : {self.categorie}"
    
#==================================================================================
# Classe Commandes
#==================================================================================
    
class Commandes(models.Model):
    numcmd = models.CharField(max_length = 60)
    qtecmd = models.IntegerField(default = 0)
    datecmd = models.DateField(auto_now = True)
    produits = models.ForeignKey(Produits, on_delete = models.CASCADE)
    
    def __str__(self):
        return f"Quantite : {self.qtecmd}"
    
#==================================================================================
# Classe Livraisons
#==================================================================================

class Livraisons(models.Model):
    fournisseur = models.ForeignKey(Fournisseurs, on_delete = models.CASCADE)
    qtelivrer = models.IntegerField(default = 0)
    produits = models.ForeignKey(Produits, on_delete = models.CASCADE)
    datelivrer = models.DateField(auto_now = True)
    
    def __str__(self):
        return f"Fournisseur : {self.fournisseur} Produits : {self.produits}"
    
    
#==================================================================================
# Classe Ventes des Produits
#==================================================================================

class VenteProduit(models.Model):
    code = models.CharField(max_length=20, unique=True)
    date_vente = models.DateTimeField(auto_now_add=True)
    total = models.IntegerField(default=0)

    def __str__(self):
        return f"Vente {self.code}"


class LigneVente(models.Model):
    vente = models.ForeignKey(VenteProduit, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(Produits, on_delete=models.CASCADE, related_name='lignes')
    quantite = models.IntegerField(default=0)
    prix = models.IntegerField(default=0)  # Prix unitaire
    sous_total = models.IntegerField(default=0)
    
    nom_complet_client = models.CharField(max_length=60, null=True)
    adresseclt_client = models.CharField(max_length=60, null=True)
    telclt_client = models.CharField(max_length=25, null=True)
    date_saisie = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.produit.desgprod} (x{self.quantite})"

#==================================================================================

    
    