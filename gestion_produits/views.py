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

from gestion_notifications.models import Notification
from .utils import *
from gestion_audit.views import enregistrer_audit
from .models import * 
from django.core.mail import EmailMessage
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum, F, Count, Q
from openpyxl import Workbook

from django.db import transaction
from collections import defaultdict
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
def ajouter_categorie(request):
    if request.method == 'POST':
        nom = request.POST.get('nom')
        description = request.POST.get('description')

        # Vérifier le nom obligatoire
        if not nom:
            messages.error(request, "Le nom de la catégorie est obligatoire.")
            return redirect('produits:ajouter_categorie')

        CategorieProduit.objects.create(
            desgcategorie=nom,
            description=description
        )

        messages.success(request, "Catégorie ajoutée avec succès !")
        return redirect('produits:listes_categorie')

    return render(request, 'gestion_produits/listes_categorie.html')

#================================================================================================
# Fonction pour éffectuer un approvisionnement
#================================================================================================
@login_required
def approvisionner_produits(request):
    produits = Produits.objects.all()
    produits_data = []

    # Préparer les données pour le template
    for p in produits:
        stock_entrepot = p.stocks.filter(entrepot__isnull=False).first()
        stock_magasin = p.stocks.filter(magasin__isnull=False).first()

        produits_data.append({
            "produit": p,
            "stock_entrepot": stock_entrepot.qtestock if stock_entrepot else 0,
            "seuil_entrepot": stock_entrepot.seuil if stock_entrepot else 0,
            "stock_magasin": stock_magasin.qtestock if stock_magasin else 0,
            "stock_entrepot_instance": stock_entrepot,
            "stock_magasin_instance": stock_magasin,
        })

    if request.method == "POST":
        try:
            qte = int(request.POST.get("quantite", 0))
        except ValueError:
            qte = 0

        if qte <= 0:
            messages.error(request, "La quantité doit être supérieure à zéro.")
            return redirect("produits:approvisionner_produits")

        approvisionnements = []  # Pour l’email

        # Transfert global
        for p in produits_data:
            se = p["stock_entrepot_instance"]
            sm = p["stock_magasin_instance"]

            if not se or se.qtestock <= 0:
                continue

            # Créer stock magasin si absent
            if not sm:
                sm = StockProduit.objects.create(
                    produit=p["produit"],
                    entrepot=None,
                    magasin=Magasin.objects.first(),  # ou ton magasin par défaut
                    qtestock=0,
                    seuil=0
                )

            transfert = min(qte, se.qtestock)

            se.qtestock = F('qtestock') - transfert
            sm.qtestock = F('qtestock') + transfert
            se.save()
            sm.save()

            approvisionnements.append({
                "produit": p["produit"].desgprod,
                "quantite": transfert,
                "entrepot_restant": se.qtestock - transfert if isinstance(se.qtestock, int) else "",
            })

        # =================== EMAIL ADMIN ===================
        if approvisionnements:
            try:
                sujet = "Approvisionnement Entrepôt → Magasin"
                contenu = f"""
                Nouvel approvisionnement effectué.

                Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}
                Utilisateur : {request.user}

                Détails :
                """
                for a in approvisionnements:
                    contenu += f"- Produit : {a['produit']} | Quantité transférée : {a['quantite']}\n"

                email = EmailMessage(
                    sujet,
                    contenu,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL]
                )
                email.send(fail_silently=False)

            except Exception as e:
                logger.error(f"Erreur email approvisionnement : {str(e)}")
                messages.warning(request, "Approvisionnement effectué, mais email non envoyé.")

        messages.success(request, "Approvisionnement global effectué avec succès !")
        return redirect("produits:listes_produits_stock")

    return render(
        request,
        "gestion_produits/approvisionnement/approvisionner_produit.html",
        {"produits_data": produits_data}
    )

#================================================================================================
# Fonction pour éffectuer une nouvelle vente
#================================================================================================
@login_required

