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
from gest_entreprise.models import Depenses, Entreprise
from datetime import datetime as dt

from django.template.loader import get_template
from django.http import HttpResponse
from django.utils.text import slugify
from django.core.files.base import ContentFile
from weasyprint import HTML
from io import BytesIO
# ========================================================================
from django.contrib.auth.decorators import login_required

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def liste_rapports(request):
    # Vérifie le type d'utilisateur
    if request.user.type_utilisateur == "Gerante":
        # La gérante ne voit que ses propres rapports
        liste_rapports = Rapport.objects.select_related('genere_par').filter(
            genere_par=request.user
        ).order_by('-date_generation')
    else:
        # L'admin voit tous les rapports
        liste_rapports = Rapport.objects.select_related('genere_par').order_by('-date_generation')

    total_rapports = liste_rapports.count()
    liste_rapports = pagination_lis(request, liste_rapports)

    context = {
        "liste_rapports": liste_rapports,
        'total_rapports': total_rapports,
        'nom_entreprise': Entreprise.objects.first(),
    }
    return render(request, "gestion_rapports/listes_rapports.html", context)


#==================================================================================

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def creer_rapport_admin(request):
    """Affiche le formulaire pour créer un rapport."""

    return render(request, "gestion_rapports/creer_rapport_admin.html")

#==================================================================================
# Fonction pour générer les rapports de l'administrateur
#==================================================================================

