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

from django.db.models import Sum, Count, F, Q
from gest_entreprise.models import Entreprise
from datetime import datetime as dt

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

        date_debut = dt.strptime(periode_debut, "%Y-%m-%d") if periode_debut else None
        date_fin = dt.strptime(periode_fin, "%Y-%m-%d") if periode_fin else None

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
        total_par_categorie = []
        total_par_produit = []

        entreprise = Entreprise.objects.first()

        # ================= VENTES =================
        if type_rapport == "VENTES":
            data_qs = LigneVente.objects.select_related('vente', 'produit', 'produit__categorie').filter(
                date_saisie__range=[date_debut, date_fin]
            ).order_by('-id')

            total_montant = data_qs.aggregate(total=Sum('sous_total'))['total'] or 0
            total_vendus = data_qs.aggregate(total=Sum('quantite'))['total'] or 0

            # Total par catégorie
            total_par_categorie = (
                data_qs
                .values('produit__categorie__desgcategorie')
                .annotate(
                    total_montant=Sum('sous_total'),
                    total_quantite=Sum('quantite')
                )
                .order_by('produit__categorie__desgcategorie')
            )
                # Total par produit
            total_par_produit = (
                data_qs
                .values('produit__desgprod')
                .annotate(
                    total_quantite=Sum('quantite'),
                    total_montant=Sum('sous_total')
                )
                .order_by('produit__desgprod')
            )

            # Calcul bénéfice par ligne et total par vente
            ventes_dict = {}
            benefice_global = 0
            for ligne in data_qs:
                code_vente = ligne.vente.code
                if code_vente not in ventes_dict:
                    ventes_dict[code_vente] = {
                        'vente': ligne.vente,
                        'lignes': [],
                        'total_vente': 0,
                        'benefice_vente': 0
                    }

                benefice_ligne = ligne.benefice
                #ligne.benefice = benefice_ligne

                ventes_dict[code_vente]['lignes'].append(ligne)
                ventes_dict[code_vente]['total_vente'] += ligne.sous_total
                ventes_dict[code_vente]['benefice_vente'] += benefice_ligne

                benefice_global += benefice_ligne

            # Ajouter le stock actuel
            for ligne in data_qs:
                stock = getattr(ligne.produit.stocks, 'qtestock', 0)
                ligne.quantite = stock

            # Transformer en liste pour le contexte
            data_qs = list(ventes_dict.values())

        # ================= COMMANDES =================
        elif type_rapport == "COMMANDES":
            data_qs = Commandes.objects.select_related('produits', 'produits__categorie').filter(
                datecmd__range=[date_debut, date_fin]
            )
            total_montant = data_qs.aggregate(total=Sum('qtecmd'))['total'] or 0

            total_par_categorie = (
                data_qs
                .values('produits__categorie__desgcategorie')
                .annotate(
                    nombre_commandes=Count('id', distinct=True),
                    total_quantite=Sum('qtecmd'),
                    valeur_commandes=Sum(F('qtecmd') * F('produits__pu'))
                )
                .order_by('produits__categorie__desgcategorie')
            )

        # ================= LIVRAISONS =================
        elif type_rapport == "LIVRAISONS":
            data_qs = LivraisonsProduits.objects.select_related('produits', 'commande', 'produits__categorie').filter(
                datelivrer__range=[date_debut, date_fin]
            )
            total_montant = data_qs.aggregate(total=Sum('qtelivrer'))['total'] or 0

            total_par_categorie = (
                data_qs
                .values('produits__categorie__desgcategorie')
                .annotate(
                    nombre_livraisons=Count('id', distinct=True),
                    total_qtelivree=Sum('qtelivrer'),
                    valeur_livraison=Sum(F('qtelivrer') * F('produits__pu'))
                )
                .order_by('produits__categorie__desgcategorie')
            )

            total_par_produit = (
                data_qs
                .values('produits__categorie__desgcategorie', 'produits__refprod', 'produits__desgprod')
                .annotate(
                    nombre_livraisons=Count('id', distinct=True),
                    total_qtelivree=Sum('qtelivrer'),
                    valeur_livraison=Sum(F('qtelivrer') * F('produits__pu'))
                )
                .order_by('produits__categorie__desgcategorie', 'produits__refprod')
            )

            # Ajouter le stock actuel
            for item in data_qs:
                stock = getattr(item.produits.stocks, 'qtestock', 0)
                item.qtelivrer = stock

        # ================= STOCKS =================
        elif type_rapport == "STOCKS":
            data_qs = StockProduit.objects.select_related('produit', 'produit__categorie').order_by(
                'produit__categorie__desgcategorie', 'produit__desgprod'
            )
            total_montant = data_qs.aggregate(total=Sum('qtestock'))['total'] or 0

            total_par_categorie = (
                data_qs
                .values('produit__categorie__desgcategorie')
                .annotate(
                    quantite_stock=Sum('qtestock'),
                    valeur_stock=Sum(F('qtestock') * F('produit__pu'))
                )
                .order_by('produit__categorie__desgcategorie')
            )

        else:
            messages.error(request, "Type de rapport invalide.")
            return redirect("rapports:creer_rapport")

        # ================= GENERATION PDF =================
        context = {
            'rapport': rapport,
            'data': data_qs,
            'total_montant': total_montant,
            'entreprise': entreprise,
            'total_par_categorie': total_par_categorie,
            'total_par_produit': total_par_produit,
            'total_vendus' : total_vendus,
            'benefice_global' : benefice_global,
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
    """
    Supprime un rapport et enregistre l'action dans l'audit.
    """
    if request.method != "POST":
        messages.warning(request, "Méthode non autorisée pour la suppression.")
        return redirect('rapports:liste_rapports')
    
    id_supprimer = request.POST.get('id_supprimer')
    if not id_supprimer:
        messages.warning(request, "⚠️ Aucun rapport sélectionné pour suppression.")
        return redirect('rapports:liste_rapports')
    
    try:
        # Récupération du rapport à supprimer
        rapport = get_object_or_404(Rapport, id=id_supprimer)

        # --- Enregistrement de l'audit avant suppression ---
        ancienne_valeur = {
            "Titre": rapport.titre,
            "Période début": str(rapport.periode_debut),
            "Période fin": str(rapport.periode_fin),
            "Type": rapport.type,
            "Utilisateur connecté": request.user.get_full_name(),
            "Généré par": rapport.genere_par.username if rapport.genere_par else ""
        }

        # Ici on passe l'instance utilisateur, pas juste le nom
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