def vendre_produit(request):
    produits = Produits.objects.all()
    
    # Pour chaque produit, récupérer le stock
    for p in produits:
        stock = StockProduit.objects.filter(produit=p).first()
        p.qtestock_magasin = stock.qtestock if stock else 0

    if request.method == "POST":
        ids = request.POST.getlist("produit_id[]")
        quantites = request.POST.getlist("quantite[]")
        reductions = request.POST.getlist("reduction[]")

        nom_complet = request.POST.get("nom_complet_client")
        telephone = request.POST.get("telephone_client")
        adresse = request.POST.get("adresse_client")

        if not nom_complet or not telephone or not adresse:
            messages.error(request, "Veuillez renseigner le nom complet, le téléphone et l'adresse du client.")
            return redirect("produits:vendre_produit")

        total_general = 0
        lignes = []

        # Boucle sécurisée pour préparer la vente
        for prod_id, qte_str, red_str in zip(ids, quantites, reductions):
            try:
                prod = Produits.objects.get(id=prod_id)
            except Produits.DoesNotExist:
                continue

            try:
                qte = int(str(qte_str).replace(',', '').replace(' ', '') or 0)
                reduction = int(str(red_str).replace(',', '').replace(' ', '') or 0)
            except ValueError:
                messages.error(request, f"Quantité ou réduction invalide pour {prod.desgprod}")
                return redirect("produits:vendre_produit")

            if qte < 0:
                messages.error(request, f"La quantité est inférieure à 0 pour {prod.desgprod}. Disponible : {prod.qtestock_magasin}")
                return redirect("produits:vendre_produit")

            # Vérification stock
            stock = StockProduit.objects.filter(produit=prod).first()
            if not stock or stock.qtestock < qte:
                messages.error(request, f"Stock insuffisant pour {prod.desgprod}. Disponible : {stock.qtestock if stock else 0}")
                return redirect("produits:vendre_produit")

            if reduction > prod.pu:
                messages.error(request, f"La réduction pour {prod.desgprod} ne peut pas dépasser le prix unitaire ({prod.pu})")
                return redirect("produits:vendre_produit")

            sous_total = qte * (prod.pu - reduction)
            total_general += sous_total

            if not qte == 0 :
                lignes.append((prod, qte, prod.pu, reduction, sous_total))

        if not lignes:
            messages.error(request, "Aucun produit sélectionné pour la vente.")
            return redirect("produits:vendre_produit")

        # Création vente globale
        code = f"VENTE{timezone.now().strftime('%Y%m%d%H%M%S')}"
        vente = VenteProduit.objects.create(
            code=code,
            total=total_general,
            utilisateur=request.user,
            nom_complet_client=nom_complet,
            telclt_client=telephone,
            adresseclt_client=adresse
        )

        # Création lignes de vente et mise à jour stock
        for prod, qte, pu, reduction, st in lignes:
            LigneVente.objects.create(
                vente=vente,
                produit=prod,
                quantite=qte,
                prix=pu,
                sous_total=st,
                montant_reduction=reduction,
            )
            stock = StockProduit.objects.filter(produit=prod).first()
            stock.qtestock -= qte
            stock.save()

        # Envoi email admin (optionnel)
        try:
            if not hasattr(settings, 'DEFAULT_FROM_EMAIL') or not hasattr(settings, 'ADMIN_EMAIL'):
                raise ValueError("Paramètres email non définis")

            sujet = f"Nouvelle vente - Code {vente.code}"
            contenu = f"Vente par {request.user}\nClient : {nom_complet}\nTéléphone : {telephone}\nAdresse : {adresse}\nTotal : {total_general:,} GNF\nDétails :\n"
            for prod, qte, pu, reduction, st in lignes:
                contenu += f"- {prod.desgprod} | Qté : {qte} | PU : {pu:,} | Réduction : {reduction:,} | Sous-total : {st:,}\n"

            email = EmailMessage(sujet, contenu, settings.ADMIN_EMAIL, [settings.DEFAULT_FROM_EMAIL])
            email.send(fail_silently=False)

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email pour la vente {vente.code}: {str(e)}")
            messages.warning(request, f"Vente enregistrée mais email non envoyé : {str(e)}")

        messages.success(request, "Vente enregistrée avec succès !")
        return redirect("produits:recu_vente_global", vente_code=vente.code)

    return render(request, "gestion_produits/ventes/nouvelle_vente.html", {"produits": produits})

#================================================================================================
# Fonction pour afficher l'historique des ventes par date
#================================================================================================
@login_required
def historique_ventes(request):
    # Récupérer toutes les ventes avec utilisateur et lignes + produits
    ventes = (
        VenteProduit.objects
        .select_related("utilisateur")
        .prefetch_related("lignes__produit__categorie")
        .order_by("-date_vente")
    )

    ventes_par_date = defaultdict(list)

    # Regrouper les ventes par date
    for vente in ventes:
        date = vente.date_vente.date()
        ventes_par_date[date].append(vente)

    historique = []
    # Calculs par date
    for date, ventes_du_jour in ventes_par_date.items():
        total_montant = 0
        total_quantite = 0
        categories_vendues = set()
        total_profit_jour = 0

        for vente in ventes_du_jour:
            vente.total_profit = 0
            for ligne in vente.lignes.all():
                # Calcul exact du profit par ligne
                prix_achat = getattr(ligne.produit, "prix_en_gros", 0)
                ligne.profit = (ligne.produit.pu - prix_achat) * ligne.quantite

                # Accumulation
                vente.total_profit += ligne.profit
                total_profit_jour += ligne.profit
                total_quantite += ligne.quantite

                # Ajouter la catégorie du produit (assurer qu'elle existe)
                if ligne.produit.categorie:
                    categories_vendues.add(ligne.produit.categorie.id)

            total_montant += vente.total

        historique.append({
            "date": date,
            "ventes": ventes_du_jour,
            "total_montant": total_montant,
            "total_quantite": total_quantite,          # Nombre exact de produits vendus
            "total_categories": len(categories_vendues), # Nombre de catégories différentes vendues
            "total_profit": total_profit_jour,         # Bénéfice exact du jour
        })
    context = {
        "historique": historique
    }
    return render(
        request,
        "gestion_produits/ventes/historique_ventes.html",context)

#================================================================================================
# Fonction pour afficher l'historique des commandes et livraisons par date
#================================================================================================
@login_required 
def historique_commandes_livraisons(request):
    """
    Vue pour afficher l'historique des commandes et livraisons
    avec totaux calculés côté Python.
    """

    historique = []
    commandes = Commandes.objects.all().order_by('-datecmd')

    total_commandes = 0
    total_livrees = 0
    total_restantes = 0

    for cmd in commandes:
        livraisons = LivraisonsProduits.objects.filter(commande=cmd).order_by('datelivrer')
        total_livree = livraisons.aggregate(total=Sum('qtelivrer'))['total'] or 0
        qte_restante = cmd.qtecmd - total_livree

        historique.append({
            'commande': cmd,
            'livraisons': livraisons,
            'total_livree': total_livree,
            'qte_restante': qte_restante
        })

        # 🔹 Totaux pour le footer
        total_commandes += cmd.qtecmd
        total_livrees += total_livree
        total_restantes += qte_restante

    context = {
        'historique': historique,
        'total_commandes': total_commandes,
        'total_livrees': total_livrees,
        'total_restantes': total_restantes
    }

    return render(request, 'gestion_produits/livraisons/historique_commandes_livraisons.html', context)

