
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from .models import Utilisateur
from rest_framework import viewsets
from datetime import date
from gest_entreprise.models import Entreprise
from gestion_audit.views import enregistrer_audit
from gestion_audit.models import AuditLog
from gestion_notifications.models import Notification

from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from gestion_produits.models import *
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
# ===============================================
# Tableau de bord
# ===============================================
@login_required

def home(request):
    # Profil de l'entreprise
    profil = Entreprise.objects.first()

    # Utilisateur connecté
    utilisateur = request.user

    aujourdhui = timezone.now().date()
    debut_semaine = aujourdhui - timedelta(days=aujourdhui.weekday())  # Lundi
    fin_semaine = debut_semaine + timedelta(days=6)  # Dimanche
    
    # -------------------
    # Notifications
    # -------------------
    notifications = Notification.objects.filter(destinataire=utilisateur).order_by('-date')
    non_lues = notifications.filter(lu=False)
    lues = notifications.filter(lu=True)

    # -------------------
    # Audits récents
    # -------------------
    audits = AuditLog.objects.order_by('-date_action')[:5]

    # ---------------------------------------
    # Ventes récentes (dernières ventes)
    # ---------------------------------------
    dernieres_ventes = VenteProduit.objects.order_by('-date_vente')

    # ----------------------------------------------
    # Les produits les plus vendus dans la semaine
    # ----------------------------------------------

    produits_plus_vendus = (
        VenteProduit.objects
        .filter(date_vente__date__range=[debut_semaine, fin_semaine])
        .prefetch_related('lignes', 'lignes__produit')
        .annotate(qte_totale=Sum('lignes__quantite'))
        .order_by('-qte_totale')
    )

    # ----------------------------------------
    # Statistiques sur le total des produits
    # ----------------------------------------
    total_produits = Produits.objects.count()
    
    # ---------------------------------------------------------
    # Statistiques sur le total des stocks de tout les produits
    # ----------------------------------------------------------
    data_products = Produits.objects.all()
    total_stock = data_products.aggregate(qtestock=Sum('qtestock'))['qtestock'] or 0

    # ----------------------------------------
    # Statistiques sur le total de catégorie
    # ----------------------------------------
    total_categories = CategorieProduit.objects.count()
    
    # ----------------------------------------------
    # Commandes de la semaine
    # ----------------------------------------------
    """ 
    # Commande du jour
    Commandes.objects.filter(
            datecmd__gte=debut_semaine
        ).values('datecmd').annotate(total=Count('id'))
    """
    
    """ 
    # 📌 Celle-ci compte les 7 derniers jours, pas exactement la semaine civile.
    total_commandes = Commandes.objects.filter(
    datecmd__gte=timezone.now().date() - timedelta(days=7)
    ).count()
    """
    commandes_semaine = Commandes.objects.filter(
        datecmd__range=[debut_semaine, fin_semaine]
    )

    total_commandes = commandes_semaine.count()
    # ----------------------------------------------
    # Total de Livraisons de la semaine
    # ----------------------------------------------
    livraisons_semaine = LivraisonsProduits.objects.filter(
        datelivrer__range=[debut_semaine, fin_semaine]
    )
    total_livraisons = livraisons_semaine.count()

    # ----------------------------------------------
    # Total de vente éffectuée dans la semaine
    # ----------------------------------------------
    ventes_semaines = VenteProduit.objects.filter(
        date_vente__range = [
            debut_semaine, fin_semaine
        ]
    )
    total_ventes = ventes_semaines.count()
    
    # ----------------------------------------------
    # Total de audits éffectué dans la semaine
    # ----------------------------------------------
    audit_semaines = AuditLog.objects.filter(
        date_action__range = [
            debut_semaine, fin_semaine
        ]
    )
    total_audit = audit_semaines.count()

    # -------------------------------------
    # Contexte pour le template
    # -------------------------------------
    context = {
        'profil': profil,
        'notifications': notifications,
        'non_lues': non_lues,
        'lues': lues,
        'derniers_audits': audits,
        'dernieres_ventes': dernieres_ventes[:5],
        'dernieeres_notification': notifications[:5],
        'produits_plus_vendus' : produits_plus_vendus,
        'total_produits': total_produits,
        'total_categories': total_categories,
        'total_commandes': total_commandes,
        'total_livraisons': total_livraisons,
        'total_audit' : total_audit,
        'total_ventes': total_ventes,
        'total_stock' : total_stock,
        'now': date.today(),
    }

    return render(request, 'dashboard.html', context)

