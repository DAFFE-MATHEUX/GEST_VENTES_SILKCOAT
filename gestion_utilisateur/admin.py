from django.contrib import admin

from gest_entreprise.models import Entreprise
from .models import Utilisateur
from django.contrib.auth.admin import UserAdmin

#===================================================================================================
""" 
admin.site.site_header = "GESTION DES VENTES ET STOCKS"
information_entreprise = Entreprise.objects.first()
admin.site.site_title = information_entreprise.nom_entrepriese.upper()
admin.site.index_title = str(f"GESTION COMPLETE DE {information_entreprise.nom_entrepriese.upper()}")

"""
#===================================================================================================


class Administrateur_GESTPRESENCE(UserAdmin):
	fieldsets = UserAdmin.fieldsets + (
     (
         None,{
             'fields':('photo_utilisateur','role', 'employe', 'api_token')
             }),
     )

admin.site.register(Utilisateur,Administrateur_GESTPRESENCE)