from django.urls import path
from . import views

app_name = "audit"

urlpatterns = [
    path("liste_audit/", views.liste_audit, name="liste_audit"),
    path("supprimer_audit/", views.supprimer_audit, name="supprimer_audit"),
]
