from django.db import models
from simple_history.models import HistoricalRecords
class Notification(models.Model):
    # 🔹 L'administrateur ou un utilisateur connecté
    destinataire = models.EmailField(
        null=True, blank=True,
        help_text="Utilisateur destinataire de la notification.")

    # 🔹 Email du parent (optionnel)
    destinataire_email = models.EmailField(
        null=True, blank=True,
        help_text="Email du client ou tuteur si non utilisateur."
    )

    titre = models.CharField(max_length=255, null=True)
    message = models.TextField()
    date = models.DateTimeField(auto_now_add=True, null=True)
    lu = models.BooleanField(default=False)
    history = HistoricalRecords()  # <-- historique activé
    
    def __str__(self):
        if self.destinataire:
            return f"{self.titre} → {self.destinataire}"
        elif self.destinataire_email:
            return f"{self.titre} → {self.destinataire_email}"
        return f"{self.titre} → Inconnu"

    @property
    def status_color(self):
        """Retourne une couleur selon l’état de lecture."""
        return 'success' if self.lu else 'danger'
