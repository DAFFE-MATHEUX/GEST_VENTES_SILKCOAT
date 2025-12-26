from datetime import datetime
from django.template import TemplateDoesNotExist
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from gest_entreprise.models import Entreprise
from django.utils.timezone import now
from decimal import Decimal
import qrcode
from io import BytesIO
import base64
import openpyxl
from openpyxl.utils import get_column_letter

from gestion_notifications.models import Notification
from .utils import *
from gestion_audit.views import enregistrer_audit
from .models import * 
from django.core.mail import EmailMessage
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum, F, Count, Q, ExpressionWrapper, IntegerField
from openpyxl import Workbook

from django.db import transaction
from collections import defaultdict

from django.db import IntegrityError, DatabaseError
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required

import logging
logger = logging.getLogger(__name__)

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver([post_save, post_delete], sender=LigneVente)
def mise_a_jour_totaux_vente(sender, instance, **kwargs):
    instance.vente.calculer_totaux()

#================================================================================================
# Fonction pour ajouter une catégorie de produit
#================================================================================================

@login_required
@csrf_protect
def ajouter_categorie(request):
    try:
        if request.method == 'POST':
            nom = request.POST.get('nom', '').strip()
            description = request.POST.get('description', '').strip()

            # 1️⃣ Validation du champ obligatoire
            if not nom:
                messages.error(request, "Le nom de la catégorie est obligatoire.")
                return redirect('produits:ajouter_categorie')

            # 2️⃣ Vérification de doublon
            if CategorieProduit.objects.filter(desgcategorie__iexact=nom).exists():
                messages.warning(
                    request,
                    "Cette catégorie existe déjà."
                )
                return redirect('produits:ajouter_categorie')

            # 3️⃣ Création sécurisée
            CategorieProduit.objects.create(
                desgcategorie=nom,
                description=description
            )

            messages.success(request, "Catégorie ajoutée avec succès.")
            return redirect('produits:listes_categorie')

        # 4️⃣ Mauvaise méthode HTTP
        messages.error(request, "Méthode non autorisée.")
        return redirect('produits:listes_categorie')

    except IntegrityError:
        messages.error(
            request,
            "Erreur d'intégrité : données invalides ou doublon détecté."
        )
        return redirect('produits:ajouter_categorie')

    except DatabaseError:
        messages.error(
            request,
            "Erreur de base de données. Veuillez réessayer plus tard."
        )
        return redirect('produits:ajouter_categorie')

    except Exception as e:
        # 5️⃣ Erreur inconnue (loggable)
        messages.error(
            request,
            "Une erreur inattendue est survenue."
        )
        return redirect('produits:ajouter_categorie')

#================================================================================================
# Fonction pour éffectuer un approvisionnement
#================================================================================================
@login_required
def approvisionner_produits(request):
    produits = Produits.objects.all().select_related('categorie')

    # Préparer données avec stock unique
    produits_data = []
    for p in produits:
        stock = StockProduit.objects.filter(produit=p).first()
        produits_data.append({
            "produit": p,
            "stock": stock.qtestock if stock else 0,
            "stock_instance": stock,
        })

    if request.method == "POST":
        approvisionnements = []

        try:
            with transaction.atomic():
                for p in produits_data:
                    produit = p["produit"]
                    stock = p["stock_instance"]

                    qte_str = request.POST.get(f"quantite_{produit.id}", "0")
                    try:
                        qte = int(qte_str)
                    except ValueError:
                        qte = 0

                    if qte <= 0:
                        continue

                    # Créer stock si inexistant
                    if not stock:
                        stock = StockProduit.objects.create(
                            produit=produit,
                            qtestock=0,
                            seuil=0
                        )

                    stock.qtestock += qte
                    stock.save()

                    approvisionnements.append({
                        "produit": produit.desgprod,
                        "quantite": qte,
                        "stock_final": stock.qtestock
                    })

            # ================= EMAIL ADMIN =================
            if approvisionnements:
                try:
                    sujet = "Approvisionnement des produits"
                    contenu = f"""
Approvisionnement effectué avec succès.

Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}
Utilisateur : {request.user}

Détails :
"""
                    for a in approvisionnements:
                        contenu += f"- {a['produit']} | +{a['quantite']} | Stock final : {a['stock_final']}\n"

                    email = EmailMessage(
                        sujet,
                        contenu,
                        settings.DEFAULT_FROM_EMAIL,
                        [settings.ADMIN_EMAIL]
                    )
                    email.send(fail_silently=False)

                except Exception as e:
                    logger.error(f"Erreur email approvisionnement : {str(e)}")
                    messages.warning(
                        request,
                        "Approvisionnement effectué mais email non envoyé."
                    )

            messages.success(request, "Approvisionnement effectué avec succès ✔")
            return redirect("produits:listes_produits_stock")

        except Exception as e:
            messages.error(request, f"Erreur lors de l'approvisionnement : {str(e)}")

    return render(
        request,
        "gestion_produits/approvisionnement/approvisionner_produit.html",
        {"produits_data": produits_data}
    )

#================================================================================================
# Fonction pour éffectuer une nouvelle vente
#================================================================================================

@login_required
@csrf_protect
def vendre_produit(request):
    try:
        produits = Produits.objects.all()

        if request.method == "POST":

            ids = request.POST.getlist("produit_id[]")
            quantites = request.POST.getlist("quantite[]")
            reductions = request.POST.getlist("reduction[]")

            nom_complet = request.POST.get("nom_complet_client", "").strip()
            telephone = request.POST.get("telephone_client", "").strip()
            adresse = request.POST.get("adresse_client", "").strip()

            if not nom_complet or not telephone or not adresse:
                messages.error(
                    request,
                    "Veuillez renseigner le nom, le téléphone et l'adresse du client."
                )
                return redirect("produits:vendre_produit")

            total_general = 0
            lignes = []
            produits_sans_stock = []

            with transaction.atomic():

                for prod_id, qte_str, red_str in zip(ids, quantites, reductions):

                    try:
                        produit = Produits.objects.get(id=prod_id)
                    except Produits.DoesNotExist:
                        logger.warning(f"Produit inexistant: {prod_id}")
                        continue

                    try:
                        quantite = int(qte_str or 0)
                        reduction = int(red_str or 0)
                    except ValueError:
                        messages.error(
                            request,
                            f"Quantité ou réduction invalide pour {produit.desgprod}"
                        )
                        return redirect("produits:vendre_produit")

                    if quantite <= 0:
                        continue

                    stock = StockProduit.objects.select_for_update().filter(produit=produit).first()

                    if not stock or stock.qtestock <= 0:
                        produits_sans_stock.append(produit.desgprod)
                        continue  # on saute le produit sans stock

                    if stock.qtestock < quantite:
                        messages.error(
                            request,
                            f"Stock insuffisant pour {produit.desgprod} "
                            f"(Disponible : {stock.qtestock})"
                        )
                        return redirect("produits:vendre_produit")

                    if reduction > produit.pu:
                        messages.error(
                            request,
                            f"La réduction dépasse le prix unitaire pour {produit.desgprod}"
                        )
                        return redirect("produits:vendre_produit")

                    prix_net = produit.pu - reduction
                    sous_total = prix_net * quantite
                    total_general += sous_total

                    lignes.append({
                        "produit": produit,
                        "quantite": quantite,
                        "pu": produit.pu,
                        "reduction": reduction,
                        "sous_total": sous_total,
                        "stock": stock
                    })

                if produits_sans_stock:
                    messages.warning(
                        request,
                        f"Les produits suivants n'ont pas de stock et ont été ignorés: {', '.join(produits_sans_stock)}"
                    )

                if not lignes:
                    messages.error(
                        request,
                        "Aucun produit valide sélectionné pour la vente."
                    )
                    return redirect("produits:vendre_produit")

                # Création de la vente
                vente = VenteProduit.objects.create(
                    code=f"VENTE{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    total=total_general,
                    utilisateur=request.user,
                    nom_complet_client=nom_complet,
                    telclt_client=telephone,
                    adresseclt_client=adresse
                )

                # Création des lignes de vente et mise à jour du stock
                for ligne in lignes:
                    LigneVente.objects.create(
                        vente=vente,
                        produit=ligne["produit"],
                        quantite=ligne["quantite"],
                        prix=ligne["pu"],
                        montant_reduction=ligne["reduction"],
                        sous_total=ligne["sous_total"]
                    )
                    ligne["stock"].qtestock -= ligne["quantite"]
                    ligne["stock"].save(update_fields=["qtestock"])

                # Envoi d'email admin (non bloquant)
                try:
                    contenu = f"Nouvelle vente : {vente.code}\n\n"
                    for l in lignes:
                        contenu += f"- {l['produit'].desgprod} | Qté: {l['quantite']} | Reduction: {l['reduction']} | Sous-total: {l['sous_total']}\n"
                    contenu += f"\nTOTAL : {total_general}"

                    EmailMessage(
                        f"Nouvelle vente {vente.code}",
                        contenu,
                        settings.DEFAULT_FROM_EMAIL,
                        [settings.ADMIN_EMAIL]
                    ).send()

                except Exception as mail_error:
                    logger.error(f"Email vente échoué : {mail_error}")
                    messages.warning(
                        request,
                        "Vente enregistrée mais email non envoyé."
                    )

            messages.success(request, "✅ Vente enregistrée avec succès.")
            return redirect(
                reverse("produits:recu_vente_global", kwargs={"vente_code": vente.code})
            )

        return render(
            request,
            "gestion_produits/ventes/nouvelle_vente.html",
            {"produits": produits}
        )

    except IntegrityError:
        messages.error(request, "Erreur d'intégrité des données.")
        return redirect("produits:vendre_produit")

    except DatabaseError:
        messages.error(request, "Erreur de base de données. Veuillez réessayer.")
        return redirect("produits:vendre_produit")

    except Exception as e:
        # 🔹 Affichage détaillé pour debug
        logger.exception("Erreur vente produit")
        messages.error(
            request,
            f"Une erreur inattendue est survenue: {str(e)}"
        )
        return redirect("produits:vendre_produit")

#================================================================================================
# Fonction pour afficher l'historique des ventes par date
#================================================================================================

@login_required
@csrf_protect

def historique_ventes(request):

    ventes = (
        VenteProduit.objects
        .select_related("utilisateur")
        .prefetch_related("lignes__produit__categorie")
        .order_by("-date_vente")
    )

    ventes_par_date = defaultdict(list)

    for vente in ventes:
        ventes_par_date[vente.date_vente.date()].append(vente)

    historique = []

    for date, ventes_du_jour in ventes_par_date.items():
        total_montant = 0
        total_quantite = 0
        total_benefice = 0
        categories = set()

        for vente in ventes_du_jour:
            for ligne in vente.lignes.all():

                total_quantite += ligne.quantite
                total_benefice += ligne.benefice

                if ligne.produit and ligne.produit.categorie:
                    categories.add(ligne.produit.categorie.id)

            total_montant += vente.total

        historique.append({
            "date": date,
            "ventes": ventes_du_jour,
            "total_montant": total_montant,
            "total_quantite": total_quantite,
            "total_categories": len(categories),
            "total_profit": total_benefice,
        })

    return render(
        request,
        "gestion_produits/ventes/historique_ventes.html",
        {"historique": historique}
    )

