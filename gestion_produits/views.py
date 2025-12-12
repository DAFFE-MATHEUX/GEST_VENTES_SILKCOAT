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
from .utils import *
from gestion_clients.views import nouveau_client
from gestion_audit.views import enregistrer_audit
from .models import * 
from django.core.mail import EmailMessage
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse
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
def approvisionner_produit(request, id):
    produit = Produits.objects.get(id=id)

    if request.method == "POST":
        qte = int(request.POST.get("quantite"))

        produit.qtestock += qte
        produit.save()

        messages.success(request, "Approvisionnement réussi !")
        return redirect("produits:vendre_produit")

    return render(request, "gestion_produits/approvisionnement/approvisionner_produit.html", {
        "produit": produit
    })

#================================================================================================
# Fonction pour éffectuer une nouvelle vente
#================================================================================================

@login_required
def vendre_produit(request):
    produits = Produits.objects.all()

    if request.method == "POST":
        ids = request.POST.getlist("produit_id[]")
        quantites = request.POST.getlist("quantite[]")

        nom_complet = request.POST.get("nom_complet_client[]")
        telephone = request.POST.get("telephone_client[]")
        adresse = request.POST.get("adresse_client[]")

        if not nom_complet or not telephone:
            messages.error(request, "Veuillez renseigner le nom complet et le numéro de téléphone du client.")
            return redirect("produits:vendre_produit")

        total_general = 0
        lignes = []

        # Vérification des stocks
        for i in range(len(ids)):
            prod = Produits.objects.get(id=ids[i])
            qte = int(quantites[i])

            if qte <= 0:
                messages.error(request, f"Quantité invalide pour {prod.desgprod}.")
                return redirect("produits:vendre_produit")

            if qte > prod.qtestock:
                messages.error(request, f"Stock insuffisant pour {prod.desgprod}. Disponible : {prod.qtestock}")
                return redirect("produits:vendre_produit")

            sous_total = qte * prod.pu
            total_general += sous_total

            lignes.append((prod, qte, prod.pu, sous_total))

        # Génération du code de vente
        code = f"V{timezone.now().strftime('%Y%m%d%H%M%S')}"

        # Création de la vente globale
        vente = VenteProduit.objects.create(
            code=code,
            total=total_general,
            utilisateur = request.user,
        )
        nouveau_client(
                nomcomplet = nom_complet,
                telephone= telephone,
                adresse = adresse
            )

        # Lignes de vente
        for prod, qte, pu, st in lignes:
            LigneVente.objects.create(
                vente=vente,
                produit=prod,
                quantite=qte,
                prix=pu,
                sous_total=st,
                
                #nom_complet_client = nom_complet,
                #telclt_client = telephone,
                #adresseclt_client = adresse,
            )

            # Mise à jour stock
            prod.qtestock -= qte
            prod.save()
            

        # 🟦 ENVOI D'EMAIL À L'ADMIN
        try:
            sujet = f"Nouvelle vente enregistrée - Code {vente.code}"
            contenu = f"""
                Nouvelle vente effectuée.
                Par l'utilisateur : {request.user}
                Code vente : {vente.code}
                Client : {nom_complet}
                Téléphone : {telephone}
                Adresse : {adresse}

                Total : {total_general:,} GNF

                Détails :
            """

            for (p, q, pu, st) in lignes:
                contenu += f"- {p.desgprod} | Qté : {q} | Prix : {pu} | Sous-total : {st}\n"

            email = EmailMessage(
                sujet,
                contenu,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
            )
            email.send()

        except Exception as e:
            messages.warning(request, f"Vente enregistrée mais email non envoyé : {str(e)}")

        messages.success(request, "Vente enregistrée avec succès !")
        return redirect("produits:recu_vente_global", vente_code=vente.code)

    return render(request, "gestion_produits/ventes/nouvelle_vente.html", {"produits": produits})


