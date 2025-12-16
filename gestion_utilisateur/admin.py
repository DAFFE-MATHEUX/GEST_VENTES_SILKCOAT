from django.contrib import admin

from gest_entreprise.models import Entreprise
from .models import Utilisateur
from django.contrib.auth.admin import UserAdmin

#===================================================================================================
 
from django.contrib import admin
from gest_entreprise.models import Entreprise

# Définir le header et index_title via une fonction plutôt qu'une requête directe
admin.site.site_header = "GESTION DES VENTES ET STOCKS"

def get_entreprise_nom():
    try:
        entreprise = Entreprise.objects.first()
        if entreprise:
            return entreprise.nom_entrepriese.upper()
        return "ENTREPRISE"
    except Exception:
        # La table n'existe pas encore (pendant les migrations)
        return "ENTREPRISE"

nom_entreprise = get_entreprise_nom()
admin.site.site_title = nom_entreprise
admin.site.index_title = f"GESTION COMPLETE DE {nom_entreprise}"


#===================================================================================================


class Administrateur_VENTE(UserAdmin):
	fieldsets = UserAdmin.fieldsets + (
     (
         None,{
             'fields':('photo_utilisateur','type_utilisateur', 'api_token')
             }),
     )

admin.site.register(Utilisateur,Administrateur_VENTE)