
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from .models import Utilisateur
from datetime import date
from gest_entreprise.models import Depenses
from gestion_audit.views import enregistrer_audit
from gestion_audit.models import AuditLog
from gestion_notifications.models import Notification

from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from gestion_produits.models import *
from django.db.models import Sum, F
from django.utils import timezone
from django.conf import settings
import calendar
from datetime import date, timedelta


# ===============================================
# Tableau de bord
# ===============================================

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def home(request):
    # ===============================
    # UTILISATEUR
    # ===============================
    utilisateur = request.user

    # ===============================
    # MOIS / ANNÉE SÉLECTIONNÉS
    # ===============================
    aujourd_hui = timezone.now().date()
    mois = int(request.GET.get("mois", aujourd_hui.month))
    annee = int(request.GET.get("annee", aujourd_hui.year))

    # Début & fin mois courant
    debut_mois = date(annee, mois, 1)
    dernier_jour = calendar.monthrange(annee, mois)[1]
    fin_mois = date(annee, mois, dernier_jour)

    # ===============================
    # DATE ACTUELLE
    # ===============================
    hier = aujourd_hui - timedelta(days=1)

    # ===============================
    # MOIS PRÉCÉDENT
    # ===============================
    if mois == 1:
        mois_prec = 12
        annee_prec = annee - 1
    else:
        mois_prec = mois - 1
        annee_prec = annee

    debut_mois_prec = date(annee_prec, mois_prec, 1)
    fin_mois_prec = date(annee_prec, mois_prec, calendar.monthrange(annee_prec, mois_prec)[1])

    # ===============================
    # NOTIFICATIONS
    # ===============================
    dernieeres_notification = Notification.objects.all().order_by('-date')
    non_lues = dernieeres_notification.filter(lu=False)
    lues = dernieeres_notification.filter(lu=True)

    # ===============================
    # DERNIÈRES COMMANDES / LIVRAISONS
    # ===============================
    listes_commandes = Commandes.objects.order_by('-datecmd')[:3]
    listes_livraisons = LivraisonsProduits.objects.order_by('-datelivrer')[:3]

    # ===============================
    # DERNIÈRES VENTES
    # ===============================
    dernieres_ventes = VenteProduit.objects.order_by('-date_vente')[:5]
    for vente in dernieres_ventes:
        vente.calculer_totaux()
        vente.quantite_vendue()

    # Totaux globaux
    totaux = VenteProduit.objects.aggregate(
        total_ventes=Sum('total'),
        total_benefice=Sum('benefice_total'),
        total_quantite=Sum('total_quanite')
    )

    # ===============================
    # COMPARAISON PAR JOUR
    # ===============================
    total_hier = VenteProduit.objects.filter(date_vente=hier).aggregate(total=Sum('total'))['total'] or 0
    total_aujourdhui = VenteProduit.objects.filter(date_vente=aujourd_hui).aggregate(total=Sum('total'))['total'] or 0

    labels_jour_comparaison = ["Hier", "Aujourd’hui"]
    data_jour_hier = [total_hier, 0]
    data_jour_aujourdhui = [0, total_aujourdhui]

    # ===============================
    # COMPARAISON PAR SEMAINE
    # ===============================
    debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    fin_semaine = debut_semaine + timedelta(days=6)
    debut_semaine_prec = debut_semaine - timedelta(days=7)
    fin_semaine_prec = debut_semaine - timedelta(days=1)

    total_semaine_actuelle = VenteProduit.objects.filter(date_vente__range=[debut_semaine, fin_semaine]).aggregate(total=Sum('total'))['total'] or 0
    total_semaine_precedente = VenteProduit.objects.filter(date_vente__range=[debut_semaine_prec, fin_semaine_prec]).aggregate(total=Sum('total'))['total'] or 0

    labels_semaine = ["Semaine Précédente", "Semaine Actuelle"]
    data_semaine_precedente = [total_semaine_precedente, 0]
    data_semaine_actuelle = [0, total_semaine_actuelle]

    # ===============================
    # COMPARAISON MENSUELLE
    # ===============================
    total_mois_actuel = VenteProduit.objects.filter(date_vente__range=[debut_mois, fin_mois]).aggregate(total=Sum('total'))['total'] or 0
    total_mois_precedent = VenteProduit.objects.filter(date_vente__range=[debut_mois_prec, fin_mois_prec]).aggregate(total=Sum('total'))['total'] or 0

    labels_mois = ['Mois Précédent', 'Mois Actuel']
    data_mois_precedent = [total_mois_precedent]
    data_mois_actuel = [total_mois_actuel]

    # ===============================
    # COURBE JOURNALIÈRE
    # ===============================
    labels_jours = []
    ventes_journalieres = []
    for jour in range(1, dernier_jour + 1):
        date_jour = date(annee, mois, jour)
        total_jour = VenteProduit.objects.filter(date_vente=date_jour).aggregate(total=Sum('total'))['total'] or 0
        labels_jours.append(str(jour))
        ventes_journalieres.append(total_jour)

    # ===============================
    # TOP PRODUITS VENDUS
    # ===============================
    produits_plus_vendus = (
        LigneVente.objects
        .filter(vente__date_vente__range=[debut_mois, fin_mois])
        .values('produit__desgprod', 'produit__categorie__desgcategorie')
        .annotate(qte_totale=Sum('quantite'))
        .order_by('-qte_totale')[:5]
    )
    labels_produits = [p['produit__desgprod'] for p in produits_plus_vendus]
    quantites_produits = [p['qte_totale'] for p in produits_plus_vendus]

    # ===============================
    # TOP PRODUITS RENTABLES
    # ===============================
    top_produits_rentables = (
        LigneVente.objects
        .filter(vente__date_vente__range=[debut_mois, fin_mois])
        .values('produit__refprod', 'produit__desgprod', 'produit__categorie__desgcategorie')
        .annotate(
            benefice_total=Sum('benefice'),
            qte_vendue=Sum('quantite')
        )
        .order_by('-benefice_total')[:5]
    )

    total_quantite_vendu = sum(p['qte_vendue'] for p in top_produits_rentables)
    total_benefice = sum(p['benefice_total'] for p in top_produits_rentables)

    labels_rentables = [p['produit__desgprod'] for p in top_produits_rentables]
    benefices = [p['benefice_total'] for p in top_produits_rentables]

    # ===============================
    # STATISTIQUES GÉNÉRALES
    # ===============================
    total_produits = Produits.objects.count()
    total_categories = CategorieProduit.objects.count()
    total_stock = StockProduit.objects.aggregate(total=Sum('qtestock'))['total'] or 0
    total_commandes = Commandes.objects.filter(datecmd__range=[debut_mois, fin_mois]).count()
    total_livraisons = LivraisonsProduits.objects.filter(datelivrer__range=[debut_mois, fin_mois]).count()
    total_ventes = VenteProduit.objects.filter(date_vente__range=[debut_mois, fin_mois]).aggregate(total=Sum('total'))['total'] or 0
    total_depenses = Depenses.objects.filter(date_operation__range=[debut_mois, fin_mois]).count()

    # ===============================
    # CONTEXTE
    # ===============================
    context = {
        'mois_selectionne': mois,
        'annee_selectionnee': annee,
        'labels_jours': labels_jours,
        'ventes_journalieres': ventes_journalieres,
        'labels_produits': labels_produits,
        'quantites_produits': quantites_produits,
        'labels_rentables': labels_rentables,
        'benefices': benefices,
        'produits_plus_vendus': produits_plus_vendus,
        'top_produits_rentables': top_produits_rentables,
        'dernieres_ventes': dernieres_ventes,
        'listes_commandes': listes_commandes,
        'listes_livraisons': listes_livraisons,
        'dernieeres_notification': dernieeres_notification[:5],
        'non_lues': non_lues,
        'lues': lues,
        'total_depenses': total_depenses,
        'total_produits': total_produits,
        'total_categories': total_categories,
        'total_stock': total_stock,
        'total_commandes': total_commandes,
        'total_livraisons': total_livraisons,
        'total_ventes': total_ventes,
        'labels_mois': labels_mois,
        'data_mois_precedent': data_mois_precedent,
        'data_mois_actuel': data_mois_actuel,
        'totaux': totaux,
        'hier': hier,
        'aujourd_hui': aujourd_hui,
        'labels_semaine': labels_semaine,
        'data_semaine_precedente': data_semaine_precedente,
        'data_semaine_actuelle': data_semaine_actuelle,
        'labels_jour_comparaison': labels_jour_comparaison,
        'data_jour_hier': data_jour_hier,
        'data_jour_aujourdhui': data_jour_aujourdhui,
        'total_quantite_vendu': total_quantite_vendu,
        'total_benefice': total_benefice,
    }

    return render(request, 'gestion_utilisateur/dashboard.html', context)