#================================================================================================
# Fonction pour afficher l'historique des commandes et livraisons par date
#================================================================================================
@csrf_protect
@login_required
def historique_commandes_livraisons(request):
    """
    Vue sécurisée pour afficher l'historique des commandes et livraisons
    avec calculs côté Python.
    """
    try:
        historique = []
        commandes = Commandes.objects.all().order_by('-datecmd')

        total_commandes = 0
        total_livrees = 0
        total_restantes = 0

        for cmd in commandes:
            # 🔹 Récupérer les livraisons liées à cette commande
            livraisons = LivraisonsProduits.objects.filter(commande=cmd).order_by('datelivrer')
            
            # 🔹 Total livré pour cette commande
            total_livree = livraisons.aggregate(total=Sum('qtelivrer'))['total'] or 0
            
            # 🔹 Quantité restante
            qte_restante = max(cmd.qtecmd - total_livree, 0)

            historique.append({
                'commande': cmd,
                'livraisons': livraisons,
                'total_livree': total_livree,
                'qte_restante': qte_restante
            })

            # 🔹 Totaux pour le footer
            total_commandes += cmd.qtecmd or 0
            total_livrees += total_livree
            total_restantes += qte_restante

        context = {
            'historique': historique,
            'total_commandes': total_commandes,
            'total_livrees': total_livrees,
            'total_restantes': total_restantes
        }

        return render(
            request,
            'gestion_produits/livraisons/historique_commandes_livraisons.html',
            context
        )

    except DatabaseError as db_err:
        logger.error(f"Erreur base de données historique commandes/livraisons: {db_err}")
        messages.error(request, "Erreur lors de la récupération des commandes/livraisons.")
        return render(request, 'gestion_produits/livraisons/historique_commandes_livraisons.html', {
            'historique': [],
            'total_commandes': 0,
            'total_livrees': 0,
            'total_restantes': 0
        })

    except Exception as e:
        logger.exception("Erreur inattendue historique commandes/livraisons")
        messages.error(request, "Une erreur inattendue est survenue.")
        return render(request, 'gestion_produits/livraisons/historique_commandes_livraisons.html', {
            'historique': [],
            'total_commandes': 0,
            'total_livrees': 0,
            'total_restantes': 0
        })

#================================================================================================
# Fonction pour éffectuer une nouvelle commande
#================================================================================================
@csrf_protect
@login_required

def nouvelle_commande(request):
    """
    Vue sécurisée pour créer une nouvelle commande.
    Enregistre la commande et envoie un email à l'admin.
    """
    produits = Produits.objects.all()
    produits_data = [{"produit": p} for p in produits]

    if request.method == "POST":
        ids = request.POST.getlist("produit_id[]")
        quantites = request.POST.getlist("quantite[]")

        # Informations fournisseur
        nom_complet_fournisseur = request.POST.get("nom_complet_fournisseur")
        telephone_fournisseur = request.POST.get("telephone_fournisseur")
        adresse_fournisseur = request.POST.get("adresse_fournisseur")

        if not ids or not quantites:
            messages.error(request, "Aucun produit sélectionné.")
            return redirect("produits:nouvelle_commande")

        lignes = []
        total_general = 0
        numcmd = f"CMD{timezone.now().strftime('%Y%m%d%H%M%S')}"

        try:
            for i in range(len(ids)):
                try:
                    prod = Produits.objects.get(id=ids[i])
                except Produits.DoesNotExist:
                    messages.error(request, "Produit introuvable.")
                    continue  # passer au suivant

                try:
                    qte = int(quantites[i])
                except ValueError:
                    messages.error(request, f"Quantité invalide pour {prod.desgprod}.")
                    continue

                if qte <= 0:
                    continue  # Ignorer

                # Créer la commande
                Commandes.objects.create(
                    numcmd=numcmd,
                    qtecmd=qte,
                    produits=prod,
                    nom_complet_fournisseur=nom_complet_fournisseur,
                    adresse_fournisseur=adresse_fournisseur,
                    telephone_fournisseur=telephone_fournisseur,
                )

                lignes.append((prod, qte))
                total_general += prod.pu * qte

            if not lignes:
                messages.error(request, "Aucune commande valide n'a été enregistrée.")
                return redirect("produits:nouvelle_commande")

            # 🔹 Envoi email sécurisé
            try:
                sujet = f"Nouvelle commande enregistrée - Fournisseur {nom_complet_fournisseur}"
                contenu = f"""
Nouvelle commande effectuée.

Fournisseur : {nom_complet_fournisseur}
Téléphone : {telephone_fournisseur}
Adresse : {adresse_fournisseur}

Total estimé : {total_general:,} GNF

Détails :
"""
                for p, q in lignes:
                    contenu += f"- {p.desgprod} | Qté : {q} | PU : {p.pu} | Sous-total : {p.pu * q}\n"

                EmailMessage(
                    sujet,
                    contenu,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL],
                ).send(fail_silently=False)

            except Exception as e:
                logger.warning(f"Email non envoyé pour la commande {numcmd}: {str(e)}")
                messages.warning(request, f"Commande enregistrée mais email non envoyé : {str(e)}")

            messages.success(request, f"Commande {numcmd} enregistrée avec succès !")
            return redirect("produits:listes_des_commandes")

        except Exception as e:
            logger.error(f"Erreur inattendue lors de la création de la commande: {str(e)}")
            messages.error(request, "Erreur inattendue lors de l'enregistrement de la commande.")
            return redirect("produits:nouvelle_commande")

    context = {'produits_data': produits_data}
    return render(request, "gestion_produits/commandes/nouvelle_commande.html", context)

#================================================================================================
# Fonction pour éffectuer une receptin de livraisons des commandes
#================================================================================================

@login_required
@transaction.atomic
def reception_livraison(request):
    """
    Vue sécurisée pour réceptionner les commandes avec livraison.
    L'utilisateur peut saisir 0 pour refuser certaines livraisons.
    Envoi un email à l'administrateur après la livraison.
    """
    # 🔹 Préparer les commandes avec quantité restante
    commandes_data = []
    commandes = Commandes.objects.all().order_by('-datecmd')

    for cmd in commandes:
        total_livree = (
            LivraisonsProduits.objects
            .filter(commande=cmd)
            .aggregate(total=Sum("qtelivrer"))["total"] or 0
        )
        qte_restante = max(cmd.qtecmd - total_livree, 0)

        commandes_data.append({
            "commande": cmd,
            "total_livree": total_livree,
            "qte_restante": qte_restante
        })

    # 🔹 Traitement POST
    if request.method == "POST":
        commande_ids = request.POST.getlist("commande_id[]")
        qte_livree_list = request.POST.getlist("qte_livree[]")

        if len(commande_ids) != len(qte_livree_list):
            messages.error(request, "Erreur : données du formulaire invalides.")
            return redirect("produits:reception_livraison")

        numlivrer = f"LIV{timezone.now().strftime('%Y%m%d%H%M%S')}"
        livraisons_effectuees = []

        for i, cmd_id in enumerate(commande_ids):
            try:
                cmd = Commandes.objects.get(id=cmd_id)
            except Commandes.DoesNotExist:
                logger.warning(f"Commande introuvable : {cmd_id}")
                continue

            try:
                qte_livree = int(qte_livree_list[i])
            except ValueError:
                qte_livree = 0

            total_livree = (
                LivraisonsProduits.objects
                .filter(commande=cmd)
                .aggregate(total=Sum("qtelivrer"))["total"] or 0
            )
            qte_restante = cmd.qtecmd - total_livree

            if qte_livree <= 0:
                continue
            if qte_livree > qte_restante:
                messages.warning(
                    request,
                    f"{cmd.produits.desgprod} : quantité saisie ({qte_livree}) supérieure à la quantité restante ({qte_restante})."
                )
                continue

            try:
                # 🔹 Enregistrer la livraison
                LivraisonsProduits.objects.create(
                    numlivrer=numlivrer,
                    commande=cmd,
                    produits=cmd.produits,
                    qtelivrer=qte_livree,
                    datelivrer=timezone.now().date(),
                    statuts="Livrée"
                )

                # 🔹 Mise à jour du stock
                stock, created = StockProduit.objects.get_or_create(
                    produit=cmd.produits,
                    defaults={"qtestock": qte_livree}
                )
                if not created:
                    stock.qtestock += qte_livree
                    stock.save(update_fields=["qtestock"])

                # 🔹 Mise à jour statut commande
                total_livree += qte_livree
                cmd.statuts = "Livrée" if total_livree == cmd.qtecmd else "Partiellement livrée"
                cmd.save(update_fields=["statuts"])

                livraisons_effectuees.append({
                    "commande": cmd.numcmd,
                    "produit": cmd.produits.desgprod,
                    "qte_livree": qte_livree,
                    "fournisseur": cmd.nom_complet_fournisseur
                })

            except Exception as e:
                logger.error(f"Erreur lors de l'enregistrement de la livraison pour {cmd.numcmd}: {str(e)}")
                messages.error(request, f"Erreur lors de l'enregistrement de la livraison pour {cmd.produits.desgprod}.")

        # 🔹 Email admin
        if livraisons_effectuees:
            contenu = "📦 Nouvelle réception de livraison :\n\n"
            for l in livraisons_effectuees:
                contenu += (
                    f"- Commande : {l['commande']} | "
                    f"Produit : {l['produit']} | "
                    f"Quantité livrée : {l['qte_livree']} | "
                    f"Fournisseur : {l['fournisseur']}\n"
                )
            try:
                EmailMessage(
                    subject="Réception de livraison enregistrée",
                    body=contenu,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.ADMIN_EMAIL]
                ).send(fail_silently=False)
            except Exception as e:
                logger.warning(f"Email non envoyé pour la réception {numlivrer}: {str(e)}")
                messages.warning(request, f"Email non envoyé : {str(e)}")

        messages.success(request, "Livraison enregistrée avec succès.")
        return redirect("produits:listes_des_livraisons")

    return render(
        request,
        "gestion_produits/livraisons/reception_livraison.html",
        {"commandes": commandes_data}
    )

