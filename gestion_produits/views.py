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
from django.db.models import Sum, F
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
    
        # Pour chaque produit, récupérer le stock magasin
    for p in produits:
        stock_magasin = StockProduit.objects.filter(produit=p, magasin__isnull=False).first()
        p.qtestock_magasin = stock_magasin.qtestock if stock_magasin else 0

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
                messages.error(request, f"La quantité est inférieur à 0 pour {prod.desgprod}. Disponible : {stock_magasin.qtestock if stock_magasin else 0}")
                return redirect("produits:vendre_produit")

            # Vérification stock magasin uniquement
            stock_magasin = StockProduit.objects.filter(produit=prod, magasin__isnull=False).first()
            if not stock_magasin or stock_magasin.qtestock < qte:
                messages.error(request, f"Stock insuffisant en magasin pour {prod.desgprod}. Disponible : {stock_magasin.qtestock if stock_magasin else 0}, Veuillez approvisionnement la quantitée")
                return redirect("produits:vendre_produit")

            if reduction > prod.pu:
                messages.error(request, f"La réduction pour {prod.desgprod} ne peut pas dépasser le prix unitaire ({prod.pu})")
                return redirect("produits:vendre_produit")

            sous_total = qte * (prod.pu - reduction)
            total_general += sous_total

            lignes.append((prod, qte, prod.pu, reduction, sous_total))

        if not lignes:
            messages.error(request, "Aucun produit sélectionné pour la vente.")
            return redirect("produits:vendre_produit")

        # Création vente globale
        code = f"VENTE{timezone.now().strftime('%Y%m%d%H%M%S')}"
        vente = VenteProduit.objects.create(
            code=code,
            total=total_general,
            utilisateur = request.user,
            nom_complet_client=nom_complet,
            telclt_client=telephone,
            adresseclt_client=adresse
        )

        # Création lignes de vente et mise à jour stock magasin
        for prod, qte, pu, reduction, st in lignes:
            LigneVente.objects.create(
                vente=vente,
                produit=prod,
                quantite=qte,
                prix=pu,
                sous_total=st,
                montant_reduction=reduction,
            )

            stock_magasin = StockProduit.objects.filter(produit=prod, magasin__isnull=False).first()
            stock_magasin.qtestock -= qte
            stock_magasin.save()

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

from collections import defaultdict
@login_required

def historique_ventes(request):
    # Récupérer toutes les ventes avec utilisateur et lignes
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
        total_categories = set()
        # Calcul du profit par ligne et total de la vente
        for v in ventes_du_jour:
            v.total_profit = 0
            for ligne in v.lignes.all():
                ligne.profit = (ligne.produit.pu - ligne.produit.prix_en_gros) * ligne.quantite
                v.total_profit += ligne.profit
                total_quantite += ligne.quantite
                total_categories.add(ligne.produit.categorie.id)
            total_montant += v.total

        historique.append({
            "date": date,
            "ventes": ventes_du_jour,
            "total_montant": total_montant,
            "total_quantite": total_quantite,
            "total_categories": len(total_categories),
        })

    context = {
        "historique": historique
    }

    return render(
        request,
        "gestion_produits/ventes/historique_ventes.html",
        context
    )


def historique_commandes_livraisons(request):
    """
    Affiche l'historique des commandes avec les livraisons associées,
    la quantité totale livrée et la quantité restante.
    """
    commandes = Commandes.objects.select_related('produits').all().order_by('-datecmd')

    historique = []

    for cmd in commandes:
        # Toutes les livraisons associées à cette commande
        livraisons = LivraisonsProduits.objects.filter(commande=cmd).order_by('datelivrer')

        # Quantité totale livrée
        total_livree = livraisons.aggregate(total=Sum('qtelivrer'))['total'] or 0

        # Quantité restante à livrer
        qte_restante = max(cmd.qtecmd - total_livree, 0)

        historique.append({
            'commande': cmd,
            'livraisons': livraisons,
            'total_livree': total_livree,
            'qte_restante': qte_restante
        })

    context = {
        'historique': historique
    }

    return render(
        request,
        "gestion_produits/livraisons/historique_commandes_livraisons.html",
        context
    )

