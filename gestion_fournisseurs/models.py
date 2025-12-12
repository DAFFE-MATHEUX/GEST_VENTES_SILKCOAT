from django.db import models


class Fournisseurs(models.Model):
    nomcomplets = models.CharField(max_length = 40)
    adressefour = models.TextField()
    telfour = models.CharField(max_length = 25)
    emailfour = models.EmailField(max_length = 70, null=True)
    date_saisie = models.DateField(auto_now = True)
    
    class Meta:
        unique_together = ['nomcomplets', 'telfour']
        
    def __str__(self):
        return f"Nom Complet : {self.nomcomplets} Téléphone : {self.telfour}"