#=============================================================================================
# Fonction pour gérer les réçu Global de Ventes
#=============================================================================================
@login_required
def recu_vente_global(request, vente_code):
    try:
        vente = VenteProduit.objects.get(code=vente_code)
    except VenteProduit.DoesNotExist:
        messages.error(request, f"Aucune vente ne correspond au code : {vente_code}")
        return redirect("produits:listes_des_ventes")
    except Exception as ex:
        messages.error(request, f"Erreur inattendue : {str(ex)}")
        return redirect("produits:listes_des_ventes")

    # --- récupérer les lignes ---
    lignes = LigneVente.objects.filter(vente=vente)
    if not lignes.exists():
        messages.error(request, "Aucun produit trouvé pour cette vente.")
        return redirect("produits:listes_des_ventes")

    # --- calcul du total ---
    total = sum(Decimal(l.sous_total) for l in lignes)

    # --- génération QR code ---
    try:
        qr_data = (
            f"Reçu Vente : {vente.code}\n"
            f"Date : {vente.date_vente.strftime('%d/%m/%Y %H:%M')}\n"
            f"Nombre d'articles : {lignes.count()}\n"
            f"Total : {total} GNF\n"
            f"Nom du Client : {vente.nom_complet_client}\n"
            f"Téléphone du Client : {vente.telclt_client}\n"
            f"Adresse du Client : {vente.adresseclt_client}\n"
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    except Exception as e:
        qr_code_base64 = None
        messages.warning(request, f"QR code non généré : {e}")

    # --- contexte pour le template ---
    context = {
        "vente": vente,
        "lignes": lignes,
        "total": total,
        "today": now(),
        "qr_code_base64": qr_code_base64,
        "entreprise": Entreprise.objects.first(),  # Assure-toi qu'il y a bien une instance
    }

    return render(request, "gestion_produits/recu_ventes/recu_vente_global.html", context)

#================================================================================================
# Fonction pour afficher la listes des catégories
#================================================================================================
@login_required
def listes_categorie(request):
    try:
        # Récupérer toutes les catégories par ordre décroissant d'id
        listes_categories = CategorieProduit.objects.all().order_by('-id')

        # Pagination : 10 catégories par page
        paginator = Paginator(listes_categories, 10)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        total_categories = listes_categories.count()
    except Exception as ex:
        messages.warning(request, f"Erreur lors du chargement des catégories : {str(ex)}")
        page_obj = []
        total_categories = 0

    context = {
        'liste_categories': page_obj,  # objet paginé pour le template
        'total_categories': total_categories,
    }
    return render(request, "gestion_produits/listes_categorie.html", context)

#================================================================================================
# Fonction pour modifier les informations d'une catégorie de produit
#================================================================================================
@login_required
def modifier_categorie(request):
    if request.method == 'POST':
        cat_id = request.POST.get('id_modif')
        nom = request.POST.get('nom_modif')
        description = request.POST.get('description_modif')

        if not cat_id or not nom:
            messages.error(request, "L'identifiant et le nom de la catégorie sont obligatoires.")
            return redirect('produits:listes_categorie')

        try:
            categorie = CategorieProduit.objects.get(id=cat_id)
            categorie.desgcategorie = nom
            categorie.description = description
            categorie.save(update_fields=['desgcategorie', 'description'])

            messages.success(request, "Catégorie modifiée avec succès !")
        except CategorieProduit.DoesNotExist:
            messages.error(request, "La catégorie spécifiée n'existe pas.")
        except Exception as ex:
            messages.error(request, f"Erreur lors de la modification : {str(ex)}")

        return redirect('produits:listes_categorie')

#================================================================================================
# Fonction pour supprimer une catégorie de produit
#================================================================================================
@login_required
def supprimer_categorie(request):
    if request.method == 'POST':
        cat_id = request.POST.get('id_supprime')
        if not cat_id:
            messages.error(request, "Aucun identifiant de catégorie fourni.")
            return redirect('produits:listes_categorie')

        try:
            categorie = CategorieProduit.objects.get(id=cat_id)

            # Vérifier si la catégorie est utilisée par un produit
            if Produits.objects.filter(categorie=cat_id).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer cette catégorie car elle est utilisée par un produit. "
                    "Veuillez d'abord supprimer les produits associés."
                )
                return redirect('produits:listes_categorie')

            # Préparer l'ancienne valeur pour audit/email
            ancienne_valeur = {
                "id": categorie.id,
                "nom_categorie": categorie.desgcategorie,
                "description": categorie.description if categorie.description else ""
            }

            # Supprimer la catégorie
            categorie.delete()

            # Enregistrer audit
            enregistrer_audit(
                utilisateur=request.user,
                action="Suppression catégorie",
                table="CategorieProduit",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
            )

            # Envoyer notification par email à l'admin
            try:
                sujet = "🗑 Suppression de catégorie"
                contenu = (
                    f"L'utilisateur {request.user.get_full_name()} "
                    f"a supprimé la catégorie :\n\n"
                    f"ID : {ancienne_valeur['id']}\n"
                    f"Nom : {ancienne_valeur['nom_categorie']}\n"
                    f"Description : {ancienne_valeur['description']}"
                )
                EmailMessage(
                    sujet,
                    contenu,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL],
                ).send(fail_silently=False)
            except Exception as e:
                messages.warning(request, f"Catégorie supprimée mais email non envoyé : {e}")

            messages.success(request, "Catégorie supprimée avec succès !")

        except CategorieProduit.DoesNotExist:
            messages.error(request, "Catégorie introuvable.")
        except Exception as ex:
            messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

        return redirect('produits:listes_categorie')

#================================================================================================
# Fonction pour supprimer un produit donné
#================================================================================================
@login_required
def supprimer_produits(request):
    if request.method != 'POST':
        messages.error(request, "Méthode invalide pour cette action.")
        return redirect('produits:listes_produits')

    prod_id = request.POST.get('id_supprimer')
    if not prod_id:
        messages.error(request, "Aucun produit sélectionné pour la suppression.")
        return redirect('produits:listes_produits')

    try:
        produit = Produits.objects.get(id=prod_id)

        # Vérifier les dépendances
        if LigneVente.objects.filter(produit=produit).exists():
            messages.warning(
                request,
                "Impossible de supprimer ce produit car il est utilisé dans une vente."
            )
            return redirect('produits:listes_produits')

        if StockProduit.objects.filter(produit=produit).exists():
            messages.warning(
                request,
                "Impossible de supprimer ce produit car il est utilisé dans un stock."
            )
            return redirect('produits:listes_produits')

        if Commandes.objects.filter(produits=produit).exists():
            messages.warning(
                request,
                "Impossible de supprimer ce produit car il est utilisé dans une commande."
            )
            return redirect('produits:listes_produits')

        if LivraisonsProduits.objects.filter(produits=produit).exists():
            messages.warning(
                request,
                "Impossible de supprimer ce produit car il est utilisé dans une livraison."
            )
            return redirect('produits:listes_produits')

        # ----- Ancienne valeur pour audit -----
        ancienne_valeur = {
            "id": produit.id,
            "refprod": produit.refprod,
            "desgprod": produit.desgprod,
            "pu": float(produit.pu),
            "categorie": str(produit.categorie) if produit.categorie else None,
        }

        # ----- Suppression -----
        produit.delete()

        # ----- Audit -----
        enregistrer_audit(
            utilisateur=request.user,
            action="Suppression produit",
            table="Produits",
            ancienne_valeur=ancienne_valeur,
            nouvelle_valeur=None
        )

        # ----- Email à l'admin -----
        try:
            sujet = f"Produit supprimé : {ancienne_valeur['desgprod']}"
            contenu = (
                f"Utilisateur : {request.user.get_full_name()} a supprimé un produit.\n\n"
                f"Détails du produit supprimé :\n"
                f"- ID : {ancienne_valeur['id']}\n"
                f"- Référence : {ancienne_valeur['refprod']}\n"
                f"- Désignation : {ancienne_valeur['desgprod']}\n"
                f"- Prix : {ancienne_valeur['pu']}\n"
                f"- Catégorie : {ancienne_valeur['categorie']}\n"
            )
            EmailMessage(
                sujet,
                contenu,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL]
            ).send(fail_silently=False)
        except Exception as e:
            messages.warning(request, f"Produit supprimé mais email non envoyé : {str(e)}")

        messages.success(request, "Produit supprimé avec succès !")
    except Produits.DoesNotExist:
        messages.error(request, "Produit introuvable.")
    except Exception as ex:
        messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

    return redirect('produits:listes_produits')

#================================================================================================
# Fonction pour supprimer un produit donné
#================================================================================================
@login_required
def supprimer_produits_stock(request):
    if request.method != 'POST':
        messages.error(request, "Méthode invalide pour cette action.")
        return redirect('produits:listes_produits_stock')

    stock_id = request.POST.get('id_supprimer')
    if not stock_id:
        messages.error(request, "Aucun stock sélectionné pour la suppression.")
        return redirect('produits:listes_produits_stock')

    try:
        stock = StockProduit.objects.select_related('produit', 'entrepot', 'magasin').get(id=stock_id)

        # ----- Ancienne valeur pour audit -----
        ancienne_valeur = {
            "id_stock": stock.id,
            "produit": stock.produit.desgprod,
            "reference": stock.produit.refprod,
            "quantite": stock.qtestock,
            "seuil": stock.seuil,
            "entrepot": str(stock.entrepot) if stock.entrepot else "N/A",
            "magasin": str(stock.magasin) if stock.magasin else "N/A",
        }

        # ----- Suppression -----
        stock.delete()

        # ----- Audit -----
        enregistrer_audit(
            utilisateur=request.user,
            action="Suppression stock produit",
            table="StockProduit",
            ancienne_valeur=ancienne_valeur,
            nouvelle_valeur=None
        )

        # ----- Notification interne -----
        Notification.objects.create(
            destinataire=request.user,
            titre="🗑 Suppression de stock",
            message=(
                f"Le stock du produit {ancienne_valeur['produit']} "
                f"a été supprimé avec succès."
            )
        )

        # ----- Email admin -----
        try:
            sujet = "🗑 Suppression d’un stock produit"
            contenu = f"""
Une suppression de stock a été effectuée.

Utilisateur : {request.user.get_full_name()}
Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}

Détails du stock supprimé :
- Produit : {ancienne_valeur['produit']}
- Référence : {ancienne_valeur['reference']}
- Quantité : {ancienne_valeur['quantite']}
- Seuil : {ancienne_valeur['seuil']}
- Entrepôt : {ancienne_valeur['entrepot']}
- Magasin : {ancienne_valeur['magasin']}
"""
            EmailMessage(
                sujet,
                contenu,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL]
            ).send(fail_silently=False)
        except Exception as e:
            logger.error(f"Erreur envoi email suppression stock : {str(e)}")
            messages.warning(
                request,
                "Stock supprimé, mais l'email d'information n'a pas pu être envoyé."
            )

        messages.success(request, "Stock produit supprimé avec succès.")

    except StockProduit.DoesNotExist:
        messages.error(request, "Stock introuvable.")
    except Exception as ex:
        messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

    return redirect('produits:listes_produits_stock')

#================================================================================================
# Fonction pour supprimer une commande donnée
#================================================================================================

