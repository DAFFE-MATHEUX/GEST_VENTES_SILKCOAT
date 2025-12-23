from django.db import models
from gestion_utilisateur.models import Utilisateur
class Entreprise(models.Model):
    nom_entrepriese = models.CharField(max_length = 80)
    contact1 = models.CharField(max_length=30)
    contact2 = models.CharField(max_length=30)
    adresse = models.CharField(max_length=30)
    email = models.EmailField(null=True)
    logo = models.FileField(upload_to='Entreprise/', null=True, blank=True)
    date_maj = models.DateField(auto_now=True)
    
    def __str__(self):
        return f"Nom : {self.nom_entrepriese} Email : {self.email}"
    

class Entrepot(models.Model):
    nom_entrepot = models.CharField(max_length = 80)
    description = models.CharField(max_length=70)
    
    def __str__(self):
        return f"Nom : {self.nom_entrepot}"
    
class Magasin(models.Model):
    nom_magasin = models.CharField(max_length = 80)
    description = models.CharField(max_length=70)

    def __str__(self):
        return f"Nom : {self.nom_magasin}"
    

class Depenses(models.Model):
    date_operation = models.DateField(auto_now_add=True)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    designation = models.CharField(max_length=105)
    destine_a = models.CharField(max_length=45)
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.designation} ({self.date_operation})"

        
        