#================================================================================================
# Fonction pour éffectuer une nouvelle commande
#================================================================================================
@login_required
def nouvelle_commande(request):
    produits = Produits.objects.all()

    # Préparer les données pour le template
    produits_data = []
    for p in produits:
        produits_data.append({
            "produit": p,
        })
        
    if request.method == "POST":
        ids = request.POST.getlist("produit_id[]")
        quantites = request.POST.getlist("quantite[]")
        
        # Informations du Fournisseur
        nom_complet_fournisseur = request.POST.get("nom_complet_fournisseur")
        telephone_fournisseur = request.POST.get("telephone_fournisseur")
        adresse_fournisseur = request.POST.get("adresse_fournisseur")

        if not ids or not quantites:
            messages.error(request, "Aucun produit sélectionné.")
            return redirect("produits:nouvelle_commande")

        lignes = []
        total_general = 0
        numcmd = f"CMD{timezone.now().strftime('%Y%m%d%H%M%S')}"

        for i in range(len(ids)):
            try:
                prod = Produits.objects.get(id=ids[i])
                qte = int(quantites[i])
            except Produits.DoesNotExist:
                messages.error(request, "Produit introuvable.")
                return redirect("produits:nouvelle_commande")
            except ValueError:
                messages.error(request, f"Quantité invalide pour {prod.desgprod}.")
                return redirect("produits:nouvelle_commande")

            if qte <= 0:
                continue  # Ignorer les produits avec 0 quantité

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

        # Email à l'admin
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

            email = EmailMessage(
                sujet,
                contenu,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
            )
            email.send()
        except Exception as e:
            messages.warning(request, f"Commande enregistrée mais email non envoyé : {str(e)}")

        messages.success(request, f"Commande {numcmd} enregistrée avec succès !")
        return redirect("produits:listes_des_commandes")

    context = {
        'produits_data': produits_data,
    }
    return render(request, "gestion_produits/commandes/nouvelle_commande.html", context)

#================================================================================================
# Fonction pour éffectuer une receptin de livraisons des commandes
#================================================================================================
@login_required

@transaction.atomic

