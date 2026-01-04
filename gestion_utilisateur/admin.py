from django.contrib import admin
from gest_entreprise.models import Entreprise
from .models import Utilisateur
from django.contrib.auth.admin import UserAdmin
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# ==================================================
# ADMIN GLOBAL HEADER (STATIQUE)
# ==================================================
admin.site.site_header = "GESTION DES VENTES ET STOCKS"

# Valeurs par défaut avant que la DB soit prête
admin.site.site_title = "ENTREPRISE"
admin.site.index_title = "GESTION COMPLETE DE ENTREPRISE"

# ==================================================
# SIGNAL POST_MIGRATE : METTRE À JOUR LES TITRES DYNAMIQUEMENT
# ==================================================
@receiver(post_migrate)
def update_admin_titles(sender, **kwargs):
    try:
        entreprise = Entreprise.objects.first()
        if entreprise:
            nom_entreprise = entreprise.nom_entrepriese.upper()
        else:
            nom_entreprise = "ENTREPRISE"
        admin.site.site_title = nom_entreprise
        admin.site.index_title = f"GESTION COMPLETE DE {nom_entreprise}"
    except Exception:
        # Si la table n'existe pas encore
        admin.site.site_title = "ENTREPRISE"
        admin.site.index_title = "GESTION COMPLETE DE ENTREPRISE"

# ==================================================
# ADMIN POUR LE MODÈLE UTILISATEUR
# ==================================================
class Administrateur(UserAdmin):
    # Ajouter les champs personnalisés dans le formulaire admin
    fieldsets = UserAdmin.fieldsets + (
        (None, {
            'fields': ('photo_utilisateur', 'type_utilisateur', 'api_token', 'is_approved'),
        }),
    )

    # Champs à afficher dans la liste
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'type_utilisateur', 'is_staff', 'is_superuser', 
        'is_active', 'is_approved'
    )
    list_filter = (
        'is_staff', 'is_superuser', 'is_active', 
        'type_utilisateur', 'is_approved'
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

# ==================================================
# ENREGISTREMENT DU MODÈLE
# ==================================================
admin.site.register(Utilisateur, Administrateur)
