from django.urls import path, include
from .views import *
from rest_framework.routers import DefaultRouter
from django.contrib.auth import views as auth_views

app_name = 'gestionUtilisateur'

urlpatterns = [
    #=========================================================================
    # ===== REST API =====
    #=========================================================================
    
    #=========================================================================

    # ===== Utilisateurs =====
    path('modificationUser/<int:pk>/', modifier_utilisateur, name="modification_User"),
    path('listeUser/', liste_utilisateur, name="liste_utilisateur"),
    path('inscription_utilisateur/', inscriptionutilisateur, name="inscription_utilisateur"),
    path('supprimer_utilisateur/', supprimerutilisateur, name="supprimerutilisateur"),
    path('tableau_bord/', home, name='tableau_bord'),
    path('connexion/', login_user, name='connexion_utilisateur'),
    path('deconnexion/', Logoutuser, name='deconnexion_utilisateur'),

        # Page publique d'accueil / bienvenue
    path('', page_bienvenue, name='page_bienvenue'),

    #=========================================================================

    # ===== Flow mot de passe =====
    # 1️⃣ Formulaire pour demander réinitialisation
    path(
        'reset_password/',
        CustomPasswordResetView.as_view(),
        name="password_reset"
    ),

    # 2️⃣ Page après envoi du mail
    path(
        'reset_password_sent/',
        auth_views.PasswordResetDoneView.as_view(
            template_name="allauth/password_reset_sent.html"
        ),
        name="password_reset_done"
    ),

    # 3️⃣ Formulaire pour définir nouveau mot de passe
    path(
        'reset/<uidb64>/<token>/',
        CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm"
    ),

    # 4️⃣ Page après succès du reset
    path(
        'reset_password_complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name="allauth/password_reset_complete.html"
        ),
        name="password_reset_complete"
    ),
]
