from django.shortcuts import redirect, render

from gestion_produits.models import LigneVente
from .models import Clients
from .utils import pagination_liste
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import uuid
from django.contrib import messages
from gestion_audit.views import enregistrer_audit

# Create your views here.


def nouveau_client(nomcomplet, telephone, adresse):
    Clients.objects.create(
        nom_complet = nomcomplet,
        telclt = telephone,
        adresseclt = adresse,
  
    )
    

def listes_clients(request):
    listes_clients = []
    total_clients = None
    try:
        listes_clients = Clients.objects.all().order_by('-id')
        total_clients = listes_clients.count()
        
        listes_clients = pagination_liste(request,listes_clients)
    except Exception as ex :
        return messages.warning(request, f"Erreur de récupération des clients {str(ex)} !")
    except ValueError as ve:
        return messages.warning(request, f"Erreur de valeur {str(ve)} !")
        
    context = {
        'listes_clients' : listes_clients,
        'total_clients' : total_clients
    }
    return render(request, "gestion_clients/listes_clients.html", context)

#================================================================================================
# Fonction pour supprimer un produit donné
#================================================================================================

@login_required
def supprimer_client(request):
    if request.method == 'POST':
        clt_id = request.POST.get('id_supprimer')

        try:
            client = Clients.objects.get(id=clt_id)

            # Vérifier si le client est lié à des ventes
            if LigneVente.objects.filter(
                produit = client.telclt
                ).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer ce client car il est déjà utilisé dans une vente. "
                    "Veuillez d'abord supprimer ses ventes associées."
                )
                return redirect('listes_clients')

            # ----- Ancienne valeur pour l'audit -----
            ancienne_valeur = {
                "id": client.id,
                "nomcomplet": client.nom_complet if hasattr(client, "nomcomplet") else "",
                "telct": client.telclt,
                "adresse": client.adresseclt,
            }

            # ----- Suppression -----
            client.delete()

            # ----- Audit -----
            enregistrer_audit(
                utilisateur = request.user,
                action="Suppression produit",
                table="Produits",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
            )

            messages.success(request, "Client supprimé avec succès !")

        except Clients.DoesNotExist:
            messages.error(request, "Client introuvable.")
        except Exception as ex:
            messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

        return redirect('produits:listes_produits')
