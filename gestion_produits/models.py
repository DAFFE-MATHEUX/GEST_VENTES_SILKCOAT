from django.db import models
from gestion_utilisateur.models import Utilisateur
from simple_history.models import HistoricalRecords

#==================================================================================
# Table Categorie Produit
#==================================================================================

class CategorieProduit(models.Model):
    desgcategorie = models.CharField(max_length=65, unique=True)
    description = models.TextField(null = True, blank = True)
    date_maj = models.DateField(auto_now = True)
    history = HistoricalRecords() # Pour l'historique dans la partie administration de Django
    
    def __str__(self):
        return f"Catégorie : {self.desgcategorie}"
  
#==================================================================================
# Table Produits
#==================================================================================
    
class Produits(models.Model):
    refprod = models.CharField(max_length = 50)
    desgprod = models.TextField(null=True, blank = True)

    pu = models.IntegerField(default = 0)
    prix_en_gros = models.IntegerField(default = 0)  # Prix unitaire en gros
    photoprod = models.ImageField(upload_to = 'Produits/', null = True, blank = True)
    image_url = models.URLField(null=True, max_length=690, blank=True)
    date_maj = models.DateField(auto_now = True)
    categorie = models.ForeignKey(CategorieProduit, on_delete=models.CASCADE, related_name='produit')
    history = HistoricalRecords() # Pour l'historique dans la partie administration de Django
    
    class Meta:
        unique_together = ['refprod', 'categorie']
        
    def __str__(self):
        return f"Références : {self.refprod} Catégorie : {self.categorie}"

#==================================================================================
# Table Stock des Produits
#==================================================================================

class StockProduit(models.Model):
    produit = models.OneToOneField(
        Produits,
        on_delete=models.CASCADE,
        related_name='stocks'
    )

    qtestock = models.IntegerField(default=0)
    seuil = models.IntegerField(default=0)

    date_maj = models.DateTimeField(auto_now=True)
    history = HistoricalRecords() # Pour l'historique dans la partie administration de Django

    class Meta:
        verbose_name = "Stock Produit"
        verbose_name_plural = "Stocks Produits"
        constraints = [
            models.UniqueConstraint(
                fields=["produit"],
                name="unique_stock_produit"
            )
        ]

    def __str__(self):
        return f"{self.produit.refprod} | Stock: {self.qtestock}"

#==================================================================================
# Table Ventes des Produits
#==================================================================================
class VenteProduit(models.Model):
    code = models.CharField(max_length=20, unique=True)
    date_vente = models.DateTimeField(auto_now_add=True)
    total = models.IntegerField(default=0)
    benefice_total = models.IntegerField(default=0)
    
    nom_complet_client = models.CharField(max_length=70, null=True)
    adresseclt_client = models.CharField(max_length=60, null=True)
    telclt_client = models.CharField(max_length=65, null=True)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True)
    history = HistoricalRecords()  # Pour l'historique dans la partie administration de Django
    
    class Meta:
        ordering = ['-code']
    def __str__(self):
        return f"Vente {self.code} Par {self.utilisateur}"
    
    def calculer_totaux(self):
        self.total = sum(ligne.sous_total for ligne in self.lignes.all())
        self.benefice_total = sum(ligne.benefice for ligne in self.lignes.all())
        self.save(update_fields=['total', 'benefice_total'])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


#==================================================================================
# Table LigneVente
#==================================================================================
class LigneVente(models.Model):
    vente = models.ForeignKey(VenteProduit, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(Produits, on_delete=models.CASCADE, related_name='lignes')
    quantite = models.IntegerField(default=0)
    prix = models.IntegerField(default=0)  # Prix unitaire en details
    pu_reduction = models.IntegerField(default=0)  
    montant_reduction = models.IntegerField(default=0) 
    sous_total = models.IntegerField(default=0)
    benefice = models.IntegerField(default=0)
    date_saisie = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.produit.desgprod} (x{self.quantite})"

    def save(self, *args, **kwargs):
        self.pu_reduction = self.prix - self.montant_reduction
        # Calcul du sous-total
        self.sous_total = (self.prix - self.montant_reduction) * self.quantite 

        self.benefice = (self.pu_reduction - self.produit.prix_en_gros ) * self.quantite

        super().save(*args, **kwargs)
   
#==================================================================================
# Table Commandes
#==================================================================================
class Commandes(models.Model):
    numcmd = models.CharField(max_length = 60)
    qtecmd = models.IntegerField(default = 0)
    datecmd = models.DateField(auto_now_add = True)
    statuts = models.CharField(max_length=60, null=True, default="Non Livrer")
    produits = models.ForeignKey(Produits, on_delete = models.CASCADE)
    history = HistoricalRecords() # Pour l'historique dans la partie administration de Django
    # Information du Fournisseur
    nom_complet_fournisseur = models.CharField(max_length=70, null=True)
    adresse_fournisseur = models.CharField(max_length=60, null=True)
    telephone_fournisseur = models.CharField(max_length=60, null=True)
    
    def __str__(self):
        return f"Produits : {self.produits} | Quantite : {self.qtecmd}"
    
#==================================================================================
# Table Livraisons
#==================================================================================
class LivraisonsProduits(models.Model):
    numlivrer = models.CharField(max_length = 60, default=0)
    qtelivrer = models.IntegerField(default = 0)
    commande = models.ForeignKey(Commandes, on_delete = models.CASCADE, default=1)
    produits = models.ForeignKey(Produits, on_delete = models.CASCADE)
    datelivrer = models.DateField(auto_now_add = True)
    statuts = models.CharField(max_length=60, null=True)
    history = HistoricalRecords()  # Pour l'historique dans la partie administration de Django
    def __str__(self):
        return f"Produits : {self.produits} | Statuts : {self.statuts}"
    

#==================================================================================

    
    