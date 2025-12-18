from django.db import models
from gestion_utilisateur.models import Utilisateur
from gest_entreprise.models import Entrepot, Magasin
#==================================================================================
# Table Categorie Produit
#==================================================================================

class CategorieProduit(models.Model):
    desgcategorie = models.CharField(max_length=65)
    description = models.TextField(null = True, blank = True)
    date_maj = models.DateField(auto_now = True)
    
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
    date_maj = models.DateField(auto_now = True)
    categorie = models.ForeignKey(CategorieProduit, on_delete=models.CASCADE, related_name='produit')
    
    class Meta:
        unique_together = ['refprod', 'categorie']
        
    def __str__(self):
        return f"Références : {self.refprod} Catégorie : {self.categorie}"

#==================================================================================
# Table Stock des Produits
#==================================================================================
class StockProduit(models.Model):
    produit = models.ForeignKey(
        Produits,
        on_delete=models.CASCADE,
        related_name='stocks'
    )

    entrepot = models.ForeignKey(
        Entrepot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stocks'
    )

    magasin = models.ForeignKey(
        Magasin,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stocks'
    )

    qtestock = models.IntegerField(default=0)
    seuil = models.IntegerField(default=0)

    date_maj = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(entrepot__isnull=False, magasin__isnull=True) |
                    models.Q(entrepot__isnull=True, magasin__isnull=False)
                ),
                name="stock_entrepot_ou_magasin"
            ),
            models.UniqueConstraint(
                fields=["produit", "entrepot", "magasin"],
                name="unique_stock_produit_lieu"
            )
        ]

    def __str__(self):
        lieu = self.entrepot or self.magasin
        return f"{self.produit.refprod} | {lieu}"

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

    class Meta:
        ordering = ['-code']
    def __str__(self):
        return f"Vente {self.code} Par {self.utilisateur}"
    
    def calculer_totaux(self):
        self.total = sum(ligne.sous_total for ligne in self.lignes.all())
        self.benefice_total = sum(ligne.benefice for ligne in self.lignes.all())
        self.save(update_fields=['total', 'benefice_total'])

#==================================================================================
# Table LigneVente
#==================================================================================
class LigneVente(models.Model):
    vente = models.ForeignKey(VenteProduit, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(Produits, on_delete=models.CASCADE, related_name='lignes')
    quantite = models.IntegerField(default=0)
    prix = models.IntegerField(default=0)  # Prix unitaire en details
    montant_reduction = models.IntegerField(default=0)  # Prix unitaire en details
    sous_total = models.IntegerField(default=0)
    benefice = models.IntegerField(default=0)
    date_saisie = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.produit.desgprod} (x{self.quantite})"

    def save(self, *args, **kwargs):
        # Calcul du sous-total
        self.sous_total = (self.prix * self.quantite) - self.montant_reduction

        # Calcul du bénéfice
        cout_total = self.produit.pu * self.quantite
        revenu_total = self.prix * self.quantite
        self.benefice = revenu_total - cout_total

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
    
    def __str__(self):
        return f"Produits : {self.produits} | Statuts : {self.statuts}"
    

#==================================================================================

    
    