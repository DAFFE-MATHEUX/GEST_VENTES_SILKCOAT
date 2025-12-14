from django.db import models
from django.contrib.auth.models import AbstractUser

# ============================
# TABLE : Utilisateur
# ============================
class Utilisateur(AbstractUser):
    ROLE_CHOICES = [
        ('Admin','Admin'),
        ('Gerante','Gerante'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    api_token = models.CharField(max_length=255, blank=True, null=True)
    photo_utilisateur = models.FileField(upload_to='Utilisateur/', blank=True, null=True)
    
    def __str__(self):
        return f'Role : {self.role}'
    
    
    