def reception_livraison(request):
    """
    Vue pour réceptionner les commandes avec livraison,
    l'utilisateur peut saisir 0 pour refuser certaines livraisons.
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
                continue

            try:
                qte_livree = int(qte_livree_list[i])
            except ValueError:
                qte_livree = 0  # Si non numérique, considérer 0

            total_livree = (
                LivraisonsProduits.objects
                .filter(commande=cmd)
                .aggregate(total=Sum("qtelivrer"))["total"] or 0
            )
            qte_restante = cmd.qtecmd - total_livree

            # Ignorer si quantité saisie = 0 ou supérieure à la quantité restante
            if qte_livree <= 0:
                continue
            if qte_livree > qte_restante:
                messages.warning(
                    request,
                    f"{cmd.produits.desgprod} : quantité restante {qte_restante}."
                )
                continue

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
                # Ajouter la quantité livrée à la valeur existante
                stock.qtestock = stock.qtestock + qte_livree
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
                ).send()
            except Exception as e:
                messages.warning(request, f"Email non envoyé : {e}")

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

    # --- lignes et calculs ---
    lignes = LigneVente.objects.filter(vente=vente)
    if not lignes.exists():
        messages.error(request, "Aucun produit trouvé pour cette vente.")
        return redirect("produits:listes_des_ventes")

    total = sum((Decimal(l.sous_total) for l in lignes))

    # --- génération QR code ---
    qr_data = (
        f"Reçu Vente : {vente.code}\n"
        f"Date : {vente.date_vente}\n"
        f"Nombre d'articles : {lignes.count()}\n"
        f"Total : {total} GNF\n"
        f"Nom du Client : {vente.nom_complet_client}\n"
        f"Téléphone du Client : {vente.telclt_client}\n"
        f"Adresse du Client : {vente.adresseclt_client}\n"
    )

    qr = qrcode.QRCode(
        version = 1,
        error_correction = qrcode.constants.ERROR_CORRECT_H,
        box_size = 10,
        border = 4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    context = {
        "vente": vente,
        "lignes": lignes,
        "total": total,
        "today": now(),
        "qr_code_base64": qr_code_base64,
        "entreprise": Entreprise.objects.first(),
    }

    return render(request, "gestion_produits/recu_ventes/recu_vente_global.html", context)

#================================================================================================
# Fonction pour afficher la listes des catégories
#================================================================================================
@login_required
def listes_categorie(request):
    try:
        listes_categories = CategorieProduit.objects.all().order_by('-id')
        total_categories = listes_categories.count()
    except Exception as ex:
        messages.warning(request, f"Erreur lors du chargement des catégories : {str(ex)}")
        listes_categories = []
        total_categories = 0

    context = {
        'liste_categories': listes_categories,
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

        try:
            categorie = CategorieProduit.objects.get(id=cat_id)
            categorie.desgcategorie = nom
            categorie.description = description
            categorie.save()

            messages.success(request, "Catégorie modifiée avec succès !")
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
        print(f"valeur : {cat_id}")

        try:
            categorie = CategorieProduit.objects.get(id=cat_id)

            # Vérifier si un produit utilise cette catégorie
            if Produits.objects.filter(categorie = cat_id).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer cette catégorie car elle est déjà utilisée par un produit. "
                    "Veuillez d'abord supprimer les produits associés."
                )
                return redirect('produits:listes_categorie')

            # ----- Préparer l'ancienne valeur pour l'audit -----
            ancienne_valeur = {
                "id": categorie.id,
                "nom_categorie": categorie.desgcategorie,
                "description": categorie.description if hasattr(categorie, 'description') else ""
            }

            # ----- Supprimer la catégorie -----
            categorie.delete()

            # ----- Audit : suppression -----
            enregistrer_audit(
                utilisateur = request.user,
                action = "Suppression catégorie",
                table = "CategorieProduit",
                ancienne_valeur = ancienne_valeur,
                nouvelle_valeur = None
            )

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
    if request.method == 'POST':
        prod_id = request.POST.get('id_supprimer')

        try:
            produit = Produits.objects.get(id=prod_id)

            # Vérifier si le produit est lié à des ventes
            if LigneVente.objects.filter(
                produit = prod_id
                ).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer ce produit car il est déjà utilisé dans une vente. "
                    "Veuillez d'abord supprimer les ventes associées."
                )
                return redirect('produits:listes_produits')
            
            # Vérifier si le produit est lié à des Stocks
            if StockProduit.objects.filter(
                produit = prod_id
                ).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer ce produit car il est déjà utilisé dans un Stock. "
                    "Veuillez d'abord supprimer les Stocks Produits."
                )
                return redirect('produits:listes_produits')

            # Vérifier si le produit est lié à des commandes
            if Commandes.objects.filter(
                produits = prod_id
                ).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer ce produit car il est déjà utilisé dans une commande. "
                    "Veuillez d'abord supprimer les commandes associées."
                )
                return redirect('produits:listes_produits')


            # Vérifier si le produit est lié à des Livraisons
            if LivraisonsProduits.objects.filter(
                produits = prod_id
                ).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer ce produit car il est déjà utilisé dans une Livraisons. "
                    "Veuillez d'abord supprimer les Livraisons."
                )
                return redirect('produits:listes_produits')

            # ----- Ancienne valeur pour l'audit -----
            ancienne_valeur = {
                "id": produit.id,
                "refprod": produit.refprod if hasattr(produit, "refprod") else "",
                "desgprod": produit.desgprod,
                "pu": float(produit.pu),
                "categorie": str(produit.categorie) if produit.categorie else None,
            }

            # ----- Suppression -----
            produit.delete()

            # ----- Audit -----
            enregistrer_audit(
                utilisateur = request.user,
                action="Suppression produit",
                table="Produits",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
            )

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
    if request.method == 'POST':
        stock_id = request.POST.get('id_supprimer')

        try:
            stock = StockProduit.objects.select_related(
                'produit', 'entrepot', 'magasin'
            ).get(id=stock_id)

            # ===== ANCIENNE VALEUR (AUDIT) =====
            ancienne_valeur = {
                "id_stock": stock.id,
                "produit": stock.produit.desgprod,
                "reference": stock.produit.refprod,
                "quantite": stock.qtestock,
                "seuil": stock.seuil,
                "entrepot": str(stock.entrepot) if stock.entrepot else "N/A",
                "magasin": str(stock.magasin) if stock.magasin else "N/A",
            }
            # ===== SUPPRESSION =====
            stock.delete()
            
            # ===== AUDIT =====
            enregistrer_audit(
                utilisateur = str(request.user),
                action ="Suppression stock produit",
                table="StockProduit",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
            )

            # ===== NOTIFICATION =====
            Notification.objects.create(
                destinataire = request.user,
                titre="🗑 Suppression de stock",
                message = (
                    f"Le stock du produit {ancienne_valeur['produit']} "
                    f"a été supprimé avec succès."
                )
            )

            # ===== ENVOI EMAIL ADMIN =====
            try:
                sujet = "🗑 Suppression d’un stock produit"
                contenu = f"""
            Une suppression de stock a été effectuée.

            Utilisateur : {request.user}
            Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}

            Détails du stock supprimé :
            - Produit : {ancienne_valeur['produit']}
            - Référence : {ancienne_valeur['reference']}
            - Quantité : {ancienne_valeur['quantite']}
            - Seuil : {ancienne_valeur['seuil']}
            - Entrepôt : {ancienne_valeur['entrepot']}
            - Magasin : {ancienne_valeur['magasin']}
            """
                email = EmailMessage(
                    sujet,
                    contenu,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL]
                )
                email.send(fail_silently=False)
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
    if request.method == 'POST':
        commande_id = request.POST.get('id_supprimer')

        if not commande_id:
            messages.warning(request, "Aucune commande sélectionnée pour suppression.")
            return redirect('produits:listes_des_commandes')
        try:
            commande = get_object_or_404(Commandes, id=commande_id)

            # Vérifier si cette commande est liée à des produits
            if Produits.objects.filter(commande=commande).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer cette commande car elle contient des produits. "
                    "Veuillez d'abord supprimer les produits associés."
                )
                return redirect('produits:listes_des_commandes')

            # ----- Préparer ancienne valeur pour l'audit -----
            ancienne_valeur = {
                "Num Commande": commande.numcmd,
                "Produit": commande.produits.desgprod if commande.produits else "",
                "Qté commandée": commande.qtecmd,
                "Fournisseur": commande.nom_complet_fournisseur,
                "Utilisateur connecté": request.user.get_full_name(),
            }

            # ----- Suppression de la commande -----
            commande.delete()

            # ----- Enregistrement de l'audit -----
            enregistrer_audit(
                utilisateur=request.user,
                action="Suppression",
                table="Commandes",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
            )

            # ===== Notification interne =====
            Notification.objects.create(
                destinataire=request.user,
                titre="🗑 Suppression de commande",
                message=f"La commande {ancienne_valeur['Num Commande']} a été supprimée."
            )

            # ===== Envoi email admin =====
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

        except Commandes.DoesNotExist:
            messages.error(request, "Commande introuvable.")
        except Exception as ex:
            messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

        return redirect('produits:listes_des_commandes')

#================================================================================================
# Fonction pour supprimer une livraisons donnée
#================================================================================================
@login_required
def supprimer_livraisons(request):
    if request.method == 'POST':
        livraison_id = request.POST.get('id_supprimer')

        try:
            with transaction.atomic():

                # 1️⃣ Récupérer la livraison
                livraison = get_object_or_404(LivraisonsProduits, id=livraison_id)

                produit = livraison.produits
                quantite = livraison.qtelivrer
                numlivrer = livraison.numlivrer

                # 2️⃣ Restaurer le stock ENTREPÔT
                stock_entrepot = StockProduit.objects.filter(
                    produit=produit,
                    entrepot__isnull=False,
                    magasin__isnull=True
                ).first()

                if stock_entrepot:
                    stock_entrepot.qtestock = F('qtestock') - quantite
                    stock_entrepot.save()

                # 3️⃣ Ancienne valeur (audit)
                ancienne_valeur = {
                    "id_livraison": livraison.id,
                    "numlivrer": numlivrer,
                    "produit": produit.desgprod,
                    "quantite_livree": quantite,
                    "date": str(livraison.datelivrer),
                }

                # 4️⃣ Suppression
                livraison.delete()

                # 5️⃣ Audit
                enregistrer_audit(
                    utilisateur=request.user,
                    action="Suppression livraison produit",
                    table="LivraisonsProduits",
                    ancienne_valeur=ancienne_valeur,
                    nouvelle_valeur=None
                )

            # ===== NOTIFICATION =====
            Notification.objects.create(
                destinataire=request.user,
                titre="🗑 Suppression de livraison",
                message=(
                    f"La livraison {numlivrer} du produit "
                    f"{produit.desgprod} a été supprimée."
                )
            )

            # ===== EMAIL ADMIN =====
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
                    "Livraison supprimée mais email non envoyé."
                )

            messages.success(
                request,
                "Livraison supprimée avec succès. Stock mis à jour ✔"
            )

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
        messages.warning(request, "Méthode non autorisée pour la suppression.")
        return redirect('produits:listes_des_ventes')

    vente_id = request.POST.get('id_supprimer')
    if not vente_id:
        messages.warning(request, "⚠️ Aucun vente sélectionnée pour suppression.")
        return redirect('produits:listes_des_ventes')

    try:
        with transaction.atomic():
            # 1️⃣ Récupérer la vente
            vente = get_object_or_404(VenteProduit, id=vente_id)
            code_vente = vente.code

            # 2️⃣ Récupérer toutes les lignes liées
            lignes = LigneVente.objects.select_related('produit').filter(vente=vente)

            # 3️⃣ Restaurer le stock
            for ligne in lignes:
                produit = ligne.produit

                # Stock magasin
                stock_magasin = produit.stocks.filter(magasin__isnull=False).first()
                if stock_magasin:
                    stock_magasin.qtestock += ligne.quantite
                    stock_magasin.save(update_fields=['qtestock'])

                # Stock entrepôt
                stock_entrepot = produit.stocks.filter(entrepot__isnull=False).first()
                if stock_entrepot:
                    stock_entrepot.qtestock += ligne.quantite
                    stock_entrepot.save(update_fields=['qtestock'])

            # 4️⃣ Enregistrement de l'audit
            ancienne_valeur = {
                "Vente": code_vente,
                "Produits": [{ 
                    "Produit": ligne.produit.desgprod,
                    "Qté": ligne.quantite,
                    "Sous-total": ligne.sous_total
                } for ligne in lignes],
                "Utilisateur connecté": request.user.get_full_name(),
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

            # 6️⃣ Notification interne
            Notification.objects.create(
                destinataire=request.user,
                titre=f"🗑 Suppression de vente {code_vente}",
                message=f"La vente {code_vente} a été supprimée avec succès. Les stocks ont été restaurés automatiquement."
            )

            # 7️⃣ Envoi email à l'administrateur
            try:
                sujet = f"🗑 Suppression d'une vente - {code_vente}"
                contenu = f"""