@login_required
def supprimer_commandes(request):
    if request.method != 'POST':
        messages.error(request, "Méthode invalide pour cette action.")
        return redirect('produits:listes_des_commandes')

    commande_id = request.POST.get('id_supprimer')
    if not commande_id:
        messages.warning(request, "Aucune commande sélectionnée pour suppression.")
        return redirect('produits:listes_des_commandes')

    try:
        commande = get_object_or_404(Commandes, id=commande_id)

        # Vérifier si la commande est liée à des livraisons
        if commande.livraisonsproduits_set.exists():
            messages.warning(
                request,
                "Impossible de supprimer cette commande car elle est déjà liée à des livraisons."
            )
            return redirect('produits:listes_des_commandes')

        # ----- Préparer ancienne valeur pour audit -----
        ancienne_valeur = {
            "Num Commande": commande.numcmd,
            "Produit": commande.produits.desgprod if commande.produits else "",
            "Qté commandée": commande.qtecmd,
            "Fournisseur": commande.nom_complet_fournisseur,
            "Utilisateur connecté": request.user.get_full_name(),
        }

        # ----- Suppression -----
        commande.delete()

        # ----- Enregistrement de l'audit -----
        enregistrer_audit(
            utilisateur=request.user,
            action="Suppression commande",
            table="Commandes",
            ancienne_valeur=ancienne_valeur,
            nouvelle_valeur=None
        )

        # ----- Notification interne -----
        Notification.objects.create(
            destinataire=request.user,
            titre="🗑 Suppression de commande",
            message=f"La commande {ancienne_valeur['Num Commande']} a été supprimée."
        )

        # ----- Email admin -----
        try:
            sujet = "🗑 Suppression d'une commande"
            contenu = f"""
Une commande a été supprimée.

Numéro commande : {ancienne_valeur['Num Commande']}
Produit : {ancienne_valeur['Produit']}
Qté commandée : {ancienne_valeur['Qté commandée']}
Fournisseur : {ancienne_valeur['Fournisseur']}
Utilisateur : {request.user.get_full_name()}
Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}
"""
            EmailMessage(
                sujet,
                contenu,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL]
            ).send(fail_silently=False)
        except Exception as e:
            logger.error(f"Erreur email suppression commande : {str(e)}")
            messages.warning(
                request,
                "Commande supprimée mais l'email d'information n'a pas pu être envoyé."
            )

        messages.success(request, "Commande supprimée avec succès ✔")

    except Exception as ex:
        messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

    return redirect('produits:listes_des_commandes')

#================================================================================================
# Fonction pour supprimer une livraisons donnée
#================================================================================================

@login_required
def supprimer_livraisons(request):
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée.")
        return redirect('produits:listes_des_livraisons')

    livraison_id = request.POST.get('id_supprimer')

    if not livraison_id:
        messages.warning(request, "Aucune livraison sélectionnée.")
        return redirect('produits:listes_des_livraisons')

    try:
        with transaction.atomic():
            # 1️⃣ Récupérer la livraison
            livraison = get_object_or_404(LivraisonsProduits, id=livraison_id)
            produit = livraison.produits
            quantite = livraison.qtelivrer
            numlivrer = livraison.numlivrer

            # 2️⃣ Restaurer le stock produit
            stock_produit = StockProduit.objects.filter(produit=produit).first()
            if stock_produit:
                stock_produit.qtestock = stock_produit.qtestock - quantite  # <-- correction
                stock_produit.save(update_fields=['qtestock'])

            # 3️⃣ Ancienne valeur (audit)
            ancienne_valeur = {
                "id_livraison": livraison.id,
                "numlivrer": numlivrer,
                "produit": produit.desgprod,
                "quantite_livree": quantite,
                "date": str(livraison.datelivrer),
            }

            # 4️⃣ Supprimer la livraison
            livraison.delete()

            # 5️⃣ Enregistrement audit
            enregistrer_audit(
                utilisateur=request.user,
                action="Suppression livraison produit",
                table="LivraisonsProduits",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
            )

        # 6️⃣ Notification interne
        Notification.objects.create(
            destinataire=request.user,
            titre="🗑 Suppression de livraison",
            message=(
                f"La livraison {numlivrer} du produit "
                f"{produit.desgprod} a été supprimée."
            )
        )

        # 7️⃣ Email administrateur
        try:
            sujet = "🗑 Suppression d'une livraison"
            contenu = f"""
Une livraison a été supprimée.

Numéro livraison : {numlivrer}
Produit : {produit.desgprod}
Quantité : {quantite}
Utilisateur : {request.user}
Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}
"""
            email = EmailMessage(
                sujet,
                contenu,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL]
            )
            email.send(fail_silently=False)
        except Exception as e:
            logger.error(f"Erreur email suppression livraison : {str(e)}")
            messages.warning(
                request,
                "Livraison supprimée mais l'email d'information n'a pas pu être envoyé."
            )

        messages.success(request, "Livraison supprimée avec succès. Stock mis à jour ✔")

    except Exception as ex:
        messages.error(
            request,
            f"Erreur lors de la suppression de la livraison : {str(ex)}"
        )

    return redirect('produits:listes_des_livraisons')

#================================================================================================
# Fonction pour supprimer une vente donnée
#================================================================================================
@login_required
def supprimer_ventes(request):
    if request.method != 'POST':
        messages.warning(request, "Méthode non autorisée.")
        return redirect('produits:listes_des_ventes')

    ligne_id = request.POST.get('id_supprimer')
    if not ligne_id:
        messages.warning(request, "Aucune vente sélectionnée.")
        return redirect('produits:listes_des_ventes')

    try:
        with transaction.atomic():

            # 1️⃣ Récupérer la ligne de vente
            ligne = get_object_or_404(LigneVente, id=ligne_id)
            vente = ligne.vente
            code_vente = vente.code

            # 2️⃣ Récupérer toutes les lignes de la vente
            lignes = LigneVente.objects.select_related('produit').filter(vente=vente)

            # 3️⃣ Restaurer le stock global
            for l in lignes:
                stock, created = StockProduit.objects.get_or_create(
                    produit=l.produit,
                    defaults={"qtestock": 0}
                )
                stock.qtestock += l.quantite
                stock.save(update_fields=["qtestock"])

            # 4️⃣ Audit
            ancienne_valeur = {
                "Vente": code_vente,
                "Produits": [
                    {
                        "Produit": l.produit.desgprod,
                        "Quantité": l.quantite,
                        "Sous-total": l.sous_total
                    } for l in lignes
                ],
                "Utilisateur": request.user.get_full_name(),
                "Date": timezone.now().strftime('%d/%m/%Y %H:%M')
            }

            enregistrer_audit(
                utilisateur=request.user,
                action="Suppression",
                table="VenteProduit",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
            )

            # 5️⃣ Supprimer lignes + vente
            lignes.delete()
            vente.delete()

            # 6️⃣ Notification
            Notification.objects.create(
                destinataire=request.user,
                titre=f"🗑 Suppression vente {code_vente}",
                message="La vente a été supprimée et le stock restauré."
            )

            # 7️⃣ Email admin
            try:
                EmailMessage(
                    subject=f"🗑 Suppression d'une vente - {code_vente}",
                    body=f"""
            Une vente a été supprimée.

            Code : {code_vente}
            Utilisateur : {request.user.get_full_name()}
            Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}

            Le stock a été restauré automatiquement.
            """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.ADMIN_EMAIL]
                ).send()
            except Exception:
                messages.warning(request, "Email non envoyé.")

        messages.success(
            request,
            f"✅ Vente {code_vente} supprimée avec succès. Stock restauré ✔"
        )
    except Exception as e:
        messages.error(request, f"⚠️ Erreur suppression : {e}")

    return redirect('produits:listes_des_ventes')

#================================================================================================
# Fonction pour afficher la liste de tout les produits
#================================================================================================
@login_required
def listes_produits(request):
    try:
        # ================= LISTE DES PRODUITS =================
        produits = (
            Produits.objects
            .select_related('categorie')
            .order_by('-id')
        )
        total_quantite_restante = StockProduit.objects.aggregate(
            total=Sum('qtestock')
        )['total'] or 0
        total_produit = produits.count()

        # ================= TOTAL PAR CATÉGORIE =================
        total_par_categorie = (
            produits
            .values('categorie__desgcategorie')
            .annotate(
                nombre_produits=Count('id', distinct=True),
                quantite_stock=Sum('stocks__qtestock'),
                valeur_stock=Sum(F('stocks__qtestock') * F('pu'))
            )
            .order_by('categorie__desgcategorie')
        )

        listes_produits = pagination_liste(request, produits)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des produits : {str(ex)}")
        listes_produits = []
        total_produit = 0
        total_quantite_restante = 0
        total_par_categorie = []

    context = {
        'listes_produits': listes_produits,
        'total_produit': total_produit,
        'total_par_categorie': total_par_categorie, 
        'total_quantite_restante' : total_quantite_restante,
    }

    return render(
        request,
        "gestion_produits/lites_produits.html",
        context
    )

#================================================================================================
# Fonction pour afficher la liste de tout les produits
#================================================================================================
@login_required
def listes_produits_stock(request):
    try:
        # ================= LISTE DES STOCKS =================
        listes_stock = (
            StockProduit.objects
            .select_related(
                'produit',
                'produit__categorie'
            )
            .order_by('-id')
        )
        total_stocks = StockProduit.objects.aggregate(
            total=Sum('qtestock')
        )['total'] or 0
        total_produit = listes_stock.count()

        # ================= TOTAL PAR CATÉGORIE =================
        total_par_categorie = (
            StockProduit.objects
            .values(
                'produit__categorie__desgcategorie',
                'produit__pu',    
                )
            .annotate(
                nombre_produits=Count('produit', distinct=True),
                quantite_stock=Sum('qtestock'),
                total_stock=Sum('qtestock'),
                valeur_stock=Sum(
                    F('qtestock') * F('produit__pu')
                ),
            ).order_by('produit__categorie__desgcategorie'))
        listes_stock = pagination_liste(request, listes_stock)
    except Exception as ex:
        messages.error(
            request,
            f"Erreur de récupération des produits en stock : {str(ex)}"
        )
        return redirect('produits:listes_produits_stock')

    context = {
        'listes_produits': listes_stock,
        'total_produit': total_produit,
        'total_par_categorie': total_par_categorie,
        'total_stocks' : total_stocks,
    }

    return render(
        request,
        "gestion_produits/stocks/lites_produits_stocks.html",
        context
    )


