from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Rapport

@admin.register(Rapport)
class RapportAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'titre', 'genere_par', 'date_generation', 'periode_debut', 'periode_fin')
    search_fields = ('titre', 'genere_par', 'periode_debut', 'periode_fin')
    ordering = ('-date_generation',)
