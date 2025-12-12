
    
# models.py
from django.db import models
from gestion_utilisateur.models import Utilisateur

class AuditLog(models.Model):
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    table_modifiee = models.CharField(max_length=90)
    ancienne_valeur = models.TextField(blank=True, null=True)
    nouvelle_valeur = models.TextField(blank=True, null=True)
    date_action = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.utilisateur} - {self.action}"
    
    

