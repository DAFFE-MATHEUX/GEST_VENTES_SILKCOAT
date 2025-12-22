from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(SimpleHistoryAdmin):
    list_display = ('id', 'action', 'utilisateur', 'date_action')
    search_fields = ('action', 'utilisateur__username')
    ordering = ('-date_action',)
