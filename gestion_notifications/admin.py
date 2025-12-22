from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'titre', 'message','destinataire', 'lu', 'date')
    list_editable = ('lu',)
    search_fields = ('titre', 'message', 'destinataire')
    ordering = ('-date',)
