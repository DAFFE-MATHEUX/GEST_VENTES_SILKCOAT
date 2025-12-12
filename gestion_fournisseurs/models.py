from django.db import models

# Create your models here.

class Fournisseurs(models.Model):
    nomfour = models.CharField(max_length = 40)
    prenomfour = models.CharField(max_length = 60)
    adressefour = models.CharField(max_length = 60)
    telfour = models.CharField(max_length = 25)
    emailfour = models.EmailField(max_length = 70, null=True)
    photofour = models.ImageField(upload_to = 'Fournisseurs/', null = True, blank = True)
    date_saisie = models.DateField(auto_now = True)
    
    class Meta:
        unique_together = ['nomfour', 'prenomfour']
        
    def __str__(self):
        return f"Noms : {self.nomfour} Prénom : {self.prenomfour}"