#================================================================================================
# Fonction pour afficher la liste de tout les livraisons
#================================================================================================
@login_required
def listes_des_livraisons(request):

    try:
        # ================= LIVRAISONS =================
        livraisons_qs = LivraisonsProduits.objects.select_related(
            'commande', 'produits', 'produits__categorie'
        )

        # ================= QUANTITÉ LIVRÉE PAR COMMANDE =================
        livraison_par_commande = (
            LivraisonsProduits.objects
            .values('commande')
            .annotate(total_livree=Sum('qtelivrer'))
        )

        livraison_map = {
            l['commande']: l['total_livree'] for l in livraison_par_commande
        }

        # ================= LISTE + QTE RESTANTE =================
        listes_livraisons = livraisons_qs.order_by('-id')

        total_quantite_restante = 0
        for l in listes_livraisons:
            total_livree = livraison_map.get(l.commande_id, 0)
            l.qte_restante = max(l.commande.qtecmd - total_livree, 0)
            total_quantite_restante += l.qte_restante

        # ================= TOTAUX GLOBAUX =================
        total_livraison = listes_livraisons.count()

        total_quantite_livrer = listes_livraisons.aggregate(
            total=Sum('qtelivrer')
        )['total'] or 0
        
        total_qtecmd = listes_livraisons.aggregate(
            total=Sum('commande__qtecmd')
        )['total'] or 0

        total_quantite_livrer = listes_livraisons.aggregate(
            total=Sum('qtelivrer')
        )['total'] or 0

        total_quantite_restante = listes_livraisons.aggregate(
            total=Sum(F('commande__qtecmd') - F('qtelivrer'))
        )['total'] or 0


        # ================= TOTAUX PAR CATÉGORIE =================
        total_par_categorie = (
            LivraisonsProduits.objects
            .values('produits__categorie__desgcategorie')
            .annotate(
                nombre_livraisons=Count('id'),
                total_qtelivree=Sum('qtelivrer'),
                total_qtecmd=Sum('commande__qtecmd')
            )
            .annotate(
                total_qte_restante=F('total_qtecmd') - F('total_qtelivree')
            )
            .order_by('produits__categorie__desgcategorie')
        )
        # ================= TOTAUX PAR PRODUIT =================
        total_par_produit = (
            LivraisonsProduits.objects
            .values(
                'produits_id',
                'produits__desgprod',
                'produits__categorie__desgcategorie'
            )
            .annotate(
                nombre_livraisons=Count('id'),
                total_qtelivree=Sum('qtelivrer'),
                total_qtecmd=Sum('commande__qtecmd')
            )
            .annotate(
                total_qte_restante=F('total_qtecmd') - F('total_qtelivree')
            )
            .order_by('produits__desgprod')
        )

        # ================= PAGINATION =================
        listes_livraisons = pagination_liste(request, listes_livraisons)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération : {ex}")
        listes_livraisons = []
        total_livraison = 0
        total_quantite_livrer = 0
        total_quantite_restante = 0
        total_par_categorie = []
        total_par_produit = []
        total_qtecmd = 0
        total_quantite_livrer = 0
        total_quantite_restante = 0

    context = {
        'listes_livraisons': listes_livraisons,
        'total_livraison': total_livraison,
        'total_quantite_livrer': total_quantite_livrer,
        'total_quantite_restante': total_quantite_restante,
        'total_par_categorie': total_par_categorie,
        'total_par_produit': total_par_produit,
        'total_qtecmd' : total_qtecmd,
        
    }

    return render(
        request,
        "gestion_produits/livraisons/listes_livraisons.html",
        context
    )

#================================================================================================
# Fonction pour filtrer la liste des livraisons par date
#================================================================================================
@login_required
def filtrer_listes_livraisons(request):

    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    try:
        # ================= QUERYSET DE BASE =================
        livraisons_qs = LivraisonsProduits.objects.select_related(
            'commande',
            'produits',
            'produits__categorie'
        )

        # ================= FILTRE PAR DATE =================
        if date_debut and date_fin:
            livraisons_qs = livraisons_qs.filter(
                datelivrer__range=[date_debut, date_fin]
            )
        elif date_debut:
            livraisons_qs = livraisons_qs.filter(datelivrer=date_debut)
        elif date_fin:
            livraisons_qs = livraisons_qs.filter(datelivrer=date_fin)

        livraisons_qs = livraisons_qs.order_by('-id')

        # ================= QTE LIVRÉE PAR COMMANDE =================
        livraison_par_commande = (
            livraisons_qs
            .values('commande')
            .annotate(total_livree=Sum('qtelivrer'))
        )

        livraison_map = {
            l['commande']: l['total_livree'] for l in livraison_par_commande
        }

        # ================= LISTE + QTE RESTANTE =================
        total_quantite_restante = 0
        for l in livraisons_qs:
            total_livree = livraison_map.get(l.commande_id, 0)
            l.qte_restante = max(l.commande.qtecmd - total_livree, 0)
            total_quantite_restante += l.qte_restante

        # ================= TOTAUX GLOBAUX =================
        total_livraison = livraisons_qs.count()

        total_qtecmd = livraisons_qs.aggregate(
            total=Sum('commande__qtecmd')
        )['total'] or 0

        total_quantite_livrer = livraisons_qs.aggregate(
            total=Sum('qtelivrer')
        )['total'] or 0

        total_quantite_restante = livraisons_qs.aggregate(
            total=Sum(F('commande__qtecmd') - F('qtelivrer'))
        )['total'] or 0

        # ================= TOTAUX PAR CATÉGORIE =================
        total_par_categorie = (
            livraisons_qs
            .values('produits__categorie__desgcategorie')
            .annotate(
                nombre_livraisons=Count('id'),
                total_qtecmd=Sum('commande__qtecmd'),
                total_qtelivree=Sum('qtelivrer')
            )
            .annotate(
                total_qte_restante=F('total_qtecmd') - F('total_qtelivree')
            )
            .order_by('produits__categorie__desgcategorie')
        )

        # ================= TOTAUX PAR PRODUIT =================
        total_par_produit = (
            livraisons_qs
            .values(
                'produits_id',
                'produits__desgprod',
                'produits__categorie__desgcategorie'
            )
            .annotate(
                nombre_livraisons=Count('id'),
                total_qtecmd=Sum('commande__qtecmd'),
                total_qtelivree=Sum('qtelivrer')
            )
            .annotate(
                total_qte_restante=F('total_qtecmd') - F('total_qtelivree')
            )
            .order_by('produits__desgprod')
        )

        # ================= PAGINATION =================
        listes_livraisons_filtre = pagination_liste(request, livraisons_qs)

    except Exception as ex:
        messages.warning(request, f"Erreur lors du filtrage : {ex}")
        listes_livraisons_filtre = []
        total_livraison = 0
        total_qtecmd = 0
        total_quantite_livrer = 0
        total_quantite_restante = 0
        total_par_categorie = []
        total_par_produit = []

    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_livraisons_filtre": listes_livraisons_filtre,

        # Totaux globaux (tfoot)
        "total_livraison": total_livraison,
        "total_qtecmd": total_qtecmd,
        "total_quantite_livrer": total_quantite_livrer,
        "total_quantite_restante": total_quantite_restante,

        # Récapitulatifs
        "total_par_categorie": total_par_categorie,
        "total_par_produit": total_par_produit,
    }

    return render(
        request,
        "gestion_produits/livraisons/listes_livraisons.html",
        context
    )

#================================================================================================
# Fonction pour afficher la liste des ventes
#================================================================================================
@login_required
def listes_des_ventes(request):
    try:
        # ================= LIGNES DE VENTE =================
        lignes = (
            LigneVente.objects
            .select_related('vente', 'produit', 'produit__categorie')
            .order_by('-id')
        )
        total_vendus = LigneVente.objects.aggregate(
            total=Sum('quantite')
        )['total'] or 0
        
        total_ventes = lignes.count()
        total_montant_ventes = 0
        benefice_global = 0
        #benefice = 0
        listes_ventes = []

        for ligne in lignes:

            # Calcul du bénéfice
            #ligne.benefice = benefice

            # Mise à jour des totaux
            benefice_global += ligne.benefice
            total_montant_ventes += ligne.sous_total

            listes_ventes.append(ligne)
            
        # ================= TOTAL PAR CATÉGORIE =================
        total_par_categorie = (
            lignes
            .values('produit__categorie__desgcategorie')
            .annotate(
                total_montant=Sum('sous_total'),
                total_quantite=Sum('quantite'),
                total_vendu=Sum('quantite'),
            )
            .order_by('produit__categorie__desgcategorie')
        )
                # Total par produit
        total_par_produit = (
            lignes
            .values('produit__desgprod')
            .annotate(
                    total_quantite=Sum('quantite'),
                    total_montant=Sum('sous_total')
                )
                .order_by('produit__desgprod')
            )

        listes_ventes = pagination_lis(request, listes_ventes)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des ventes : {str(ex)}")
        listes_ventes = []
        total_ventes = 0
        total_montant_ventes = 0
        benefice_global = 0
        #benefice = 0
        total_vendus = 0
        total_par_categorie = []
        total_par_produit = []

    # ================= CONTEXT =================
    context = {
        'listes_ventes': listes_ventes,
        'total_ventes': total_ventes,
        'total_montant_ventes': total_montant_ventes,
        'benefice_global': benefice_global,
        'total_par_categorie': total_par_categorie,
        'total_vendus' : total_vendus,
        'total_par_produit' : total_par_produit,
    }
    return render(
        request,"gestion_produits/ventes/listes_ventes.html",context)

