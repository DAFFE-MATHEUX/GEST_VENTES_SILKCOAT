from urllib import request
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Entreprise
from django.shortcuts import get_object_or_404, redirect, render

@login_required(login_url='gestionUtilisateur:connexion_utilisateur') #Empecher tant que l'utilisateur n'est pas connecté
def nouvelle_saisie(request, *args, **kwargs):
    template_name = "gestion_entreprise/listes_entreprise.html"
    # Vérification s'il existe déjà un établissement
    if Entreprise.objects.exists():
        messages.warning(request, "⚠️ Une entreprise de vente existe déjà. Vous ne pouvez pas en ajouter un autre.")
        return redirect('liste_entreprise') 

    if request.method == 'POST':
        nom_entrepriese = request.POST.get('nom_entrepriese')
        data = {
            'nom_entrepriese': nom_entrepriese,
            'email': request.POST.get('email'),
            'adresse': request.POST.get('adresse'),
            'contact1': request.POST.get('contact1'), 
            'contact2': request.POST.get('contact2'), 
            'logo': request.FILES.get('logo'),
        }

        try:
            Entreprise.objects.create(**data)
            messages.success(request, "L'entreprise a été ajouté avec succès.")
            return redirect('liste_entreprise')
        except Exception as ex:
            messages.error(request, f"❌ Erreur d'insertion de l'entreprise : {str(ex)}")
            return render(request, template_name, {'data': data})

    return render(request, template_name)

#==================================================================================================================
#Liste Etablissement Scolaire
#==================================================================================================================
def liste_entreprise(request, *args, **kwargs):
    liste_entreprise = Entreprise.objects.all().order_by('id')
    context = {
        'liste_entreprise' : liste_entreprise
    }
    return render(request, 'gestion_entreprise/listes_entreprise.html', context)

#==================================================================================================================
#Fonction pour supprimer un Entreprise
#==================================================================================================================
@login_required
def supprimer_entreprise(request):
    try:
        identifiant = request.POST.get('id_supprimer')
        etablissement = get_object_or_404(Entreprise, id=identifiant)
        etablissement.delete()
        messages.success(request, "Suppression effectuée avec succès !")
        return redirect('liste_etablissement')
    except Exception as ex:
        messages.error(request, f"Erreur de Suppression {ex}")
    return render(request, "gest_entreprise/listes_entreprise.html")
#==================================================================================================================
#Fonction Pour Modifier
#==================================================================================================================
@login_required
def modifier_entreprise(request):
    try:
            identifiant_etablissement = request.POST.get('identifiant_etablissement')
            entreprise = get_object_or_404(Entreprise, id=identifiant_etablissement)
            
            entreprise.nom_entrepriese = request.POST.get('nom_entrepriese')
            entreprise.email = request.POST.get('email')
            entreprise.adresse = request.POST.get('adresse')
            entreprise.contact2 = request.POST.get('contact1')
            entreprise.logo = request.POST.get('logo')
            entreprise.save()
            messages.success(request, "Modification effectuée avec succès ! ")
            return redirect('liste_etablissement')
    except Exception as ex:
            messages.warning(request, f"Erreur de Modiication des Informations {ex}")
    return render(request, "gestion_entreprise/liste_entreprise.html")

