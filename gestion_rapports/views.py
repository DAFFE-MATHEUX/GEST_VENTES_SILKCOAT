from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.template.loader import get_template, TemplateDoesNotExist
from django.http import HttpResponse
from weasyprint import HTML

from gestion_produits.models import LigneVente, Produits, VenteProduit
from .models import Rapport
from .utils import pagination_liste
from django.contrib.auth.decorators import login_required

from io import BytesIO
from django.core.files.base import ContentFile
from django.utils.text import slugify

from .models import Rapport
from gestion_audit.views import enregistrer_audit

from django.db.models import Sum
from gest_entreprise.models import Entreprise
# ========================================================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur') #Empecher tant que l'utilisateur n'est pas connecté
def liste_rapports(request):
    liste_rapports = Rapport.objects.select_related('genere_par').order_by('-date_generation')
    total_rapports = liste_rapports.count()
    liste_rapports = pagination_liste(request, liste_rapports)

    context = {
        "liste_rapports": liste_rapports,
        'total_rapports': total_rapports,
        'nom_entreprise' : Entreprise.objects.first(),
    }
    return render(request, "gestion_rapports/listes_rapports.html", context)



#==================================================================================

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def creer_rapport(request):
    """Affiche le formulaire pour créer un rapport."""

    return render(request, "gestion_rapports/creer_rapport.html")

#==================================================================================

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def generer_rapport(request):
    if request.method != "POST":
        messages.warning(request, "Méthode non autorisée pour la génération de rapport.")
        return redirect("rapports:generer_rapport")

    try:
        titre = (request.POST.get("titre") or "").strip()
        periode_debut = request.POST.get("periode_debut")
        periode_fin = request.POST.get("periode_fin")
        type_rapport = request.POST.get("type")

        nom_entreprise = Entreprise.objects.first()

        if not (titre and type_rapport):
            messages.error(request, "Tous les champs obligatoires ne sont pas remplis.")
            return redirect("rapports:creer_rapport")

        # Création du rapport
        rapport = Rapport.objects.create(
            titre=titre,
            periode_debut=periode_debut,
            periode_fin=periode_fin,
            type=type_rapport,
            genere_par=request.user
        )

        data_qs = []
        total_montant = None
        total_reste = None

        if type_rapport == "Produits":
            data_qs = Produits.objects.all()

        elif type_rapport == "Ventes":
            data_qs = VenteProduit.objects.filter(
                date_vente__range=[periode_debut, periode_fin]
            )
            total_montant = data_qs.aggregate(total=Sum('total'))['total'] or 0

        elif type_rapport == "Commandes":
            data_qs = LigneVente.objects.filter(
                vente__date_vente__range=[periode_debut, periode_fin]
            )
            total_montant = data_qs.aggregate(total=Sum('sous_total'))['total'] or 0

        else:
            messages.error(request, "Type de rapport invalide.")
            return redirect("rapports:creer_rapport")

        # Contexte pour le template PDF
        context = {
            'rapport': rapport,
            'data': data_qs,
            'total_montant': total_montant,
            'total_reste': total_reste,
            'entreprise': nom_entreprise,
        }

        # Génération du PDF
        template = get_template('gestion_rapports/rapport_pdf.html')
        html_content = template.render(context, request)

        buffer = BytesIO()
        HTML(string=html_content, base_url=request.build_absolute_uri()).write_pdf(buffer)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        filename = f"{slugify(titre)}.pdf"
        rapport.fichier_pdf.save(filename, ContentFile(pdf_bytes))
        rapport.save()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        messages.success(request, f"Rapport '{type_rapport}' généré avec succès.")
        return response

    except Exception as exc:
        messages.error(request, f"Erreur inattendue : {str(exc)}")
        return redirect("rapports:creer_rapport")

#==================================================================================

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def suppression_rapport(request):
    if request.method != "POST":
        messages.warning(request, "Méthode non autorisée pour la suppression.")
        return redirect('rapports:liste_rapports')
    
    id_supprimer = request.POST.get('id_supprimer')
    if not id_supprimer:
        messages.warning(request, "⚠️ Aucun rapport sélectionné pour suppression.")
        return redirect('rapports:liste_rapports')
    
    try:
        rapport = get_object_or_404(Rapport, id=id_supprimer)

        # --- Enregistrement de l'audit avant suppression ---
        ancienne_valeur = {
            "Titre": rapport.titre,
            "Période début": str(rapport.periode_debut),
            "Période fin": str(rapport.periode_fin),
            "Type": rapport.type,
            "Généré par": rapport.genere_par.username if rapport.genere_par else ""
        }
        enregistrer_audit(
            utilisateur=request.user,
            action="Suppression",
            table="Rapport",
            ancienne_valeur=ancienne_valeur,
            nouvelle_valeur=None
        )

        # --- Suppression effective ---
        rapport.delete()
        messages.success(request, "✅ Rapport supprimé avec succès et audit enregistré.")

    except Rapport.DoesNotExist:
        messages.error(request, "❌ Rapport non trouvé.")
    except Exception as ex:
        messages.error(request, f"⚠️ Erreur lors de la suppression : {str(ex)}")

    return redirect('rapports:liste_rapports')

#=============================================================================================




