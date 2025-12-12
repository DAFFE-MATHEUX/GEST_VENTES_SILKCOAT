from django.shortcuts import render
from .models import Fournisseurs
from datetime import datetime
from django.template import TemplateDoesNotExist
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from gest_entreprise.models import Entreprise
from django.utils.timezone import now
from decimal import Decimal
import qrcode
from io import BytesIO
import base64
import openpyxl
from openpyxl.utils import get_column_letter
from gestion_clients.views import nouveau_client
from gestion_audit.views import enregistrer_audit
from django.utils import timezone
#================================================================================================
# Fonction pour afficher la liste de tout les fournisseurs
#================================================================================================

@login_required
def listes_des_fournisseurs(request):
    listes_fournisseur = []
    total_fournisseur = 0
    
    try:
        listes_fournisseur = Fournisseurs.objects.all().order_by('-id')
        total_fournisseur = listes_fournisseur.count()
    except Exception as ex :
        return messages.warning(request, f"Erreur de récupération des fournisseurs {str(ex)} !")
    context = {
        'listes_fournisseur' : listes_fournisseur,
        'total_fournisseur' : total_fournisseur
    }
    return render(request, "gestion_fournisseurs/listes_fournisseurs.html", context)

#===========================================================================================
# Fonction pour ajouter un nouveau fournisseur
#===========================================================================================
@login_required
def ajouter_fournisseur(request):
    if request.method == "POST":
        nom = request.POST.get("nomcomplets")
        adresse = request.POST.get("adressefour")
        tel = request.POST.get("telfour")
        email = request.POST.get("emailfour")

        try:
            Fournisseurs.objects.create(
                nomcomplets=nom,
                adressefour=adresse,
                telfour=tel,
                emailfour=email
            )
            messages.success(request, "Fournisseur ajouté avec succès !")
        except Exception as ex:
            messages.error(request, f"Erreur : {ex}")

        return redirect("listes_des_fournisseurs")

#===========================================================================================
# Fonction pour modifier les informations d'un fournisseur
#===========================================================================================
@login_required
def modifier_fournisseur(request):
    if request.method == "POST":
        id_modif = request.POST.get("id_modif")

        try:
            four = Fournisseurs.objects.get(id=id_modif)
            four.nomcomplets = request.POST.get("nom_modif")
            four.adressefour = request.POST.get("adresse_modif")
            four.telfour = request.POST.get("tel_modif")
            four.emailfour = request.POST.get("email_modif")
            four.save()

            messages.success(request, "Fournisseur modifié avec succès !")

        except Exception as ex:
            messages.error(request, f"Erreur : {ex}")

        return redirect("listes_des_fournisseurs")

#===========================================================================================
# Fonction pour supprimer un fournisseur
#===========================================================================================
@login_required
def supprimer_fournisseur(request):
    if request.method == "POST":
        id_supprime = request.POST.get("id_supprime")

        try:
            four = Fournisseurs.objects.get(id=id_supprime)
            four.delete()
            messages.success(request, "Fournisseur supprimé avec succès !")
        except Exception as ex:
            messages.error(request, f"Erreur lors de la suppression : {ex}")

        return redirect("listes_des_fournisseurs")


#================================================================================================
# Fonction pour imprimer la listes des fournisseurs
#================================================================================================

@login_required
def listes_fournisseurs_impression(request):
    listes_fournisseurs = Fournisseurs.objects.all()
    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_fournisseurs' : listes_fournisseurs,
    }
    return render(
        request,
        'gestion_fournisseurs/impression_listes/apercue_avant_impression_listes_fournisseurs.html',
        context
    )
    
#================================================================================================

