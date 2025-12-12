from django.db import models

# Create your models here.

class Clients(models.Model):
    nom_complet = models.CharField(max_length=60)
    adresseclt = models.CharField(max_length=60)
    telclt = models.CharField(max_length=25)
    date_saisie = models.DateField(auto_now=True)
    
    class Meta:
        unique_together = ['nom_complet', 'telclt']
        
    def __str__(self):
        return f"Noms Complet : {self.nom_complet} Téléphone : {self.telclt}"