Une vente a été supprimée.

Code vente : {code_vente}
Utilisateur : {request.user.get_full_name()}
Date : {timezone.now().strftime('%d/%m/%Y %H:%M')}

Les stocks ont été restaurés automatiquement.
"""
                email = EmailMessage(
                    sujet,
                    contenu,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL]
                )
                email.send(fail_silently=False)
            except Exception as e:
                logger.error(f"Erreur email suppression vente : {str(e)}")
                messages.warning(
                    request,
                    "Vente supprimée mais l'email d'information n'a pas pu être envoyé."
                )

        messages.success(request, f"Vente {code_vente} supprimée avec succès. Stocks restaurés ✔")

    except Exception as ex:
        messages.error(request, f"⚠️ Erreur lors de la suppression de la vente : {str(ex)}")

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

        # Pagination
        listes_produits = pagination_liste(request, produits)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des produits : {str(ex)}")
        listes_produits = []
        total_produit = 0
        total_par_categorie = []

    context = {
        'listes_produits': listes_produits,
        'total_produit': total_produit,
        'total_par_categorie': total_par_categorie,  # 👈 clé importante
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

        total_produit = listes_stock.count()

        # ================= TOTAL PAR CATÉGORIE =================
        total_par_categorie = (
            StockProduit.objects
            .values('produit__categorie__desgcategorie')
            .annotate(
                nombre_produits=Count('produit', distinct=True),
                quantite_stock=Sum('qtestock'),
                valeur_stock=Sum(
                    F('qtestock') * F('produit__pu')
                ),
            )
            .order_by('produit__categorie__desgcategorie')
        )

        # Pagination si ta fonction existe
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
    }

    return render(
        request,
        "gestion_produits/stocks/lites_produits_stocks.html",
        context
    )

#================================================================================================
# Fonction pour filter la liste des produits en stocks selon un intervalle de date donnée
#================================================================================================
@login_required
def filtrer_listes_produits_stock(request):
    """
    Filtre les produits en stock selon la date
    et affiche les statistiques + pagination
    """

    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    total_produit = 0
    total_par_categorie = []
    listes_produits = []

    try:
        # ================== QUERYSET DE BASE ==================
        produits_qs = (
            StockProduit.objects
            .select_related(
                'produit',
                'produit__categorie'
            )
            .order_by('-id')
        )

        # ================== FILTRE PAR DATE ==================
        if date_debut and date_fin:
            produits_qs = produits_qs.filter(
                date_maj__date__range=[date_debut, date_fin]
            )
        elif date_debut:
            produits_qs = produits_qs.filter(
                date_maj__date=date_debut
            )
        elif date_fin:
            produits_qs = produits_qs.filter(
                date_maj__date=date_fin
            )

        # ================== TOTAL DES PRODUITS ==================
        total_produit = produits_qs.count()

        # ================== TOTAL PAR CATÉGORIE ==================
        total_par_categorie = (
            produits_qs
            .values('produit__categorie__desgcategorie')
            .annotate(
                nombre_produits=Count('produit', distinct=True),
                quantite_stock=Sum('qtestock'),
                valeur_stock=Sum(
                    F('qtestock') * F('produit__pu')
                ),
            )
            .order_by('produit__categorie__desgcategorie')
        )

        # ================== PAGINATION ==================
        listes_produits = pagination_liste(request, produits_qs)

    except Exception as ex:
        messages.warning(
            request,
            f"Erreur lors du filtrage des produits en stock : {str(ex)}"
        )
        return redirect('produits:listes_produits_stock')

    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_produits": listes_produits,
        "total_produit": total_produit,
        "total_par_categorie": total_par_categorie,
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
        # ------------------ LISTE DES LIVRAISONS ------------------
        listes_livraisons = LivraisonsProduits.objects.select_related(
            'commande', 'produits', 'produits__categorie'
        ).order_by('-id')

        total_livraison = listes_livraisons.count()

        # Calcul des quantités livrées et restantes
        for elem in listes_livraisons:
            total_livree = (
                LivraisonsProduits.objects.filter(
                    produits=elem.produits,
                    commande=elem.commande
                ).aggregate(total=Sum('qtelivrer'))['total'] or 0
            )
            elem.total_livree = total_livree
            elem.qte_restante = elem.commande.qtecmd - total_livree

        # ------------------ TOTAL PAR CATEGORIE ------------------
        total_par_categorie = (
            LivraisonsProduits.objects
            .values('produits__categorie__desgcategorie')
            .annotate(
                nombre_livraisons=Count('id', distinct=True),
                total_qtelivree=Sum('qtelivrer'),
                valeur_livraison=Sum(F('qtelivrer') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie')
        )

        # ------------------ TOTAL PAR PRODUIT ------------------
        total_par_produit = (
            LivraisonsProduits.objects
            .values('produits__categorie__desgcategorie', 'produits__refprod', 'produits__desgprod')
            .annotate(
                nombre_livraisons=Count('id', distinct=True),
                total_qtelivree=Sum('qtelivrer'),
                valeur_livraison=Sum(F('qtelivrer') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie', 'produits__refprod')
        )

        # ------------------ PAGINATION ------------------
        listes_livraisons = pagination_liste(request, listes_livraisons)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des livraisons : {str(ex)} !")
        listes_livraisons = []
        total_livraison = 0
        total_par_categorie = []
        total_par_produit = []

    context = {
        'listes_livraisons': listes_livraisons,
        'total_livraison': total_livraison,
        'total_par_categorie': total_par_categorie,
        'total_par_produit': total_par_produit
    }

    return render(request, "gestion_produits/livraisons/listes_livraisons.html", context)

#================================================================================================
# Fonction pour filtrer la liste des livraisons par date
#================================================================================================
@login_required

def filtrer_listes_livraisons(request):
    """
    Filtre les livraisons selon la date.
    La page affiche soit une date unique, soit un intervalle de dates.
    """

    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    total_livraison = 0
    total_par_categorie = []
    listes_livraisons_filtre = []

    try:
        # ================== QUERYSET DE BASE ==================
        livraison_qs = LivraisonsProduits.objects.select_related(
            'produits',
            'produits__categorie',
            'commande'
        ).order_by("-datelivrer")

        # ================== FILTRE PAR DATE ==================
        if date_debut and date_fin:
            livraison_qs = livraison_qs.filter(datelivrer__range=[date_debut, date_fin])
        elif date_debut:
            livraison_qs = livraison_qs.filter(datelivrer=date_debut)
        elif date_fin:
            livraison_qs = livraison_qs.filter(datelivrer=date_fin)

        # ================== TOTAL DES LIVRAISONS ==================
        total_livraison = livraison_qs.count()

        # ================== TOTAL PAR CATÉGORIE ==================
        total_par_categorie = (
            livraison_qs
            .values('produits__categorie__desgcategorie')
            .annotate(total_quantite=Sum('qtelivrer'))
            .order_by('produits__categorie__desgcategorie')
        )

        # ================== PAGINATION ==================
        listes_livraisons_filtre = pagination_liste(request, livraison_qs)

    except Exception as ex:
        messages.warning(request, f"Erreur lors du filtrage des livraisons : {str(ex)}")

    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_livraisons_filtre": listes_livraisons_filtre,
        "total_livraison": total_livraison,
        "total_par_categorie": total_par_categorie,
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

        total_ventes = lignes.count()
        total_montant_ventes = 0
        benefice_global = 0
        listes_ventes = []

        for ligne in lignes:
            # Prix d'achat par produit
            prix_achat = getattr(ligne.produit, 'pu_achat', 0) or 0

            # Calcul du bénéfice
            benefice = ligne.sous_total - (prix_achat * ligne.quantite)
            ligne.benefice = benefice

            # Mise à jour des totaux
            benefice_global += benefice
            total_montant_ventes += ligne.sous_total

            listes_ventes.append(ligne)

        # ================= TOTAL PAR CATÉGORIE =================
        total_par_categorie = (
            lignes
            .values('produit__categorie__desgcategorie')
            .annotate(
                total_montant=Sum('sous_total'),
                total_quantite=Sum('quantite')
            )
            .order_by('produit__categorie__desgcategorie')
        )

        # Pagination des lignes de vente
        listes_ventes = pagination_lis(request, listes_ventes)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des ventes : {str(ex)}")
        listes_ventes = []
        total_ventes = 0
        total_montant_ventes = 0
        benefice_global = 0
        total_par_categorie = []

    # ================= CONTEXT =================
    context = {
        'listes_ventes': listes_ventes,
        'total_ventes': total_ventes,
        'total_montant_ventes': total_montant_ventes,
        'benefice_global': benefice_global,
        'total_par_categorie': total_par_categorie,
    }

    return render(
        request,
        "gestion_produits/ventes/listes_ventes.html",
        context
    )

#================================================================================================
# Fonction pour afficher la liste des commandes éffectuées
#================================================================================================
@login_required
def listes_des_commandes(request):
    try:
        # ------------------ LISTE DES COMMANDES ------------------
        listes_commandes = Commandes.objects.select_related('produits').order_by('-id')
        total_commandes = listes_commandes.count()
        
        # Pagination
        listes_commandes = pagination_lis(request, listes_commandes)
        
        # ------------------ TOTAL PAR CATEGORIE ------------------
        total_par_categorie = (
            Commandes.objects
            .values('produits__categorie__desgcategorie')
            .annotate(
                nombre_commandes=Count('id', distinct=True),
                total_quantite=Sum('qtecmd'),
                valeur_commandes=Sum(F('qtecmd') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie'))
                # ------------------ TOTAL PAR PRODUIT ------------------
        total_par_produit = (
            Commandes.objects
            .values('produits__categorie__desgcategorie', 'produits__refprod', 'produits__desgprod')
            .annotate(
                nombre_commande=Count('id', distinct=True),
                total_qtecmd=Sum('qtecmd'),
                valeur_cmd =Sum(F('qtecmd') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie', 'produits__refprod'))


    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des commandes : {str(ex)} !")
        listes_commandes = []
        total_commandes = 0
        total_par_produit = []
        total_par_categorie = []

    context = {
        'listes_commandes': listes_commandes,
        'total_commandes': total_commandes,
        'total_par_categorie': total_par_categorie,
        'total_par_produit' : total_par_produit,
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
    listes_commandes_filtre = []

    try:
        # ================== QUERYSET DE BASE ==================
        commande_qs = Commandes.objects.prefetch_related(
            'produits',
            'produits__categorie'
        ).order_by("-datecmd")

        # ================== FILTRE PAR DATE (CORRECT DateField) ==================
        if date_debut and date_fin:
            commande_qs = commande_qs.filter(
                datecmd__range=[date_debut, date_fin]
            )
        elif date_debut:
            commande_qs = commande_qs.filter(
                datecmd=date_debut
            )
        elif date_fin:
            commande_qs = commande_qs.filter(
                datecmd=date_fin
            )

        # ================== TOTAL DES COMMANDES ==================
        total_commande = commande_qs.count()

        # ================== TOTAL PAR CATÉGORIE ==================
        total_par_categorie = commande_qs.values(
            'produits__categorie__desgcategorie'
        ).annotate(
            total_quantite=Sum('qtecmd')
        ).order_by('produits__categorie__desgcategorie')

        listes_commandes_filtre = pagination_liste(request, commande_qs)

    except Exception as ex:
        messages.warning(
            request,
            f"Erreur lors du filtrage des commandes : {str(ex)}"
        )

    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_commandes_filtre": listes_commandes_filtre,
        "total_commande": total_commande,
        "total_par_categorie": total_par_categorie,
    }
    return render( request,
        "gestion_produits/commandes/listes_commandes.html",context)

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

        # ================== TOTAL PAR CATÉGORIE ==================
        total_par_categorie = ventes_qs.values(
            'produit__categorie__desgcategorie'
        ).annotate(
            total_quantite=Sum('quantite'),
            total_montant=Sum('sous_total')
        ).order_by('produit__categorie__desgcategorie')

        # ================== CALCUL BÉNÉFICE ==================
        for ligne in ventes_qs:
            prix_achat = getattr(ligne.produit, 'prix_en_gros', 0) or 0
            benefice = ligne.sous_total - (prix_achat * ligne.quantite)
            ligne.benefice = benefice

            benefice_global += benefice
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
        total_par_categorie = []

    # ================== CONTEXT ==================
    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_ventes_filtre": listes_ventes_filtre,
        "total_ventes": total_ventes,
        "benefice_global": benefice_global,
        "total_par_categorie": total_par_categorie,
        "total_montant_ventes": total_montant_ventes,
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
    
            # ================= TOTAL PAR CATÉGORIE =================
    total_par_categorie = (
        listes_produits
        .values('categorie__desgcategorie')
        .annotate(
            nombre_produits=Count('id', distinct=True),
            quantite_stock=Sum('stocks__qtestock'),
            valeur_stock=Sum(F('stocks__qtestock') * F('pu'))
            )
            .order_by('categorie__desgcategorie')
        )

    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_produits' : listes_produits,
        'total_par_categorie' : total_par_categorie,
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

    if date_debut and date_fin:
        try:
            # Queryset filtré
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

        except Exception as ex:
            messages.warning(request, f"Erreur lors de la récupération des ventes : {str(ex)}")

    # Regrouper les lignes par vente
    ventes_dict = {}
    benefice_global = 0

    for ligne in lignes:
        code_vente = ligne.vente.code
        if code_vente not in ventes_dict:
            ventes_dict[code_vente] = {
                'vente': ligne.vente,
                'lignes': [],
                'total_vente': 0,
                'benefice_vente': 0
            }

        prix_achat = getattr(ligne.produit, 'prix_en_gros', 0)
        benefice_ligne = ligne.sous_total - (prix_achat * ligne.quantite)
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
    
    try:
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin')
    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des dates : {str(ex)}")

    except ValueError as ve:
        messages.warning(request, f"Erreur de type de données : {str(ve)}")
        
    listes_commandes = Commandes.objects.filter(
        datecmd__range=[
            date_debut, date_fin])
            # ------------------ TOTAL PAR CATEGORIE ------------------
    total_par_categorie = (
        Commandes.objects
        .values('produits__categorie__desgcategorie')
        .annotate(
            nombre_commandes=Count('id', distinct=True),
            total_quantite=Sum('qtecmd'),
            valeur_commandes=Sum(F('qtecmd') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie')
        )
    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_commandes' : listes_commandes,
        'date_debut' : date_debut,
        'date_fin' : date_fin,
        'total_par_categorie' : total_par_categorie,
    }
    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_produits.html',
        context
    )

#================================================================================================
# Fonction pour afficher le formulaire de choix de dates de saisie pour l'impression des Stocks
#================================================================================================
@login_required
def choix_par_dates_stocks_impression(request):
    return render(request, 'gestion_produits/impression_listes/stock/fiches_choix_impression_stocks.html')

#================================================================================================
# Fonction pour imprimer la listes des Produits en Stocks
#================================================================================================
@login_required
def listes_stocks_impression(request):

    date_debut = None
    date_fin = None

    try:
        # Accepte POST ou GET
        date_debut_str = request.POST.get('date_debut') or request.GET.get('date_debut')
        date_fin_str = request.POST.get('date_fin') or request.GET.get('date_fin')

        if date_debut_str:
            date_debut = datetime.strptime(date_debut_str, "%Y-%m-%d")

        if date_fin_str:
            # Inclure toute la journée
            date_fin = datetime.strptime(date_fin_str, "%Y-%m-%d")
            date_fin = date_fin.replace(hour=23, minute=59, second=59)

    except ValueError:
        messages.warning(request, "Format de date invalide (AAAA-MM-JJ attendu).")

    # ================= FILTRAGE =================
    listes_produits = StockProduit.objects.all()

    if date_debut and date_fin:
        listes_produits = listes_produits.filter(
            date_maj__range=[date_debut, date_fin]
        )

    # ================= CONTEXT =================
    nom_entreprise = Entreprise.objects.first()

    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_produits': listes_produits,
        'date_debut': date_debut_str,
        'date_fin': date_fin_str,
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
    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des dates : {str(ex)}")

    except ValueError as ve:
        messages.warning(request, f"Erreur de type de données : {str(ve)}")
        
    listes_livraisons = LivraisonsProduits.objects.filter(
        datelivrer__range=[
            date_debut, date_fin])
    
    # Calcul des quantités livrées et restantes pour chaque livraison
    for elem in listes_livraisons:
        total_livree = LivraisonsProduits.objects.filter(
        produits=elem.produits,
        commande=elem.commande
        ).aggregate(total=Sum('qtelivrer'))['total'] or 0
        elem.total_livree = total_livree
        elem.qte_restante = elem.commande.qtecmd - total_livree

        # ------------------ TOTAL PAR CATEGORIE ------------------
    total_par_categorie = (
        LivraisonsProduits.objects
        .values('produits__categorie__desgcategorie')
        .annotate(
        nombre_livraisons=Count('id', distinct=True),
        total_qtelivree=Sum('qtelivrer'),
        valeur_livraison=Sum(F('qtelivrer') * F('produits__pu'))
        )
        .order_by('produits__categorie__desgcategorie')
        )

        # ------------------ TOTAL PAR PRODUIT ------------------
    total_par_produit = (
        LivraisonsProduits.objects
        .values('produits__categorie__desgcategorie', 'produits__refprod', 'produits__desgprod')
        .annotate(
            nombre_livraisons=Count('id', distinct=True),
            total_qtelivree=Sum('qtelivrer'),
            valeur_livraison=Sum(F('qtelivrer') * F('produits__pu'))
            )
            .order_by('produits__categorie__desgcategorie', 'produits__refprod')
        )

    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_livraisons' : listes_livraisons,
        'date_debut' : date_debut,
        'date_fin' : date_fin,
        'total_par_produit' : total_par_produit,
        'total_par_categorie' : total_par_categorie,
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
