from django.contrib import admin
from .models import Entreprise, Depenses
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(Entreprise, SimpleHistoryAdmin)
admin.site.register(Depenses, SimpleHistoryAdmin)