from django.db import models

# Create your models here.
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
    