#================================================================================================
# Fonction pour afficher la liste des commandes éffectuées
#================================================================================================
@login_required
def listes_des_commandes(request):
    total_commande = 0
    listes_commandes = []
    total_par_categorie = []
    total_par_produit = []
    total_quantite = 0
    try:
        # ------------------ LISTE DES COMMANDES ------------------
        listes_commandes_qs = Commandes.objects.select_related(
            'produits', 'produits__categorie'
        ).order_by('-id')
        total_commande = listes_commandes_qs.count()

        # ------------------ TOTAL PAR CATEGORIE ------------------
        total_par_categorie = (
            listes_commandes_qs
            .values('produits__categorie__desgcategorie')
            .annotate(
                nombre_commandes=Count('id', distinct=True),
                total_quantite=Sum('qtecmd'),
                valeur_commandes=Sum(F('qtecmd') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie')
        )

        # ------------------ TOTAL PAR PRODUIT ------------------
        total_par_produit = (
            listes_commandes_qs
            .values('produits__categorie__desgcategorie', 'produits__refprod', 'produits__desgprod')
            .annotate(
                nombre_commandes=Count('id', distinct=True),
                total_quantite=Sum('qtecmd'),
                valeur_commandes=Sum(F('qtecmd') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie', 'produits__refprod')
        )

        # ------------------ TOTAL GLOBAUX ------------------
        total_quantite = listes_commandes_qs.aggregate(total_qte=Sum('qtecmd'))['total_qte'] or 0

        # ------------------ PAGINATION ------------------
        if 'pagination_lis' in globals():
            listes_commandes = pagination_lis(request, listes_commandes_qs)
        else:
            listes_commandes = listes_commandes_qs

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des commandes : {str(ex)} !")
        listes_commandes = []
        total_commande = 0
        total_par_produit = []
        total_par_categorie = []
        total_quantite = 0

    context = {
        'listes_commandes': listes_commandes,
        'total_commande': total_commande,
        'total_par_categorie': total_par_categorie,
        'total_par_produit': total_par_produit,
        'total_quantite': total_quantite,
    }

    return render(request, "gestion_produits/commandes/listes_commandes.html", context)

#================================================================================================
# Fonction pour filter la liste des commandes selon un intervalle de date donnée
#================================================================================================
@login_required
def filtrer_listes_commandes(request):
    """
    Filtre les commandes selon la date
    (DateField : une date ou intervalle)
    """
    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    total_commande = 0
    total_par_categorie = []
    total_par_produit = []
    listes_commandes_filtre = []

    try:
        # ================== QUERYSET DE BASE ==================
        commande_qs = Commandes.objects.select_related(
            'produits', 'produits__categorie'
        ).order_by("-datecmd")

        # ================== FILTRE PAR DATE ==================
        if date_debut and date_fin:
            commande_qs = commande_qs.filter(datecmd__range=[date_debut, date_fin])
        elif date_debut:
            commande_qs = commande_qs.filter(datecmd=date_debut)
        elif date_fin:
            commande_qs = commande_qs.filter(datecmd=date_fin)

        # ================== TOTAL DES COMMANDES ==================
        total_commande = commande_qs.count()

        # ================== TOTAL PAR CATEGORIE ==================
        total_par_categorie = commande_qs.values(
            'produits__categorie__desgcategorie'
        ).annotate(
            nombre_commandes=Count('id', distinct=True),
            total_quantite=Sum('qtecmd'),
            valeur_commandes=Sum(F('qtecmd') * F('produits__pu'))
        ).order_by('produits__categorie__desgcategorie')

        # ================== TOTAL PAR PRODUIT ==================
        total_par_produit = commande_qs.values(
            'produits__categorie__desgcategorie',
            'produits__refprod',
            'produits__desgprod'
        ).annotate(
            nombre_commandes=Count('id', distinct=True),
            total_quantite=Sum('qtecmd'),
            valeur_commandes=Sum(F('qtecmd') * F('produits__pu'))
        ).order_by('produits__categorie__desgcategorie', 'produits__refprod')

        # ================== TOTAL GLOBAUX ==================
        total_quantite = commande_qs.aggregate(total_qte=Sum('qtecmd'))['total_qte'] or 0

        # ================== PAGINATION ==================
        if 'pagination_liste' in globals():
            listes_commandes_filtre = pagination_liste(request, commande_qs)
        else:
            listes_commandes_filtre = commande_qs

    except Exception as ex:
        messages.warning(request, f"Erreur lors du filtrage des commandes : {str(ex)}")
        listes_commandes_filtre = []
        total_commande = 0
        total_par_categorie = []
        total_par_produit = []
        total_quantite = 0

    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_commandes_filtre": listes_commandes_filtre,
        "total_commande": total_commande,
        "total_par_categorie": total_par_categorie,
        "total_par_produit": total_par_produit,
        "total_quantite": total_quantite,
    }

    return render(request, "gestion_produits/commandes/listes_commandes.html", context)

#================================================================================================
# Fonction pour filter la liste des vente selon un intervalle de date donnée
#================================================================================================
@login_required
def filtrer_listes_ventes(request):
    """
    Filtre les ventes selon la date
    et affiche les statistiques + pagination
    """

    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    total_ventes = 0
    total_montant_ventes = 0
    benefice_global = 0
    total_par_categorie = []
    listes_ventes_filtre = []
    total_vendus = 0

    try:
        # ================== QUERYSET DE BASE ==================
        ventes_qs = LigneVente.objects.select_related(
            'produit',
            'vente',
            'produit__categorie'
        ).order_by("-vente__date_vente")

        # ================== FILTRE PAR DATE ==================
        if date_debut and date_fin:
            ventes_qs = ventes_qs.filter(
                vente__date_vente__date__range=[date_debut, date_fin]
            )

        # ================== TOTAL DES VENTES ==================
        total_ventes = ventes_qs.count()
        
        total_vendus = LigneVente.objects.aggregate(
            total=Sum('quantite')
        )['total'] or 0

        # ================== TOTAL PAR CATÉGORIE ==================
        total_par_categorie = ventes_qs.values(
            'produit__categorie__desgcategorie'
        ).annotate(
            total_quantite=Sum('quantite'),
            total_montant=Sum('sous_total')
        ).order_by('produit__categorie__desgcategorie')
        
        # Total par produit
        total_par_produit = (
            ventes_qs
            .values('produit__desgprod')
            .annotate(
                    total_quantite=Sum('quantite'),
                    total_montant=Sum('sous_total')
                )
                .order_by('produit__desgprod')
            )

        # ================== CALCUL BÉNÉFICE ==================
        for ligne in ventes_qs:

            benefice_global += ligne.benefice
            total_montant_ventes += ligne.sous_total

        # ================== PAGINATION ==================
        listes_ventes_filtre = pagination_lis(request, ventes_qs)

    except Exception as ex:
        messages.warning(
            request,
            f"Erreur lors du filtrage des ventes : {str(ex)}"
        )
        # Initialisation en cas d'erreur
        listes_ventes_filtre = []
        total_ventes = 0
        total_montant_ventes = 0
        benefice_global = 0
        total_vendus = 0
        total_par_categorie = []
        total_par_produit = []

    # ================== CONTEXT ==================
    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_ventes_filtre": listes_ventes_filtre,
        "total_ventes": total_ventes,
        "benefice_global": benefice_global,
        "total_par_categorie": total_par_categorie,
        "total_montant_ventes": total_montant_ventes,
        'total_par_produit' : total_par_produit,
        'total_vendus' : total_vendus,
    }

    return render(
        request,
        "gestion_produits/ventes/listes_ventes.html",
        context
    )

#================================================================================================
# Fonction pour consulter un produit donnée
#================================================================================================
@login_required
def consulter_produit(request, id):
    try:
        produit = Produits.objects.get(id=id)
    except Produits.DoesNotExist:
        messages.error(request, "Produit introuvable.")
        return redirect('produits:listes_produits')

    context = {
        'produit': produit,
    }
    return render(request, 'gestion_produits/consulter_informations_eleves.html', context)

#================================================================================================
# Fonction pour editer un produit pour provoir le modifier
#================================================================================================
@login_required
def editer_produit(request, id):
    try:
        produit = Produits.objects.get(id=id)
    except Produits.DoesNotExist:
        messages.error(request, "Produit introuvable.")
        return redirect('produits:listes_produits')

    context = {
        'produit': produit,
        'categories': CategorieProduit.objects.all(),
    }
    return render(request, 'gestion_produits/modifier_produits.html', context)

#================================================================================================
# Fonction pour modifier un produit donnée
#================================================================================================
@login_required
def modifier_produit(request, id):
    try:
        produit = Produits.objects.get(id=id)
    except Produits.DoesNotExist:
        messages.error(request, "Produit introuvable.")
        return redirect('produits:editer_produit')

    categories = CategorieProduit.objects.all()

    if request.method == 'POST':
        produit.desgprod = request.POST.get('desgprod')
        produit.qtestock = request.POST.get('qtestock')
        produit.seuil = request.POST.get('seuil')
        produit.pu = request.POST.get('pu')
        produit.prix_en_gros = request.POST.get('prix_en_gros')

        categorie_id = request.POST.get('categorie')
        produit.categorie_id = categorie_id

        if 'photoprod' in request.FILES:
            produit.photoprod = request.FILES['photoprod']

        produit.save()

        messages.success(request, "Produit modifié avec succès !")
        return redirect('produits:listes_produits')

    context = {
        'produit': produit,
        'categories': categories,
    }
    return render(request, 'gestion_produits/modifier_produits.html', context)

#================================================================================================
# Fonction gérer les réferenes de produit
#================================================================================================
def generate_references(prefix, date_str, numero):
    return f"{prefix}{date_str}{str(numero).zfill(4)}"

#================================================================================================
# Fonction pour ajouter un nouveau produit
#================================================================================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def nouveau_produit(request):
    prefix = "PROD"
    date_str = datetime.now().strftime("%Y%m%d")

    # Trouver le dernier produit du jour pour incrémentation
    last_produit = Produits.objects.filter(
        refprod__startswith=f"{prefix}{date_str}"
    ).order_by('-refprod').first()

    if last_produit:
        dernier_numero = int(last_produit.refprod[-4:])
    else:
        dernier_numero = 0

    # Première référence à afficher
    ref_generee = generate_references(prefix, date_str, dernier_numero + 1)

    # ------- TRAITEMENT DU FORMULAIRE -------
    if request.method == 'POST':

        refs = request.POST.getlist("refprod[]")
        noms = request.POST.getlist("desgprod[]")
        pus = request.POST.getlist("pu[]")
        pu_engros = request.POST.getlist("pu_engros[]")
        categories = request.POST.getlist("categorie[]")
        photos = request.FILES.getlist("photoprod[]")

        total = len(noms)
        success_count = 0

        # Vérification cohérence des listes
        if not (len(refs) == len(noms) == len(pus) == len(pu_engros) == len(categories)):
            messages.error(request, "Erreur : Données incomplètes dans le formulaire.")
            return redirect("produits:nouveau_produit")

        for i in range(total):
            ref = refs[i]
            desg = noms[i]
            try:
                pu = int(pus[i])
                pu_engro_val = int(pu_engros[i])
            except ValueError:
                messages.error(request, f"Erreur : Le prix doit être un nombre pour le produit {desg}.")
                return redirect("produits:nouveau_produit")

            cat_id = categories[i]
            photo = photos[i] if i < len(photos) else None

            # Vérifier doublons
            if Produits.objects.filter(refprod=ref).exists():
                messages.error(request, f"La Référence {ref} existe déjà.")
                return redirect('produits:nouveau_produit')
            elif Produits.objects.filter(desgprod=desg).exists():
                messages.error(request, f"Le nom du Produit {desg} existe déjà.")
                return redirect('produits:nouveau_produit')

            # Création du produit
            try:
                Produits.objects.create(
                    refprod=ref,
                    desgprod=desg,
                    pu=pu,
                    prix_en_gros=pu_engro_val,
                    photoprod=photo,
                    categorie_id=cat_id
                )
                success_count += 1
            except Exception as e:
                messages.error(request, f"Erreur lors de l’enregistrement de {ref} : {e}")

        if success_count > 0:
            messages.success(request, f"{success_count} produit(s) enregistré(s) avec succès.")
            return redirect("produits:listes_produits")

    # ------- CONTEXTE POUR LE TEMPLATE -------
    context = {
        "ref_generee": ref_generee,
        "categorie_choices": CategorieProduit.objects.all(),
    }

    return render(request, "gestion_produits/nouveau_produit.html", context)

#================================================================================================
# Fonction pour ajouter un nouveau produit
#================================================================================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur')

def ajouter_stock_multiple(request):
    produits = Produits.objects.all()

    if request.method == "POST":
        produit_ids = request.POST.getlist("produit[]")
        qte_list = request.POST.getlist("qtestock[]")
        seuil_list = request.POST.getlist("seuil[]")

        success_count = 0

        for i in range(len(produit_ids)):
            try:
                produit = Produits.objects.get(id=int(produit_ids[i]))

                qte = int(qte_list[i])
                seuil = int(seuil_list[i])

                # Création ou mise à jour du stock unique
                stock, created = StockProduit.objects.get_or_create(
                    produit=produit,
                    defaults={
                        "qtestock": qte,
                        "seuil": seuil
                    }
                )

                if not created:
                    stock.qtestock += qte
                    stock.seuil = seuil
                    stock.save()

                success_count += 1

            except Produits.DoesNotExist:
                messages.error(
                    request,
                    f"Produit introuvable à la ligne {i + 1}."
                )

            except ValueError:
                messages.error(
                    request,
                    f"Quantité ou seuil invalide pour le produit sélectionné."
                )

            except Exception as e:
                messages.error(
                    request,
                    f"Erreur pour le produit {produit.refprod} : {e}"
                )

        messages.success(
            request,
            f"{success_count} produit(s) enregistré(s) / mis à jour avec succès."
        )

        return redirect("produits:ajouter_stock_multiple")

    return render(
        request,
        "gestion_produits/stocks/ajouter_stock_multiple.html",
        {
            "produits": produits,
        }
    )


#================================================================================================
# Fonction pour imprimer la listes des produits
#================================================================================================
@login_required
def listes_produits_impression(request):

    listes_produits = Produits.objects.all()

    total_quantite_restante = StockProduit.objects.aggregate(
            total=Sum('qtestock')
        )['total'] or 0
    total_produit = listes_produits.count()
        # ================= TOTAL PAR CATÉGORIE =================
    total_par_categorie = (
        listes_produits
            .values('categorie__desgcategorie')
            .annotate(
                nombre_produits=Count('id', distinct=True),
                quantite_stock=Sum('stocks__qtestock'),
            )
            .order_by('categorie__desgcategorie')
        )

    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_produits' : listes_produits,
        'total_par_categorie' : total_par_categorie,
        'total_produit' : total_produit,
        'total_quantite_restante' : total_quantite_restante,
    }
    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_produits.html',
        context
    )

