from django.urls import path
from . import views

app_name = "audit"

urlpatterns = [
    # Listes des Audits
    path("liste_audit/", views.liste_audit, name="liste_audit"),
    # Suppression des Audits
    path("supprimer_audit/", views.supprimer_audit, name="supprimer_audit"),
]
