from django.db import models
from gestion_utilisateur.models import Utilisateur
from simple_history.models import HistoricalRecords
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
    

class Depenses(models.Model):
    date_operation = models.DateField(auto_now_add=True)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    designation = models.CharField(max_length=105)
    destine_a = models.CharField(max_length=45)
    history = HistoricalRecords()
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"Par {self.utilisateur.get_full_name()} {self.designation} ({self.date_operation})"

        
        