#================================================================================================
# Fonction pour imprimer la listes des Catégories Produits
#================================================================================================
@login_required
def listes_categorie_produits_impression(request):
    listes_categorie_produits = []
    try:
        listes_categorie_produits = CategorieProduit.objects.all()
    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des données {str(ex)}")
    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_categorie_produits' : listes_categorie_produits,
    }
    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_categorieproduits.html',
        context
    )

#================================================================================================
# Fonction pour afficher formulaire de choix de dates de saisie pour l'impression
#================================================================================================
@login_required
def choix_par_dates_ventes_impression(request):
    return render(request, 'gestion_produits/impression_listes/fiches_choix_impression_ventes.html')

#================================================================================================
# Fonction pour imprimer la listes des ventes
#================================================================================================
@login_required
def listes_ventes_impression(request):
    # Récupération des dates depuis POST
    date_debut = request.POST.get('date_debut')
    date_fin = request.POST.get('date_fin')

    lignes = LigneVente.objects.none()
    total_par_categorie = []
    total_par_produit = []
    total_quantite_produits = 0
    total_montant_produits = 0
    total_quantite_categories = 0
    total_montant_categories = 0
    benefice_global = 0

    if date_debut and date_fin:
        try:
            lignes = (
                LigneVente.objects
                .select_related('vente', 'produit', 'produit__categorie')
                .filter(date_saisie__range=[date_debut, date_fin])
                .order_by('-id')
            )

            # Total par catégorie
            total_par_categorie = (
                lignes
                .values('produit__categorie__desgcategorie')
                .annotate(
                    total_montant=Sum('sous_total'),
                    total_quantite=Sum('quantite')
                )
                .order_by('produit__categorie__desgcategorie')
            )

            # Totaux globaux par catégorie
            total_quantite_categories = sum(c['total_quantite'] for c in total_par_categorie)
            total_montant_categories = sum(c['total_montant'] for c in total_par_categorie)

            # Total par produit
            total_par_produit = (
                lignes
                .values('produit__desgprod')
                .annotate(
                    total_montant=Sum('sous_total'),
                    total_quantite=Sum('quantite')
                )
                .order_by('produit__desgprod')
            )

            # Totaux globaux par produit
            total_quantite_produits = sum(p['total_quantite'] for p in total_par_produit)
            total_montant_produits = sum(p['total_montant'] for p in total_par_produit)

        except Exception as ex:
            messages.warning(request, f"Erreur lors de la récupération des ventes : {str(ex)}")

    # Regrouper les lignes par vente
    ventes_dict = {}
    for ligne in lignes:
        code_vente = ligne.vente.code
        if code_vente not in ventes_dict:
            ventes_dict[code_vente] = {
                'vente': ligne.vente,
                'lignes': [],
                'total_vente': 0,
                'benefice_vente': 0
            }

        # Calcul du bénéfice pour chaque ligne
        benefice_ligne = (ligne.pu_reduction - ligne.produit.prix_en_gros) * ligne.quantite
        ligne.benefice = benefice_ligne

        ventes_dict[code_vente]['lignes'].append(ligne)
        ventes_dict[code_vente]['total_vente'] += ligne.sous_total
        ventes_dict[code_vente]['benefice_vente'] += benefice_ligne

        benefice_global += benefice_ligne

    ventes_liste = list(ventes_dict.values())
    nom_entreprise = Entreprise.objects.first()  # Si plusieurs, prendre le premier

    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'ventes_liste': ventes_liste,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'benefice_global': benefice_global,
        'total_par_categorie': total_par_categorie,
        'total_par_produit': total_par_produit,
        'total_quantite_produits': total_quantite_produits,
        'total_montant_produits': total_montant_produits,
        'total_quantite_categories': total_quantite_categories,
        'total_montant_categories': total_montant_categories,
    }

    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_ventes.html',
        context
    )

#================================================================================================
# Fonction pour afficher le formulaire de choix de dates de saisie pour l'impression des Commandes
#================================================================================================
@login_required
def choix_par_dates_commandes_impression(request):
    return render(request, 'gestion_produits/impression_listes/fiches_choix_impression_commandes.html')

#================================================================================================
# Fonction pour imprimer la listes des Commandes
#================================================================================================
@login_required

def listes_commandes_impression(request):

    date_debut = request.POST.get('date_debut')
    date_fin = request.POST.get('date_fin')

    try:
        # ================= COMMANDES FILTRÉES =================
        listes_commandes = Commandes.objects.select_related(
            'produits',
            'produits__categorie'
        ).filter(
            datecmd__range=[date_debut, date_fin]
        ).order_by('-datecmd')

        # ================= TOTAUX GLOBAUX =================
        total_commandes = listes_commandes.count()

        total_quantite = listes_commandes.aggregate(
            total=Sum('qtecmd')
        )['total'] or 0

        total_valeur = listes_commandes.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('qtecmd') * F('produits__pu'),
                    output_field=IntegerField()
                )
            )
        )['total'] or 0

        # ================= TOTAL PAR CATÉGORIE =================
        total_par_categorie = (
            listes_commandes
            .values('produits__categorie__desgcategorie')
            .annotate(
                nombre_commandes=Count('id'),
                total_quantite=Sum('qtecmd'),
                valeur_commandes=Sum(
                    ExpressionWrapper(
                        F('qtecmd') * F('produits__pu'),
                        output_field=IntegerField()
                    )
                )
            )
            .order_by('produits__categorie__desgcategorie')
        )

        # ================= TOTAL PAR PRODUIT =================
        total_par_produit = (
            listes_commandes
            .values(
                'produits__refprod',
                'produits__desgprod',
                'produits__categorie__desgcategorie'
            )
            .annotate(
                nombre_commandes=Count('id'),
                total_quantite=Sum('qtecmd'),
                valeur_commandes=Sum(
                    ExpressionWrapper(
                        F('qtecmd') * F('produits__pu'),
                        output_field=IntegerField()
                    )
                )
            )
            .order_by('produits__desgprod')
        )

    except Exception as ex:
        messages.warning(request, f"Erreur impression commandes : {ex}")
        listes_commandes = []
        total_par_categorie = []
        total_par_produit = []
        total_commandes = 0
        total_quantite = 0
        total_valeur = 0

    nom_entreprise = Entreprise.objects.first()

    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'date_debut': date_debut,
        'date_fin': date_fin,

        # données
        'listes_commandes': listes_commandes,
        'total_par_categorie': total_par_categorie,
        'total_par_produit': total_par_produit,

        # totaux globaux
        'total_commandes': total_commandes,
        'total_quantite': total_quantite,
        'total_valeur': total_valeur,
    }

    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_commandes.html',
        context
    )


#================================================================================================
# Fonction pour imprimer la listes des Produits en Stocks
#================================================================================================
@login_required
def listes_stocks_impression(request):

    listes_produits = StockProduit.objects.all()
    total_stocks = StockProduit.objects.aggregate(
        total=Sum('qtestock')
        )['total'] or 0
    total_produit = listes_produits.count()
            # ================= TOTAL PAR CATÉGORIE =================
    total_par_categorie = (
        StockProduit.objects
        .values(
            'produit__categorie__desgcategorie',
            'produit__pu',
            )
        .annotate(
            nombre_produits=Count('produit', distinct=True),
            quantite_stock=Sum('qtestock'),
            total_stock=Sum('qtestock'),
            valeur_stock=Sum(
                F('qtestock') * F('produit__pu')
            ),
        )
        .order_by('produit__categorie__desgcategorie')
    )

    # ================= CONTEXT =================
    nom_entreprise = Entreprise.objects.first()

    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_produits': listes_produits,
        'total_par_categorie' : total_par_categorie,
        'total_produit' : total_produit,
        'total_stocks' : total_stocks,
    }

    return render(
        request,
        'gestion_produits/impression_listes/stock/apercue_avant_impression_listes_stocks.html',
        context
    )

#================================================================================================
# Fonction pour afficher le formulaire de choix de dates de saisie pour l'impression des Livraisons
#================================================================================================
@login_required
def choix_par_dates_livraisons_impression(request):
    return render(request, 'gestion_produits/impression_listes/fiches_choix_impression_livraisons.html')