# ===============================================
# Inscription utilisateur avec approbation admin
# ===============================================
import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .models import Utilisateur
from gestion_notifications.models import Notification

# Fonction de validation d'image
from django.core.exceptions import ValidationError

def validate_image(file):
    max_size_mb = 2  # Taille max 2 Mo
    valid_extensions = ['jpg', 'jpeg', 'png', 'gif']
    
    # Vérifier la taille
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"La taille de l'image ne doit pas dépasser {max_size_mb} Mo.")
    
    # Vérifier l'extension
    ext = file.name.split('.')[-1].lower()
    if ext not in valid_extensions:
        raise ValidationError("Formats autorisés : jpg, jpeg, png, gif")

# Vue d'inscription utilisateur
def inscriptionutilisateur(request):
    choix_utilisateur = Utilisateur.ROLE_CHOICES

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password1 = request.POST.get('password')
        password2 = request.POST.get('confirm_password')
        type_utilisateur = request.POST.get('type_utilisateur')
        photo_utilisateur = request.FILES.get('photo_utilisateur')

        # ---------------------------
        # 1️⃣ Vérification des champs
        # ---------------------------
        if not all([username, email, first_name, last_name, password1, password2, type_utilisateur]):
            messages.error(request, "Tous les champs (sauf la photo) sont obligatoires !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if password1 != password2:
            messages.error(request, "Les mots de passe ne sont pas identiques !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if len(password1) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if Utilisateur.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur est déjà pris !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if Utilisateur.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà enregistré !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        # ---------------------------
        # 2️⃣ Validation des noms et emails
        # ---------------------------
        name_pattern = r'^[A-Za-z\s\-]+$'  # lettres, espaces et tirets uniquement
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if not re.match(name_pattern, first_name):
            messages.error(request, "Prénom invalide (lettres, espaces et tirets uniquement).")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if not re.match(name_pattern, last_name):
            messages.error(request, "Nom de famille invalide (lettres, espaces et tirets uniquement).")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if not re.match(email_pattern, email):
            messages.error(request, "Adresse email invalide !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        # ---------------------------
        # 3️⃣ Validation de la photo
        # ---------------------------
        if photo_utilisateur:
            try:
                validate_image(photo_utilisateur)
            except ValidationError as e:
                messages.error(request, str(e))
                return redirect('gestionUtilisateur:inscription_utilisateur')

        # ---------------------------
        # 4️⃣ Création de l'utilisateur
        # ---------------------------
        try:
            user = Utilisateur.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                type_utilisateur=type_utilisateur,
                photo_utilisateur=photo_utilisateur,
                is_approved=False  # L'utilisateur doit être approuvé par l'admin
            )

            messages.success(request, "Utilisateur ajouté avec succès. En attente d'approbation par l'administrateur.")

            # ---------------------------
            # 5️⃣ Notification aux admins
            # ---------------------------
            admins = Utilisateur.objects.filter(type_utilisateur='Admin', is_active=True)
            for admin in admins:
                Notification.objects.create(
                    destinataire_email=admin.email,
                    titre="Nouvel utilisateur à approuver",
                    message=f"L'utilisateur {user.username} vient de s'inscrire et nécessite votre approbation.",
                    destinataire=admin
                )

            return redirect('gestionUtilisateur:connexion_utilisateur')

        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {str(e)}")

    context = {'choix_utilisateur': choix_utilisateur}
    return render(request, 'gestion_utilisateur/inscription_utilisateur.html', context)


# ===============================================
# Connexion utilisateur avec vérification approbation
# ===============================================
def login_user(request):
    if request.method == 'POST':
        identifiant = request.POST.get('username')
        password = request.POST.get('password')
        username = identifiant

        # Si l'identifiant est un email, on récupère le username correspondant
        if '@' in identifiant:
            try:
                user_obj = Utilisateur.objects.get(email=identifiant)
                username = user_obj.username
            except Utilisateur.DoesNotExist:
                messages.error(request, "Aucun utilisateur avec cet e-mail !")
                return redirect('gestionUtilisateur:connexion_utilisateur')

        # Authentification
        user = authenticate(request, username=username, password=password)
        if user:
            # Vérification si l'utilisateur est actif
            if not user.is_active:
                messages.error(request, "Votre compte est désactivé ! Contactez l'administrateur.")
                return redirect('gestionUtilisateur:connexion_utilisateur')

            # Vérification si l'utilisateur est approuvé (sauf pour les Admin)
            if user.type_utilisateur != 'Admin' and not user.is_approved:
                messages.error(request, "Votre compte n'a pas encore été approuvé par un administrateur !")
                return redirect('gestionUtilisateur:connexion_utilisateur')

            # Connexion réussie
            login(request, user)
            messages.success(request, f"Bienvenue {user.first_name} !")
            return redirect('gestionUtilisateur:tableau_bord')
        else:
            messages.error(request, "Identifiant ou mot de passe incorrect !")
            return redirect('gestionUtilisateur:connexion_utilisateur')

    return render(request, 'gestion_utilisateur/login.html')

# ===============================================
# Déconnexion
# ===============================================
def Logoutuser(request):
    logout(request)
    messages.success(request, 'Vous êtes maintenant déconnecté')
    return redirect('/')

def page_bienvenue(request):
        return render(request, 'gestion_utilisateur/page_bienvenue.html')


# ===============================================
# Liste utilisateurs
# ===============================================

# Pattern pour valider noms/prénoms
NAME_PATTERN = r'^[A-Za-z\s\-]+$'
EMAIL_PATTERN = r'^[\w\.-]+@[\w\.-]+\.\w+$'

@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def liste_utilisateur(request):
    """
    Vue pour afficher la liste des utilisateurs et gérer l'approbation/refus.
    Les utilisateurs avec noms/emails invalides ne peuvent pas être approuvés.
    """

    listeuser_qs = Utilisateur.objects.all().order_by('last_name')
    
    # Pagination : 7 utilisateurs par page
    pageuser = Paginator(listeuser_qs, 7)
    numpage = request.GET.get("page")
    listeuser = pageuser.get_page(numpage)

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        action = request.POST.get("action")  # 'approve' ou 'refuse'

        if user_id and action:
            try:
                user_obj = Utilisateur.objects.get(id=user_id)

                # 🔹 Vérification automatique de la validité
                valid_first_name = re.match(NAME_PATTERN, user_obj.first_name)
                valid_last_name = re.match(NAME_PATTERN, user_obj.last_name)
                valid_email = re.match(EMAIL_PATTERN, user_obj.email)

                if action == "approve":
                    if not (valid_first_name and valid_last_name and valid_email):
                        messages.error(
                            request, 
                            f"Impossible d'approuver {user_obj.username} : informations invalides."
                        )
                    else:
                        user_obj.is_approved = True
                        user_obj.is_active = True
                        user_obj.save()

                        Notification.objects.create(
                            destinataire=user_obj,
                            message="✅ Votre compte a été approuvé par l'administrateur."
                        )
                        messages.success(request, f"Utilisateur {user_obj.username} approuvé avec succès.")

                elif action == "refuse":
                    user_obj.is_approved = False
                    user_obj.is_active = False
                    user_obj.save()

                    Notification.objects.create(
                        destinataire=user_obj,
                        message="❌ Votre compte n'a pas été approuvé par l'administrateur."
                    )
                    messages.info(request, f"Utilisateur {user_obj.username} désapprouvé avec succès.")

            except Utilisateur.DoesNotExist:
                messages.error(request, "Utilisateur introuvable.")

            return redirect('gestionUtilisateur:liste_utilisateur')

    context = {
        'listeuser': listeuser,
    }

    return render(request, 'gestion_utilisateur/liste_utilisateur.html', context)

# ===============================================
# Supprimer utilisateur
# ===============================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def supprimerutilisateur(request):
    if request.method == "POST":
        id_supprimer = request.POST.get("id_supprimer")

        if not id_supprimer:
            messages.warning(request, "⚠️ Aucun utilisateur sélectionné pour suppression.")
            return redirect('gestionUtilisateur:liste_utilisateur')

        try:
            utilisateur_obj = get_object_or_404(Utilisateur, id=id_supprimer)

            # 🔒 1. Empêcher suppression si l'utilisateur est connecté
            if request.user.id == utilisateur_obj.id:
                messages.warning(
                    request,
                    "❌ Vous ne pouvez pas supprimer votre propre compte pendant que vous êtes connecté."
                )
                return redirect('gestionUtilisateur:liste_utilisateur')

            # 🔒 2. Empêcher suppression si l'utilisateur a reçu des notifications
            if Notification.objects.filter(destinataire=utilisateur_obj.email).exists():
                messages.warning(
                    request,
                    "❌ Impossible de supprimer cet utilisateur : il possède déjà des notifications enregistrées."
                )
                return redirect('gestionUtilisateur:liste_utilisateur')

            # 🔒 3. Empêcher suppression si l'utilisateur a déjà des ventes enregistrées
            if LigneVente.objects.filter(vente__utilisateur=utilisateur_obj).exists():
                messages.warning(
                    request,
                    "❌ Impossible de supprimer cet utilisateur : il possède déjà des ventes enregistrées."
                )
                return redirect('gestionUtilisateur:liste_utilisateur')

            # 🔒 4. Empêcher suppression si l'utilisateur apparaît dans l'audit
            if AuditLog.objects.filter(utilisateur=utilisateur_obj).exists():
                messages.warning(
                    request,
                    "❌ Impossible de supprimer cet utilisateur : des actions auditées existent."
                )
                return redirect('gestionUtilisateur:liste_utilisateur')

            # --- 5. Audit avant suppression ---
            details_ancienne_valeur = {
                "Nom": utilisateur_obj.first_name,
                "Prénom": utilisateur_obj.last_name,
                "Email": utilisateur_obj.email,
                "Rôle": getattr(utilisateur_obj, "type_utilisateur", ""),
                "Username": utilisateur_obj.username,
                "Statut": "Actif" if utilisateur_obj.is_active else "Inactif",
            }

            enregistrer_audit(
                utilisateur=request.user,
                action="Suppression",
                table="Utilisateur",
                ancienne_valeur=details_ancienne_valeur,
                nouvelle_valeur=None
            )

            # --- 6. Suppression effective ---
            utilisateur_obj.delete()
            messages.success(request, "✅ Utilisateur supprimé avec succès.")

        except Exception as ex:
            messages.error(request, f"⚠️ Erreur lors de la suppression : {str(ex)}")

        return redirect('gestionUtilisateur:liste_utilisateur')

    messages.warning(request, "⚠️ Méthode non autorisée pour la suppression.")
    return redirect('gestionUtilisateur:liste_utilisateur')

# ===============================================
# Password reset personnalisé
# ===============================================
class CustomPasswordResetView(PasswordResetView):
    template_name = "allauth/password_reset.html"
    email_template_name = "allauth/password_reset_email.html"
    subject_template_name = "allauth/password_reset_subject.txt"
    success_url = reverse_lazy('gestionUtilisateur:password_reset_done')


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "allauth/password_reset_form.html"
    success_url = reverse_lazy('gestionUtilisateur:password_reset_complete')
# ===============================================

# End of GestionUtilisateur/views.py