#================================================================================================
# Fonction pour éffectuer une nouvelle commande
#================================================================================================
@login_required
def nouvelle_commande(request):
    produits = Produits.objects.all()

    if request.method == "POST":
        ids = request.POST.getlist("produit_id[]")
        quantites = request.POST.getlist("quantite[]")
        nom_complet_client = request.POST.get("nom_complet_client")
        telephone_client = request.POST.get("telephone_client")
        adresse_client = request.POST.get("adresse_client")

        # Validation des produits et quantités
        if not ids or not quantites:
            messages.error(request, "Aucun produit sélectionné.")
            return redirect("produits:nouvelle_commande")

        lignes = []
        total_general = 0

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
                numcmd=f"C{timezone.now().strftime('%Y%m%d%H%M%S')}",
                qtecmd=qte,
                produits=prod
            )

            lignes.append((prod, qte))
            total_general += prod.pu * qte  # Total en fonction du prix unitaire

        # Email à l'admin
        try:
            sujet = f"Nouvelle commande enregistrée - Client {nom_complet_client}"
            contenu = f"""
Nouvelle commande effectuée.

Téléphone : {telephone_client}
Adresse : {adresse_client}

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

        messages.success(request, "Commande(s) enregistrée(s) avec succès !")
        return redirect("produits:listes_commandes")

    return render(request, "gestion_produits/commandes/nouvelle_commande.html", {
        "produits": produits,
    })

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

    context = {
        "vente": vente,
        "lignes": lignes,
        "total": total,
        "today": now(),
        "qr_code_base64": qr_code_base64,
        "etablissement": Entreprise.objects.first(),
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
# Fonction pour supprimer une vente donnée
#================================================================================================

@login_required
def supprimer_ventes(request):
    if request.method == 'POST':
        vente = request.POST.get('id_supprimer')

        try:
            categorie = LigneVente.objects.get(id=vente)
            categorie.delete()
            messages.success(request, "Ligne vente supprimée avec succès !")
            return redirect('produits:listes_des_ventes')
        except Exception as ex:
            messages.error(request, f"Erreur lors de la suppression : {str(ex)}")

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
# Fonction pour afficher la liste de tout les livraisons
#================================================================================================

@login_required
def listes_des_livraisons(request):
    listes_livraisons = []
    total_livraison = 0
    
    try:
        listes_livraisons = Livraisons.objects.all().order_by('-id')
        total_livraison = listes_livraisons.count()
        listes_livraisons = pagination_liste(request, listes_livraisons)
    except Exception as ex :
        return messages.warning(request, f"Erreur de récupération des produits {str(ex)} !")
    context = {
        'listes_livraisons' : listes_livraisons,
        'total_livraison' : total_livraison
    }
    return render(request, "gestion_produits/lites_produits.html", context)

#================================================================================================
# Fonction pour afficher la liste des ventes
#================================================================================================

@login_required
def listes_des_ventes(request):
    listes_ventes = []
    total_ventes = None
    try:
        listes_ventes = LigneVente.objects.all().order_by('-id')
        total_ventes = listes_ventes.count()
        
        listes_ventes = pagination_lis(request,listes_ventes)
    except Exception as ex :
        return messages.warning(request, f"Erreur de récupération des produits {str(ex)} !")
    except ValueError as ve:
        return messages.warning(request, f"Erreur de valeur {str(ve)} !")
        
    context = {
        'listes_ventes' : listes_ventes,
        'total_ventes' : total_ventes
    }
    return render(request, "gestion_produits/ventes/listes_ventes.html", context)

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
        return redirect('listes_produits')

    categories = CategorieProduit.objects.all()

    if request.method == 'POST':
        produit.desgprod = request.POST.get('desgprod')
        produit.qtestock = request.POST.get('qtestock')
        produit.seuil = request.POST.get('seuil')
        produit.pu = request.POST.get('pu')

        categorie_id = request.POST.get('categorie')
        produit.categorie_id = categorie_id

        if 'photoprod' in request.FILES:
            produit.photoprod = request.FILES['photoprod']

        produit.save()

        messages.success(request, "Produit modifié avec succès !")
        return redirect('listes_produits')

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
        stocks = request.POST.getlist("qtestock[]")
        seuils = request.POST.getlist("seuil[]")
        pus = request.POST.getlist("pu[]")
        categories = request.POST.getlist("categorie[]")
        
        photos = request.FILES.getlist("photoprod[]")

        total = len(noms)
        success_count = 0

        # Vérification cohérence des listes
        if not (len(refs) == len(noms) == len(stocks) == len(seuils) == len(pus) == len(categories)):
            messages.error(request, "Erreur : Données incomplètes dans le formulaire.")
            return redirect("produits:nouveau_produit")

        for i in range(total):

            ref = refs[i]
            desg = noms[i]
            qte = int(stocks[i])
            seuil = int(seuils[i])
            pu = int(pus[i])
            cat_id = categories[i]
            photo = photos[i] if i < len(photos) else None

            # Vérifier doublon
            if Produits.objects.filter(refprod=ref).exists():
                messages.error(request, f"Référence {ref} déjà existante.")
                continue

            try:
                Produits.objects.create(
                    refprod=ref,
                    desgprod=desg,
                    qtestock=qte,
                    seuil=seuil,
                    pu=pu,
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
# Fonction pour afficher le formulaire de choix de dates de saisie pour l'impression des produit
#================================================================================================

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

    nom_entreprise = Produits.objects.first()
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
        
    listes_ventes = VenteProduit.objects.filter(
        date_vente__range=[date_debut, date_fin]
    )

    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_ventes' : listes_ventes,
    }
    return render(
        request,
        'gestion_produits/impression_listes/apercue_avant_impression_listes_ventes.html',
        context
    )


#================================================================================================
# Fonction pour afficher le formulaire de formulaire d'exportation des données
#================================================================================================

@login_required
def exportation_donnees_excel(request):
    
    return render(request, 'gestion_produits/exportation/exportation_donnees_excel.html')

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

#==============================================================================================