#================================================================================================
# Fonction pour imprimer la listes des Livraisons
#================================================================================================
@login_required
def listes_livraisons_impression(request):

    try:
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin')

        # ================= QUERYSET DE BASE =================
        livraisons_qs = LivraisonsProduits.objects.select_related(
            'commande',
            'produits',
            'produits__categorie'
        )

        # ================= FILTRE PAR DATE =================
        if date_debut and date_fin:
            livraisons_qs = livraisons_qs.filter(
                datelivrer__range=[date_debut, date_fin]
            )
        elif date_debut:
            livraisons_qs = livraisons_qs.filter(datelivrer=date_debut)
        elif date_fin:
            livraisons_qs = livraisons_qs.filter(datelivrer=date_fin)

        livraisons_qs = livraisons_qs.order_by('-id')

        # ================= QTE LIVRÉE PAR COMMANDE =================
        livraison_par_commande = (
            livraisons_qs
            .values('commande')
            .annotate(total_livree=Sum('qtelivrer'))
        )

        livraison_map = {
            l['commande']: l['total_livree'] for l in livraison_par_commande
        }

        # ================= LISTE + QTE RESTANTE =================
        total_quantite_restante = 0
        for l in livraisons_qs:
            total_livree = livraison_map.get(l.commande_id, 0)
            l.qte_restante = max(l.commande.qtecmd - total_livree, 0)
            total_quantite_restante += l.qte_restante

        # ================= TOTAUX GLOBAUX =================
        total_livraison = livraisons_qs.count()

        total_qtecmd = livraisons_qs.aggregate(
            total=Sum('commande__qtecmd')
        )['total'] or 0

        total_quantite_livrer = livraisons_qs.aggregate(
            total=Sum('qtelivrer')
        )['total'] or 0

        total_quantite_restante = livraisons_qs.aggregate(
            total=Sum(F('commande__qtecmd') - F('qtelivrer'))
        )['total'] or 0

        # ================= TOTAUX PAR CATÉGORIE =================
        total_par_categorie = (
            livraisons_qs
            .values('produits__categorie__desgcategorie')
            .annotate(
                nombre_livraisons=Count('id'),
                total_qtecmd=Sum('commande__qtecmd'),
                total_qtelivree=Sum('qtelivrer')
            )
            .annotate(
                total_qte_restante=F('total_qtecmd') - F('total_qtelivree')
            )
            .order_by('produits__categorie__desgcategorie')
        )

        # ================= TOTAUX PAR PRODUIT =================
        total_par_produit = (
            livraisons_qs
            .values(
                'produits_id',
                'produits__desgprod',
                'produits__refprod',
                'produits__categorie__desgcategorie'
            )
            .annotate(
                nombre_livraisons=Count('id'),
                total_qtecmd=Sum('commande__qtecmd'),
                total_qtelivree=Sum('qtelivrer')
            )
            .annotate(
                total_qte_restante=F('total_qtecmd') - F('total_qtelivree')
            )
            .order_by('produits__desgprod')
        )

    except Exception as ex:
        messages.warning(request, f"Erreur impression livraisons : {ex}")
        livraisons_qs = []
        total_livraison = 0
        total_qtecmd = 0
        total_quantite_livrer = 0
        total_quantite_restante = 0
        total_par_categorie = []
        total_par_produit = []

    # ================= CONTEXTE =================
    nom_entreprise = Entreprise.objects.first()

    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),

        'listes_livraisons': livraisons_qs,
        'date_debut': date_debut,
        'date_fin': date_fin,

        # Totaux
        'total_livraison': total_livraison,
        'total_qtecmd': total_qtecmd,
        'total_quantite_livrer': total_quantite_livrer,
        'total_quantite_restante': total_quantite_restante,

        # Récaps
        'total_par_categorie': total_par_categorie,
        'total_par_produit': total_par_produit,
    }

    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_livraisons.html',
        context
    )

#================================================================================================
# Fonction pour afficher le formulaire de formulaire d'exportation des données
#================================================================================================
@login_required
def confirmation_exportation_vente(request):
    
    return render(request, 'gestion_produits/exportation/confirmation_exportation_ventes.html')

#=============================================================================================
# Fonction pour exporter les données des ventes
#==============================================================================================
@login_required
def export_ventes_excel(request):
    # 1. Récupérer toutes les ventes
    ventes = VenteProduit.objects.prefetch_related('lignes', 'lignes__produit').all()

    # 2. Créer un fichier Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liste des Ventes"

    # 3. Ajouter les en-têtes
    headers = [
        "Code Vente", "Date Vente", "Produit", "Quantité",
        "Prix Unitaire", "Sous-Total", "Total Vente"
    ]
    for col_num, header in enumerate(headers, 1):
        ws[f"{get_column_letter(col_num)}1"] = header

    # 4. Insérer les données ligne par ligne
    ligne = 2
    for vente in ventes:
        for lv in vente.lignes.all():  # Chaque produit de la vente
            ws[f"A{ligne}"] = vente.code
            ws[f"B{ligne}"] = vente.date_vente.strftime("%d/%m/%Y %H:%M")
            ws[f"C{ligne}"] = lv.produit.desgprod
            ws[f"D{ligne}"] = lv.quantite
            ws[f"E{ligne}"] = lv.prix
            ws[f"F{ligne}"] = lv.sous_total
            ws[f"G{ligne}"] = vente.total
            ligne += 1

    # 5. Ajuster la largeur des colonnes
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 25

    # 6. Retourner le fichier Excel en téléchargement
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename=ventes_produits.xlsx'
    wb.save(response)
    return response

#================================================================================================
# Fonction pour afficher le formulaire de formulaire d'exportation des données
#================================================================================================
@login_required
def confirmation_exportation_categorie(request):
    return render(request, 'gestion_produits/exportation/confirmation_exportation_categories.html')

#=============================================================================================
# Fonction pour exporter les données des Catégories Produits
#==============================================================================================
@login_required
def export_categories_excel(request):
    # 1️⃣ Récupération des catégorie (OPTIMISÉ)
    categories = CategorieProduit.objects.all()

    # 2️⃣ Création du fichier Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liste des Catégories Produits"

    # 3️⃣ En-têtes
    headers = [
        "Catégorie",
        "Description",
        "Date de Mise à Jour"
    ]

    for col_num, header in enumerate(headers, 1):
        ws[f"{get_column_letter(col_num)}1"] = header

    # 4️⃣ Données
    ligne = 2
    for elems in categories:
        ws[f"A{ligne}"] = elems.desgcategorie
        ws[f"B{ligne}"] = elems.description
        ws[f"C{ligne}"] = elems.date_maj.strftime("%d/%m/%Y %H:%M") if elems.date_maj else ""
        ligne += 1

    # 5️⃣ Ajuster largeur colonnes
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 25

    # 6️⃣ Téléchargement
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename=liste_categories_produits.xlsx'
    wb.save(response)
    return response

#================================================================================================
# Fonction pour afficher le formulaire de formulaire d'exportation des données
#================================================================================================
@login_required
def confirmation_exportation_produits(request):
    
    return render(request, 'gestion_produits/exportation/confirmation_exportation_produits.html')

#=============================================================================================
# Fonction pour exporter les données des ventes
#==============================================================================================
@login_required
def export_produits_excel(request):
    # 1️⃣ Récupération des produits + catégorie (OPTIMISÉ)
    produits = Produits.objects.select_related('categorie').all()

    # 2️⃣ Création du fichier Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liste des Produits"

    # 3️⃣ En-têtes
    headers = [
        "Catégorie",
        "Référence Produit",
        "Désignation",
        "Prix Unitaire",
        "Quantité en Stock",
        "Seuil",
        "Date de Mise à Jour"
    ]

    for col_num, header in enumerate(headers, 1):
        ws[f"{get_column_letter(col_num)}1"] = header

    # 4️⃣ Données
    ligne = 2
    for produit in produits:
        ws[f"A{ligne}"] = produit.categorie.desgcategorie if produit.categorie else ""
        ws[f"B{ligne}"] = produit.refprod
        ws[f"C{ligne}"] = produit.desgprod
        ws[f"D{ligne}"] = produit.pu
        ws[f"E{ligne}"] = produit.qtestock
        ws[f"F{ligne}"] = produit.seuil
        ws[f"G{ligne}"] = produit.date_maj.strftime("%d/%m/%Y %H:%M") if produit.date_maj else ""
        ligne += 1

    # 5️⃣ Ajuster largeur colonnes
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 25

    # 6️⃣ Téléchargement
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename=liste_produits.xlsx'
    wb.save(response)
    return response

#==============================================================================================

#================================================================================================
# Fonction pour afficher le formulaire de formulaire d'exportation des données
#================================================================================================
@login_required
def confirmation_exportation_commande(request):
    
    return render(request, 'gestion_produits/exportation/confirmation_exportation_commandes.html')

def export_commandes_excel(request):
    # 1. Récupérer les commandes avec les produits et catégories
    commandes = Commandes.objects.select_related(
        'produits',
        'produits__categorie'
    ).order_by('-datecmd')

    # 2. Créer le fichier Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liste des Commandes"

    # 3. En-têtes
    headers = [
        "N° Commande",
        "Date Commande",
        "Produit",
        "Catégorie",
        "Quantité Commandée",
        "Fournisseur",
        "Téléphone Fournisseur"
    ]

    for col, header in enumerate(headers, 1):
        ws[f"{get_column_letter(col)}1"] = header

    # 4. Remplir les lignes
    ligne = 2
    for cmd in commandes:
        ws[f"A{ligne}"] = cmd.numcmd
        ws[f"B{ligne}"] = cmd.datecmd.strftime("%d/%m/%Y")
        ws[f"C{ligne}"] = cmd.produits.desgprod
        ws[f"D{ligne}"] = (
            cmd.produits.categorie.desgcategorie
            if cmd.produits.categorie else ""
        )
        ws[f"E{ligne}"] = cmd.qtecmd
        ws[f"F{ligne}"] = cmd.nom_complet_fournisseur or ""
        ws[f"G{ligne}"] = cmd.telephone_fournisseur or ""
        ligne += 1

    # 5. Ajuster largeur colonnes
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 25

    # 6. Réponse HTTP
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = (
        f'attachment; filename=commandes_{timezone.now().date()}.xlsx'
    )

    wb.save(response)
    return response

#================================================================================================
# Fonction pour afficher le formulaire de formulaire d'exportation des données
#================================================================================================
@login_required
def confirmation_exportation_livraison(request):
    
    return render(request, 'gestion_produits/exportation/confirmation_exportation_livraisons.html')


def export_livraisons_excel(request):
    # Récupérer toutes les livraisons avec les produits
    livraisons = LivraisonsProduits.objects.select_related('produits').all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Livraisons"

    # En-têtes incluant les infos commande
    headers = [
        "Produit", "Quantité Livrée", "Date Livraison", "Statut",
        "Numéro Commande", "Quantité Commandée",
        "Fournisseur", "Téléphone Fournisseur", "Adresse Fournisseur"
    ]

    for col, header in enumerate(headers, 1):
        ws[f"{get_column_letter(col)}1"] = header

    ligne = 2
    for l in livraisons:
        # Tenter de récupérer la commande associée au produit et à la date de livraison
        commande = Commandes.objects.filter(
            produits=l.produits
        ).order_by('-datecmd').first()  # On prend la dernière commande pour ce produit

        ws[f"A{ligne}"] = l.produits.desgprod
        ws[f"B{ligne}"] = l.qtelivrer
        ws[f"C{ligne}"] = l.datelivrer.strftime("%d/%m/%Y")
        ws[f"D{ligne}"] = l.statuts

        if commande:
            ws[f"E{ligne}"] = commande.numcmd
            ws[f"F{ligne}"] = commande.qtecmd
            ws[f"G{ligne}"] = commande.nom_complet_fournisseur
            ws[f"H{ligne}"] = commande.telephone_fournisseur
            ws[f"I{ligne}"] = commande.adresse_fournisseur
        else:
            ws[f"E{ligne}"] = ""
            ws[f"F{ligne}"] = ""
            ws[f"G{ligne}"] = ""
            ws[f"H{ligne}"] = ""
            ws[f"I{ligne}"] = ""

        ligne += 1

    # Ajuster la largeur des colonnes
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 25

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=livraisons.xlsx"
    wb.save(response)
    return response

#================================================================================================