from django.template.loader import get_template
from django.utils.text import slugify
from datetime import datetime as dt
from decimal import Decimal

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def generer_rapport_admin(request):
    if request.method != "POST":
        messages.warning(request, "Méthode non autorisée.")
        return redirect("rapports:creer_rapport_admin")

    try:
        # ================= Récupération des données =================
        titre = request.POST.get("titre", "").strip()
        type_rapport = request.POST.get("type")
        periode_debut = request.POST.get("periode_debut")
        periode_fin = request.POST.get("periode_fin")

        if not titre or not type_rapport:
            messages.error(request, "Champs obligatoires manquants.")
            return redirect("rapports:creer_rapport_admin")

        date_debut = dt.strptime(periode_debut, "%Y-%m-%d") if periode_debut else None
        date_fin = dt.strptime(periode_fin, "%Y-%m-%d") if periode_fin else None

        rapport = Rapport.objects.create(
            titre=titre.upper(),
            periode_debut=date_debut,
            periode_fin=date_fin,
            type=type_rapport,
            genere_par=request.user
        )

        # ================= Variables =================
        data_qs = []
        total_montant = 0
        total_vendus = 0
        total_quantite = 0
        benefice_global = Decimal(0)
        depenses_total = Decimal(0)
        benefice_net = Decimal(0)
        total_quantite_cmd = 0
        total_quantite_livrer = 0
        total_quantite_restante = 0
        total_par_categorie = []
        total_par_produit = []
        entreprise = Entreprise.objects.first()

        # ================= VENTES =================
        if type_rapport == "VENTES":
            lignes = LigneVente.objects.select_related(
                'vente', 'produit', 'produit__categorie'
            ).filter(
                date_saisie__range=[date_debut, date_fin]
            )

            total_montant = lignes.aggregate(total=Sum('sous_total'))['total'] or 0
            total_vendus = lignes.aggregate(total=Sum('quantite'))['total'] or 0

            total_par_categorie = lignes.values(
                'produit__categorie__desgcategorie'
            ).annotate(
                total_montant=Sum('sous_total'),
                total_quantite=Sum('quantite')
            )

            total_par_produit = lignes.values(
                'produit__desgprod'
            ).annotate(
                total_quantite=Sum('quantite'),
                total_montant=Sum('sous_total')
            )

            # Construire dictionnaire ventes et calcul bénéfice brut
            ventes_dict = {}
            for ligne in lignes:
                code = ligne.vente.code
                ventes_dict.setdefault(code, {
                    'vente': ligne.vente,
                    'lignes': [],
                    'total_vente': 0,
                    'benefice_vente': 0
                })
                ventes_dict[code]['lignes'].append(ligne)
                ventes_dict[code]['total_vente'] += ligne.sous_total
                ventes_dict[code]['benefice_vente'] += ligne.benefice
                benefice_global += ligne.benefice

            data_qs = list(ventes_dict.values())

            # ================= Dépenses =================
            depenses_total = Depenses.objects.all().aggregate(total=Sum('montant'))['total'] or Decimal(0)

            # Bénéfice net
            benefice_net = benefice_global - depenses_total

        # ================= COMMANDES =================
        elif type_rapport == "COMMANDES":
            data_qs = Commandes.objects.select_related(
                'produits', 'produits__categorie'
            ).filter(datecmd__range=[date_debut, date_fin])

            total_quantite = data_qs.aggregate(total=Sum('qtecmd'))['total'] or 0
            total_quantite_cmd = total_quantite

            total_par_categorie = data_qs.values(
                'produits__categorie__desgcategorie'
            ).annotate(
                total_quantite=Sum('qtecmd'),
                nombre_commandes=Count('id', distinct=True),
                valeur=Sum(F('qtecmd') * F('produits__pu'))
            )

            total_par_produit = data_qs.values(
                'produits__desgprod',
                'produits__categorie__desgcategorie'
            ).annotate(
                nombre_commandes=Count('id', distinct=True),
                total_quantite=Sum('qtecmd'),
                valeur=Sum(F('qtecmd') * F('produits__pu'))
            )

        # ================= LIVRAISONS =================
        elif type_rapport == "LIVRAISONS":
            data_qs = LivraisonsProduits.objects.select_related(
                'produits', 'commande', 'produits__categorie'
            ).filter(datelivrer__range=[date_debut, date_fin])

            total_quantite = data_qs.aggregate(total=Sum('qtelivrer'))['total'] or 0
            total_quantite_livrer = total_quantite
            total_quantite_restante = data_qs.aggregate(
                total=Sum(F('commande__qtecmd') - F('qtelivrer'))
            )['total'] or 0

            total_par_categorie = data_qs.values(
                'produits__categorie__desgcategorie'
            ).annotate(
                nombre_livraison=Count('id', distinct=True),
                total_qtelivree=Sum('qtelivrer'),
                total_cmd=Sum('commande__qtecmd'),
                reste=F('total_cmd') - F('total_qtelivree')
            )

            total_par_produit = data_qs.values(
                'produits__desgprod',
                'produits__categorie__desgcategorie'
            ).annotate(
                nombre_livraison=Count('id', distinct=True),
                total_qtelivree=Sum('qtelivrer'),
                total_cmd=Sum('commande__qtecmd'),
                reste=F('total_cmd') - F('total_qtelivree')
            )

        else:
            messages.error(request, "Type de rapport invalide.")
            return redirect("rapports:creer_rapports_admin")

        # ================= Génération PDF =================
        context = {
            'rapport': rapport,
            'data': data_qs,
            'entreprise': entreprise,
            'total_montant': total_montant,
            'total_vendus': total_vendus,
            'total_quantite': total_quantite,
            'benefice_global': benefice_global,
            'depenses_total': depenses_total,
            'benefice_net': benefice_net,
            'total_par_categorie': total_par_categorie,
            'total_par_produit': total_par_produit,
            'total_quantite_cmd': total_quantite_cmd,
            'total_quantite_livrer': total_quantite_livrer,
            'total_quantite_restante': total_quantite_restante,
        }

        html = get_template('gestion_rapports/rapport_admin_pdf.html').render(context)
        buffer = BytesIO()
        HTML(string=html).write_pdf(buffer)

        rapport.fichier_pdf.save(
            f"{slugify(titre)}.pdf",
            ContentFile(buffer.getvalue())
        )

        messages.success(request, "Rapport généré avec succès ✔")
        return HttpResponse(buffer.getvalue(), content_type="application/pdf")

    except Exception as e:
        messages.error(request, f"Erreur : {e}")
        return redirect("rapports:creer_rapport_admin")
