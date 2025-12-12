from django.shortcuts import render
from .models import Clients
from .utils import pagination_liste
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import uuid
from django.contrib import messages
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
