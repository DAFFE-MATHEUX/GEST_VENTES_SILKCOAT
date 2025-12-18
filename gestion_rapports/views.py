from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.template.loader import get_template, TemplateDoesNotExist
from django.http import HttpResponse
from weasyprint import HTML

from gestion_produits.models import Commandes, LigneVente, LivraisonsProduits, Produits, VenteProduit, StockProduit
from .models import Rapport
from .utils import pagination_lis, pagination_liste
from django.contrib.auth.decorators import login_required

from io import BytesIO
from django.core.files.base import ContentFile
from django.utils.text import slugify

from .models import Rapport
from gestion_audit.views import enregistrer_audit

from django.db.models import Sum
from gest_entreprise.models import Entreprise
from datetime import datetime as dt

from datetime import datetime as dt
from django.db.models import Sum
from django.template.loader import get_template
from django.http import HttpResponse
from django.utils.text import slugify
from django.core.files.base import ContentFile
from weasyprint import HTML
from io import BytesIO
# ========================================================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur') #Empecher tant que l'utilisateur n'est pas connecté
def liste_rapports(request):
    liste_rapports = Rapport.objects.select_related('genere_par').order_by('-date_generation')
    total_rapports = liste_rapports.count()
    liste_rapports = pagination_lis(request, liste_rapports)

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
        messages.warning(request, "Méthode non autorisée.")
        return redirect("rapports:creer_rapport")

    try:
        titre = request.POST.get("titre", "").strip()
        type_rapport = request.POST.get("type")
        periode_debut = request.POST.get("periode_debut")
        periode_fin = request.POST.get("periode_fin")

        if not titre or not type_rapport:
            messages.error(request, "Champs obligatoires manquants.")
            return redirect("rapports:creer_rapport")

        date_debut = date_fin = None
        if periode_debut and periode_fin:
            date_debut = dt.strptime(periode_debut, "%Y-%m-%d")
            date_fin = dt.strptime(periode_fin, "%Y-%m-%d")

        # Création du rapport
        rapport = Rapport.objects.create(
            titre=titre.upper(),
            periode_debut=date_debut,
            periode_fin=date_fin,
            type=type_rapport,
            genere_par=request.user
        )

        data_qs = []
        total_montant = 0

        # ================= VENTES =================
        if type_rapport == "VENTES":
            data_qs = (
                LigneVente.objects
                .select_related('vente', 'produit')
                .filter(vente__date_vente__range=[date_debut, date_fin])
                .order_by('-vente__date_vente')
            )
            total_montant = data_qs.aggregate(total=Sum('sous_total'))['total'] or 0

            # Récupérer le stock magasin actuel pour chaque produit vendu
            for ligne in data_qs:
                try:
                    stock = StockProduit.objects.filter(
                        produit=ligne.produit
                    ).order_by('-date_maj').first()
                    ligne.stock_magasin = stock.qtestock if stock else 0
                except StockProduit.DoesNotExist:
                    ligne.stock_magasin = 0

        # ================= COMMANDES =================
        elif type_rapport == "COMMANDES":
            data_qs = Commandes.objects.filter(datecmd__range=[date_debut, date_fin])
            total_montant = data_qs.aggregate(total=Sum('qtecmd'))['total'] or 0

        # ================= LIVRAISONS =================
        elif type_rapport == "LIVRAISONS":
            data_qs = (
                LivraisonsProduits.objects
                .select_related('produits', 'commande')
                .filter(datelivrer__range=[date_debut, date_fin])
                .order_by('-datelivrer')
            )
            total_montant = data_qs.aggregate(total=Sum('qtelivrer'))['total'] or 0

            # Récupérer le stock entrepôt actuel pour chaque produit livré
            for item in data_qs:
                try:
                    stock = StockProduit.objects.filter(
                        produit=item.produits
                    ).order_by('-date_maj').first()
                    item.stock_entrepot = stock.qtestock if stock else 0
                except StockProduit.DoesNotExist:
                    item.stock_entrepot = 0

        # ================= STOCKS =================
        elif type_rapport == "STOCKS":
            data_qs = (
                StockProduit.objects
                .select_related('produit', 'entrepot', 'magasin')
                .filter(date_maj__range=[date_debut, date_fin])
                .order_by('entrepot', 'magasin', 'produit__desgprod')
            )
            total_montant = data_qs.aggregate(total=Sum('qtestock'))['total'] or 0

        else:
            messages.error(request, "Type de rapport invalide.")
            return redirect("rapports:creer_rapport")

        # ================= CONTEXTE POUR PDF =================
        context = {
            'rapport': rapport,
            'data': data_qs,
            'total_montant': total_montant,
            'entreprise': Entreprise.objects.first(),
        }

        template = get_template('gestion_rapports/rapport_pdf.html')
        html = template.render(context)
        buffer = BytesIO()
        HTML(string=html).write_pdf(buffer)

        fichier = ContentFile(buffer.getvalue())
        filename = f"{slugify(titre)}.pdf"
        rapport.fichier_pdf.save(filename, fichier)

        response = HttpResponse(fichier, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        messages.success(request, "Rapport généré avec succès ✔")
        return response

    except Exception as e:
        messages.error(request, f"Erreur : {str(e)}")
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
            'utilisateur' : request.user.get_full_name,
            "Généré par": rapport.genere_par.username if rapport.genere_par else ""
        }
        enregistrer_audit(
            utilisateur = request.user.get_full_name,
            action = "Suppression",
            table="Rapport",
            ancienne_valeur = ancienne_valeur,
            nouvelle_valeur = None
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