#=================================================================================================
# Une Fonction qui permet de gérer les rapport de la Gerante
#=================================================================================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def creer_rapport(request):
    """Affiche le formulaire pour créer un rapport."""

    return render(request, "gestion_rapports/creer_rapport.html")

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

        rapport = Rapport.objects.create(
            titre=titre.upper(),
            periode_debut=date_debut,
            periode_fin=date_fin,
            type=type_rapport,
            genere_par=request.user
        )

        # ================= VARIABLES =================
        data_qs = []
        total_montant = 0
        total_vendus = 0
        total_quantite = 0
        total_quantite_cmd = 0
        total_quantite_livrer = 0
        total_quantite_restante = 0
        total_par_categorie = []
        total_par_produit = []
        entreprise = Entreprise.objects.first()

        # ================= VENTES =================
        if type_rapport == "VENTES":
            lignes = LigneVente.objects.select_related(
                'vente', 'produit', 'produit__categorie'
            ).filter(
                date_saisie__range=[date_debut, date_fin]
            )

            total_montant = lignes.aggregate(total=Sum('sous_total'))['total'] or 0
            total_vendus = lignes.aggregate(total=Sum('quantite'))['total'] or 0

            total_par_categorie = lignes.values(
                'produit__categorie__desgcategorie'
            ).annotate(
                total_montant=Sum('sous_total'),
                total_quantite=Sum('quantite')
            )

            total_par_produit = lignes.values(
                'produit__desgprod'
            ).annotate(
                total_quantite=Sum('quantite'),
                total_montant=Sum('sous_total')
            )

            ventes_dict = {}
            for ligne in lignes:
                code = ligne.vente.code
                ventes_dict.setdefault(code, {
                    'vente': ligne.vente,
                    'lignes': [],
                    'total_vente': 0,
                    'benefice_vente': 0
                })

                ventes_dict[code]['lignes'].append(ligne)
                ventes_dict[code]['total_vente'] += ligne.sous_total

            data_qs = list(ventes_dict.values())

        # ================= COMMANDES =================
        elif type_rapport == "COMMANDES":
            data_qs = Commandes.objects.select_related(
                'produits', 'produits__categorie'
            ).filter(datecmd__range=[date_debut, date_fin])

            total_quantite = data_qs.aggregate(
                total=Sum('qtecmd')
            )['total'] or 0
            # -------- Par Catégorie ------------
            total_par_categorie = data_qs.values(
                'produits__categorie__desgcategorie'
            ).annotate(
                total_quantite=Sum('qtecmd'),
                nombre_commandes=Count('id', distinct=True),
                valeur=Sum(F('qtecmd') * F('produits__pu'))
            )
            # ------------------ TOTAL GLOBAUX ------------------
            total_quantite_cmd = data_qs.aggregate(total_qte=Sum('qtecmd'))['total_qte'] or 0

            # -------- Par Produit ------------
            total_par_produit = data_qs.values(
                'produits__desgprod',
                'produits__categorie__desgcategorie'
            ).annotate(
                nombre_commandes=Count('id', distinct=True),
                total_quantite=Sum('qtecmd'),
                valeur=Sum(F('qtecmd') * F('produits__pu'))
            )

        # ================= LIVRAISONS =================
        elif type_rapport == "LIVRAISONS":
            data_qs = LivraisonsProduits.objects.select_related(
                'produits', 'commande', 'produits__categorie'
            ).filter(datelivrer__range=[date_debut, date_fin])

            total_quantite = data_qs.aggregate(
                total=Sum('qtelivrer')
            )['total'] or 0
            
            total_quantite_livrer = data_qs.aggregate(
            total=Sum('qtelivrer')
            )['total'] or 0

            total_quantite_restante = data_qs.aggregate(
                total=Sum(F('commande__qtecmd') - F('qtelivrer'))
            )['total'] or 0
            
            # -------- Par Catégorie ------------
            total_par_categorie = data_qs.values(
                'produits__categorie__desgcategorie'
            ).annotate(
                nombre_livraison = Count('id', distinct=True),
                total_qtelivree=Sum('qtelivrer'),
                total_cmd=Sum('commande__qtecmd'),
                reste=F('total_cmd') - F('total_qtelivree')
            )
            
            # -------- Par Produit ------------
            total_par_produit = data_qs.values(
                'produits__desgprod',
                'produits__categorie__desgcategorie',
            ).annotate(
                nombre_livraison = Count('id', distinct=True),
                total_qtelivree=Sum('qtelivrer'),
                total_cmd=Sum('commande__qtecmd'),
                reste=F('total_cmd') - F('total_qtelivree'))


        else:
            messages.error(request, "Type de rapport invalide.")
            return redirect("rapports:creer_rapport")

        # ================= PDF =================
        context = {
            'rapport': rapport,
            'data': data_qs,
            'entreprise': entreprise,
            'total_montant': total_montant,
            'total_vendus': total_vendus,
            'total_quantite': total_quantite,
            'total_par_categorie': total_par_categorie,
            'total_par_produit': total_par_produit,
            'total_quantite_cmd' : total_quantite_cmd,
            'total_quantite_livrer' : total_quantite_livrer,
            'total_quantite_restante' : total_quantite_restante,
        }

        html = get_template('gestion_rapports/rapport_pdf.html').render(context)
        buffer = BytesIO()
        HTML(string=html).write_pdf(buffer)

        rapport.fichier_pdf.save(
            f"{slugify(titre)}.pdf",
            ContentFile(buffer.getvalue())
        )

        messages.success(request, "Rapport généré avec succès ✔")
        return HttpResponse(buffer.getvalue(), content_type="application/pdf")

    except Exception as e:
        messages.error(request, f"Erreur : {e}")
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




