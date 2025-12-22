from django.db import models
from django.contrib.auth.models import AbstractUser
from simple_history.models import HistoricalRecords
# ============================
# TABLE : Utilisateur
# ============================
class Utilisateur(AbstractUser):
    ROLE_CHOICES = [
        ('Gerante','Gerante'),
    ]
    type_utilisateur = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True)
    api_token = models.CharField(max_length=255, blank=True, null=True)
    photo_utilisateur = models.FileField(upload_to='Utilisateur/', blank=True, null=True)
    history = HistoricalRecords()  # <-- Ajoute l'historique
    def __str__(self):
        return f'Role : {self.type_utilisateur}'
    
    
    