#================================================================================================
# Fonction pour éffectuer une nouvelle commande
#================================================================================================
@login_required
def nouvelle_commande(request):
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
            "seuil_magasin": stock_magasin.seuil if stock_magasin else 0,
            "stock_magasin_instance": stock_magasin,
            "stock_entrepot_instance": stock_entrepot,
        })
        
    if request.method == "POST":
        ids = request.POST.getlist("produit_id[]")
        quantites = request.POST.getlist("quantite[]")
        
        # Information du Fournisseur
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
            cmd = Commandes.objects.create(
                numcmd=numcmd,
                qtecmd=qte,
                produits=prod,
                
                nom_complet_fournisseur = nom_complet_fournisseur,
                adresse_fournisseur = adresse_fournisseur,
                telephone_fournisseur = telephone_fournisseur,
            )

            lignes.append((prod, qte))
            total_general += prod.pu * qte

        # Email à l'admin
        try:
            sujet = f"Nouvelle commande enregistrée - Fournisseur {nom_complet_fournisseur}"
            contenu = f"""
            Nouvelle commande effectuée.

            Téléphone : {telephone_fournisseur}
            Adresse : {adresse_fournisseur}

            Total estimé : {total_general:,} GNF

            Détails :
            """
            for p, q, f in lignes:
                contenu += f"- {p.desgprod} | Qté : {q} | PU : {p.pu} | Fournisseur : {f.nomcomplets} | Sous-total : {p.pu*q}\n"

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
        'produits': produits,
        'produits_data' : produits_data,
    }
    return render(request, "gestion_produits/commandes/nouvelle_commande.html", context)


@login_required
def reception_livraison(request):
    commandes = Commandes.objects.all().order_by('-datecmd')

    if request.method == "POST":
        commande_ids = request.POST.getlist("commande_id[]")
        quantites_livrees = request.POST.getlist("quantite_livree[]")

        if not commande_ids:
            messages.error(request, "Aucune commande sélectionnée pour la livraison.")
            return redirect("produits:reception_livraison")

        livraisons_effectuees = []
        numlivrer = f"LIV{timezone.now().strftime('%Y%m%d%H%M%S')}"
        entrepot = Entrepot.objects.first()  # Entrepôt principal

        for i in range(len(commande_ids)):
            try:
                cmd = Commandes.objects.get(id=commande_ids[i])
                qte_livree = int(quantites_livrees[i])
            except (Commandes.DoesNotExist, ValueError):
                continue

            if qte_livree <= 0:
                continue

            # 🔹 Vérifier si la quantité totale livrée dépasse la commande
            total_livree = (
                LivraisonsProduits.objects.filter(produits=cmd.produits)
                .aggregate(total=Sum('qtelivrer'))['total'] or 0
            )

            if total_livree + qte_livree > cmd.qtecmd:
                messages.warning(
                    request,
                    f"Impossible de livrer {qte_livree} unités de {cmd.produits.desgprod}. "
                    f"Quantité commandée : {cmd.qtecmd}, déjà livrée : {total_livree}."
                )
                continue  # Passe à la prochaine commande

            # ================= LIVRAISON =================
            LivraisonsProduits.objects.create(
                numlivrer=numlivrer,
                produits=cmd.produits,
                qtelivrer=qte_livree,
                datelivrer=timezone.now().date(),
                statuts="Livrée"
            )

            # ================= STOCK ENTREPOT =================
            stock_entrepot, created = StockProduit.objects.get_or_create(
                produit=cmd.produits,
                entrepot=entrepot,
                magasin=None,
                defaults={"qtestock": qte_livree, "seuil": 0}
            )

            if not created:
                stock_entrepot.qtestock = F('qtestock') + qte_livree
                stock_entrepot.save()

            # ================= STATUT COMMANDE =================
            if hasattr(cmd, "statuts"):
                cmd.statuts = "Livrée"
                cmd.save()

            livraisons_effectuees.append({
                "produit": cmd.produits.desgprod,
                "quantite": qte_livree,
                "fournisseur": cmd.nom_complet_fournisseur
            })

            # ================= NOTIFICATION =================
            Notification.objects.create(
                destinataire=request.user,
                titre="📦 Réception de livraison",
                message=(
                    f"Le produit {cmd.produits.desgprod} "
                    f"a été livré ({qte_livree} unité(s)) "
                    f"par {cmd.nom_complet_fournisseur}."
                ),
            )

        # ================= EMAIL ADMIN =================
        if livraisons_effectuees:
            try:
                contenu = "Nouvelle réception de livraison :\n\n"
                for l in livraisons_effectuees:
                    contenu += (
                        f"- Produit : {l['produit']} | "
                        f"Quantité : {l['quantite']} | "
                        f"Fournisseur : {l['fournisseur']}\n"
                    )

                EmailMessage(
                    "Réception de livraison enregistrée",
                    contenu,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.ADMIN_EMAIL],
                ).send()

            except Exception as e:
                messages.warning(request, "Livraison enregistrée mais email non envoyé.")

        messages.success(request, "Livraisons enregistrées et stock mis à jour avec succès.")
        return redirect("produits:listes_des_livraisons")

    return render(
        request,
        "gestion_produits/livraisons/reception_livraison.html",
        {"commandes": commandes}
    )

