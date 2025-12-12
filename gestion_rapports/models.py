from django.db import models
from gestion_utilisateur.models import Utilisateur
# Create your models here.
# ============================
# 9. TABLE : Rapports
# ============================
class Rapport(models.Model):
    TYPE_CHOICES = [
        ('Inscriptions','Inscriptions'),
        ('Réinscription','Réinscription'),
        ('Paiements','Paiements'),
        ('Personnel','Personnel')
    ]

    titre = models.CharField(max_length=150)
    periode_debut = models.DateField()
    periode_fin = models.DateField()
    type = models.CharField(max_length = 20, choices = TYPE_CHOICES)
    genere_par = models.ForeignKey(Utilisateur, on_delete = models.SET_NULL, null = True)
    date_generation = models.DateTimeField(auto_now_add = True)
    fichier_pdf = models.FileField(upload_to='rapports/', blank = True, null = True)

