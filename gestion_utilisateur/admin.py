from django.contrib import admin
from .models import Utilisateur
from django.contrib.auth.admin import UserAdmin


# Register your models here.

class Administrateur_GESTPRESENCE(UserAdmin):
	fieldsets = UserAdmin.fieldsets + (
     (
         None,{
             'fields':('photo_utilisateur','role', 'employe', 'api_token')
             }),
     )

admin.site.register(Utilisateur,Administrateur_GESTPRESENCE)