#================================================================================================
# Fonction pour voir le details de produit lors de la vente
#================================================================================================
@login_required
def details_vente(request, id):
    vente = get_object_or_404(VenteProduit, id=id)
    lignes = vente.lignes.select_related('produit').all()
    return render(request, "gestion_produits/ventes/details_vente.html", {"vente": vente, "lignes": lignes})


#=============================================================================================
# Fonction pour gérer les réçu Global de Paiement
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
                utilisateur=request.user,
                action="Suppression catégorie",
                table="CategorieProduit",
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=None
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

            # ----- Ancienne valeur pour l'audit -----
            ancienne_valeur = {
                "id": produit.id,
                "refprod": produit.refprod if hasattr(produit, "refprod") else "",
                "desgprod": produit.desgprod,
                "pu": float(produit.pu),
                "qtestock": produit.qtestock,
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
        prod_id = request.POST.get('id_supprimer')

        try:
            produit = Commandes.objects.get(id=prod_id)

            # Vérifier si le produit est lié à des commandes
            if Produits.objects.filter(produit=produit).exists():
                messages.warning(
                    request,
                    "Impossible de supprimer cette commande car il est déjà utilisé dans une commande. "
                    "Veuillez d'abord supprimer les commandes associées."
                )
                return redirect('produits:listes_des_commandes')

            # ----- Ancienne valeur pour l'audit -----
            ancienne_valeur = {
                "id": produit.id,
                "refprod": produit.refprod if hasattr(produit, "refprod") else "",
                "desgprod": produit.desgprod,
                "pu": float(produit.pu),
                "qtestock": produit.qtestock,
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

            messages.success(request, "Produit supprimé avec succès !")

        except Produits.DoesNotExist:
            messages.error(request, "Produit introuvable.")
        except Exception as ex:
            messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

        return redirect('produits:listes_produits')

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
    if request.method == 'POST':
        vente_id = request.POST.get('id_supprimer')

        try:
            # 🔒 Transaction pour éviter incohérences
            with transaction.atomic():

                # 1️⃣ Récupérer la vente
                vente = get_object_or_404(VenteProduit, id=vente_id)
                code_vente = vente.code  # sauvegarde avant suppression

                # 2️⃣ Récupérer toutes les lignes liées
                lignes = LigneVente.objects.select_related('produit').filter(vente=vente)

                # 3️⃣ Restaurer le stock
                for ligne in lignes:
                    produit = ligne.produit
                    produit.qtestock += ligne.quantite
                    produit.save()

                # 4️⃣ Supprimer lignes + vente
                lignes.delete()
                vente.delete()

            # ===== NOTIFICATION =====
            Notification.objects.create(
                destinataire=request.user,
                titre="🗑 Suppression de vente",
                message=(
                    f"La vente {code_vente} a été supprimée avec succès. "
                    "Les stocks ont été restaurés automatiquement."
                )
            )

            # ===== ENVOI EMAIL ADMIN =====
            try:
                sujet = "🗑 Suppression d'une vente"
                contenu = f"""
                Une vente a été supprimée.

                Code vente : {code_vente}
                Utilisateur : {request.user}
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

            messages.success(
                request,
                "Vente supprimée avec succès. Stocks restaurés ✔"
            )

        except Exception as ex:
            messages.error(
                request,
                f"Erreur lors de la suppression de la vente : {str(ex)}"
            )

    return redirect('produits:listes_des_ventes')

#================================================================================================
# Fonction pour afficher la liste de tout les produits
#================================================================================================

@login_required
def listes_produits(request):
    listes_produits = []
    total_produit = 0
    
    try:
        listes_produits = Produits.objects.all().order_by('-id')
        total_produit = listes_produits.count()
        listes_produits = pagination_liste(request, listes_produits)
    except Exception as ex :
        return messages.warning(request, f"Erreur de récupération des produits {str(ex)} !")
    context = {
        'listes_produits' : listes_produits,
        'total_produit' : total_produit
    }
    return render(request, "gestion_produits/lites_produits.html", context)

#================================================================================================
# Fonction pour afficher la liste de tout les produits
#================================================================================================

@login_required

def listes_produits_stock(request):
    try:
        listes_stock = StockProduit.objects.select_related('produit', 'entrepot', 'magasin').all().order_by('-id')
        total_produit = listes_stock.count()

        # Appliquer la pagination
        listes_stock = pagination_liste(request, listes_stock)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des produits en stock : {str(ex)} !")
        return redirect('produits:listes_produits_stock')  # Retourner un HttpResponse

    context = {
        'listes_produits': listes_stock,
        'total_produit': total_produit
    }

    return render(request, "gestion_produits/stocks/lites_produits_stocks.html", context)

#================================================================================================
# Fonction pour afficher la liste de tout les livraisons
#================================================================================================
@login_required
def listes_des_livraisons(request):
    listes_livraisons = []
    total_livraison = 0
    
    try:
        # Récupérer toutes les livraisons avec les relations utiles
        listes_livraisons = LivraisonsProduits.objects.select_related(
            'commande', 'produits'
        ).order_by('-id')

        total_livraison = listes_livraisons.count()

        # Calcul des quantités livrées et restantes pour chaque élément
        for elem in listes_livraisons:
            total_livree = LivraisonsProduits.objects.filter(
                produits=elem.produits,
                commande=elem.commande
            ).aggregate(total=Sum('qtelivrer'))['total'] or 0
            elem.total_livree = total_livree
            elem.qte_restante = elem.commande.qtecmd - total_livree

        # Pagination si nécessaire
        listes_livraisons = pagination_liste(request, listes_livraisons)

    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des produits : {str(ex)} !")

    context = {
        'listes_livraisons': listes_livraisons,
        'total_livraison': total_livraison
    }
    return render(request, "gestion_produits/livraisons/listes_livraisons.html", context)

#================================================================================================
# Fonction pour afficher la liste des ventes
#================================================================================================
@login_required

def listes_des_ventes(request):
    try:
        # Récupération des lignes de vente
        listes_ventes = LigneVente.objects.select_related(
            'vente', 'produit'
        ).order_by('-id')

        # Totaux
        total_ventes = listes_ventes.count()

        total_montant_ventes = listes_ventes.aggregate(
            total=Sum('sous_total')
        )['total'] or 0

        benefice_global = listes_ventes.aggregate(
            total=Sum('benefice')
        )['total'] or 0

        # Pagination
        listes_ventes = pagination_lis(request, listes_ventes)

    except Exception as ex:
        messages.warning(
            request,
            f"Erreur de récupération des ventes : {str(ex)}"
        )
        listes_ventes = []
        total_ventes = 0
        total_montant_ventes = 0
        benefice_global = 0

    context = {
        'listes_ventes': listes_ventes,
        'total_ventes': total_ventes,
        'total_montant_ventes': total_montant_ventes,
        'benefice_global': benefice_global,
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
    listes_commandes = []
    total_commandes = None
    try:
        listes_commandes = Commandes.objects.all().order_by('-id')
        total_commandes = listes_commandes.count()
        
        listes_commandes = pagination_lis(request,listes_commandes)
    except Exception as ex :
        return messages.warning(request, f"Erreur de récupération des commandes {str(ex)} !")
    except ValueError as ve:
        return messages.warning(request, f"Erreur de valeur {str(ve)} !")
        
    context = {
        'listes_commandes' : listes_commandes,
        'total_commandes' : total_commandes
    }
    return render(request, "gestion_produits/commandes/listes_commandes.html", context)

#================================================================================================
# Fonction pour filter la liste des vente selon un intervalle de date donnée
#================================================================================================
@login_required
def filtrer_listes_ventes(request):
    """
    Filtre les ventes selon la date,
    puis applique la pagination.
    """
    total_ventes = 0
    listes_ventes_filtre = []
    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    try:
        # Récupération de tous les paiements
        listes_ventes = VenteProduit.objects.all().order_by("-date_vente")
        listes_ventes_filtre = listes_ventes

        # Filtre par date si défini
        if date_debut and date_fin:
            listes_ventes_filtre = listes_ventes_filtre.filter(
                date_vente__range=(date_debut, date_fin)
            )

        # Pagination
        listes_ventes_filtre = pagination_liste(
            request, listes_ventes_filtre
        )

        # Calcul du total (avant pagination)
        try:
            total_ventes = listes_ventes_filtre.paginator.count
        except AttributeError:
            # Si la pagination n'a pas été appliquée ou est une liste
            total_ventes = len(listes_ventes_filtre)

    except TemplateDoesNotExist as tdne:
        messages.warning(request, f"Erreur de template non retrouvé : {str(tdne)}")
    except Exception as ex:
        messages.warning(request, f"Erreur de filtrage des données : {str(ex)}")

    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_ventes_filtre": listes_ventes_filtre,
        "total_ventes": total_ventes,
    }

    return render(request, "gestion_produits/ventes/listes_ventes.html", context)

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
    entrepots = Entrepot.objects.all()
    magasins = Magasin.objects.all()

    if request.method == "POST":
        # Récupération des listes de valeurs depuis le formulaire
        produit_ids = request.POST.getlist("produit[]")
        entrepot_ids = request.POST.getlist("entrepot[]")
        magasin_ids = request.POST.getlist("magasin[]")

        qte_entrepot_list = request.POST.getlist("qtestock_entrepot[]")
        qte_magasin_list = request.POST.getlist("qtestock_magasin[]")
        seuil_entrepot_list = request.POST.getlist("seuil_entrepot[]")
        seuil_magasin_list = request.POST.getlist("seuil_magasin[]")

        success_count = 0

        # Parcours de chaque produit
        for i in range(len(produit_ids)):
            try:
                produit = Produits.objects.get(id=int(produit_ids[i]))
                entrepot = Entrepot.objects.get(id=int(entrepot_ids[i]))
                magasin = Magasin.objects.get(id=int(magasin_ids[i]))

                qte_entrepot = int(qte_entrepot_list[i])
                qte_magasin = int(qte_magasin_list[i])
                seuil_e = int(seuil_entrepot_list[i])
                seuil_m = int(seuil_magasin_list[i])

                # =======================
                # STOCK ENTREPOT
                # =======================
                stock_entrepot, created_e = StockProduit.objects.get_or_create(
                    produit=produit,
                    entrepot=entrepot,
                    magasin=None,
                    defaults={
                        "qtestock": qte_entrepot,
                        "seuil": seuil_e
                    }
                )

                if not created_e:
                    stock_entrepot.qtestock += qte_entrepot
                    stock_entrepot.seuil = seuil_e
                    stock_entrepot.save()

                # =======================
                # STOCK MAGASIN
                # =======================
                stock_magasin, created_m = StockProduit.objects.get_or_create(
                    produit=produit,
                    magasin=magasin,
                    entrepot=None,
                    defaults={
                        "qtestock": qte_magasin,
                        "seuil": seuil_m
                    }
                )

                if not created_m:
                    stock_magasin.qtestock += qte_magasin
                    stock_magasin.seuil = seuil_m
                    stock_magasin.save()

                success_count += 1

            except Produits.DoesNotExist:
                messages.error(request, f"Produit introuvable pour l'entrée {i+1}.")
            except Entrepot.DoesNotExist:
                messages.error(request, f"Entrepôt introuvable pour l'entrée {i+1}.")
            except Magasin.DoesNotExist:
                messages.error(request, f"Magasin introuvable pour l'entrée {i+1}.")
            except ValueError:
                messages.error(request, f"Quantité ou seuil invalide pour le produit {produit.refprod}.")
            except Exception as e:
                messages.error(request, f"Erreur pour le produit {produit.refprod}: {e}")

        messages.success(
            request,
            f"{success_count} produit(s) enregistré(s) / mis à jour avec succès."
        )
        return redirect("produits:ajouter_stock_multiple")

    return render(request, "gestion_produits/stocks/ajouter_stock_multiple.html", {
        "produits": produits,
        "entrepots": entrepots,
        "magasins": magasins,
    })

#================================================================================================
# Fonction pour afficher le formulaire de choix de dates de saisie pour l'impression des produit
#================================================================================================
@login_required
def choix_par_dates_produit_impression(request):
    return render(request, 'gestion_produits/impression_listes/fiches_choix_impression_produits.html')

#================================================================================================
# Fonction pour imprimer la listes des produits
#================================================================================================
@login_required
def listes_produits_impression(request):
    
    try:
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin')
    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des dates : {str(ex)}")

    except ValueError as ve:
        messages.warning(request, f"Erreur de type de données : {str(ve)}")
        
    listes_produits = Produits.objects.filter(
        date_maj__range=[date_debut, date_fin]
    )

    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_produits' : listes_produits,
    }
    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_produits.html',
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
    
    try:
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin')
    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des dates : {str(ex)}")

    except ValueError as ve:
        messages.warning(request, f"Erreur de type de données : {str(ve)}")
        
    listes_ventes = LigneVente.objects.all()
    
    listes_ventes_filtre = listes_ventes.filter(
        date_saisie__range = [
            date_debut, date_fin
        ]
    )
    print(f"listes_ventes : {listes_ventes_filtre}")
    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_ventes' : listes_ventes_filtre,
        'date_debut' : date_debut,
        'date_fin' : date_fin,
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
            date_debut, date_fin
    ]
    )
    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_commandes' : listes_commandes,
        'date_debut' : date_debut,
        'date_fin' : date_fin,
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
# Fonction pour imprimer la listes des Commandes
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
            date_debut, date_fin
    ]
    )

    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_livraisons' : listes_livraisons,
        'date_debut' : date_debut,
        'date_fin' : date_fin,
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