# ===============================================
# Connexion
# ===============================================
def login_user(request):
    if request.method == 'POST':
        identifiant = request.POST.get('username')
        password = request.POST.get('password')
        username = identifiant

        if '@' in identifiant:
            try:
                user_obj = Utilisateur.objects.get(email=identifiant)
                username = user_obj.username
            except Utilisateur.DoesNotExist:
                messages.error(request, "Aucun utilisateur avec cet e-mail !")
                return redirect('gestionUtilisateur:connexion_utilisateur')

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('gestionUtilisateur:tableau_bord')
        else:
            messages.error(request, "Identifiant ou mot de passe incorrect !")
            return redirect('gestionUtilisateur:connexion_utilisateur')

    return render(request, 'gestion_utilisateurs/login.html')

# ===============================================
# Déconnexion
# ===============================================
def Logoutuser(request):
    logout(request)
    messages.success(request, 'Vous êtes maintenant déconnecté')
    return redirect('/')


# ===============================================
# Inscription
# ===============================================
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

        # Vérifications
        if not all([username, email, first_name, last_name, password1, password2, type_utilisateur, photo_utilisateur]):
            messages.error(request, "Tous les champs sont obligatoires !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if password1 != password2:
            messages.error(request, "Les mots de passe ne sont pas identiques !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if len(password1) < 6:
            messages.error(request, "Le mot de passe doit contenir au moins 6 caractères !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if Utilisateur.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur est déjà pris !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        if Utilisateur.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà enregistré !")
            return redirect('gestionUtilisateur:inscription_utilisateur')

        try:
            Utilisateur.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                type_utilisateur=type_utilisateur,
                photo_utilisateur=photo_utilisateur
            )
            messages.success(request, "Utilisateur ajouté avec succès.")
            return redirect('gestionUtilisateur:tableau_bord')
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {str(e)}")
    context = {
        'choix_utilisateur' : choix_utilisateur,
    }
    return render(request, 'gestion_utilisateurs/inscription_utilisateur.html', context)


# ===============================================
# Liste utilisateurs
# ===============================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def liste_utilisateur(request):
    listeuser_qs = Utilisateur.objects.all().order_by('last_name')
    pageuser = Paginator(listeuser_qs, 7)
    numpage = request.GET.get('page')
    listeuser = pageuser.get_page(numpage)
    context = {'listeuser': listeuser, 'total_utilisateur': listeuser_qs.count()}
    return render(request, 'gestion_utilisateurs/liste_utilisateur.html', context)


# ===============================================
# Modifier utilisateur
# ===============================================
@login_required(login_url='gestionUtilisateur:connexion_utilisateur')
def modifier_utilisateur(request, pk):
    utilisateur = get_object_or_404(Utilisateur, id=pk)
    if request.method == 'POST':
        if request.POST['password'] != request.POST['confirmation_password']:
            messages.warning(request, 'Vos mots de passe ne sont pas conformes')
        else:
            utilisateur.username = request.POST['username']
            utilisateur.email = request.POST['email']
            utilisateur.first_name = request.POST['first_name']
            utilisateur.last_name = request.POST['last_name']
            password = request.POST['password']
            if password:
                utilisateur.set_password(password)
            new_photo = request.FILES.get('new_photo_user')
            if new_photo:
                utilisateur.photo_utilisateur = new_photo
            utilisateur.save()
            messages.success(request, "Utilisateur modifié avec succès")
            return redirect('gestionUtilisateur:liste_utilisateur')
    return redirect('gestionUtilisateur:liste_utilisateur')


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
            # 🔒 2. Empêcher suppression si l'utilisateur a reçu des notifications
            if LigneVente.objects.filter(utilisateur=utilisateur_obj).exists():
                messages.warning(
                    request,
                    "❌ Impossible de supprimer cet utilisateur : il possède déjà des ventes enregistrées."
                )
                return redirect('gestionUtilisateur:liste_utilisateur')

            # 🔒 3. Empêcher suppression si l'utilisateur apparaît dans l'audit
            if AuditLog.objects.filter(utilisateur=utilisateur_obj).exists():
                messages.warning(
                    request,
                    "❌ Impossible de supprimer cet utilisateur : des actions auditées existent."
                )
                return redirect('gestionUtilisateur:liste_utilisateur')

            # --- 4. Audit avant suppression ---
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