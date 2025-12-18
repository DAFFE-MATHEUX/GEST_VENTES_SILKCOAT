from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Notification
from django.contrib.auth.decorators import login_required
from gestion_utilisateur.models import Utilisateur
from .utils import pagination_liste
from rest_framework import viewsets
from .models_serializers import NotificationSerializer
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Notification
from gest_entreprise.models import Entreprise
from django.utils import timezone
#=================================================================================
class Notification_View_Set(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

#=================================================================================

@login_required
def liste_notifications_global(request, utilisateur):
    # Vérifie que l'utilisateur existe
    user = get_object_or_404(Utilisateur, username=utilisateur)
    
    # Récupère les notifications destinées à cet utilisateur
    listes_notifications_global = Notification.objects.filter(destinataire=user).order_by('-date')
    
    context = {
        "listes_notifications_global": listes_notifications_global,
        "utilisateur": user,
    }
    return render(request, "gestion_notifications/liste_notifications.html", context)


@login_required
def marquer_notification_lue(request, id):
    notif = get_object_or_404(Notification, id=id, destinataire=request.user)
    notif.lu = True
    notif.save()
    return redirect('gestionUtilisateur:tableau_bord')  # ou une autre page

@login_required
def marquer_tout_lu(request):
    Notification.objects.filter(destinataire=request.user, lu=False).update(lu=True)
    return redirect('gestionUtilisateur:tableau_bord')


@receiver(post_save, sender=Notification)
def envoyer_email_notification(sender, instance, created, **kwargs):
    """
    ✅ Signal appelé automatiquement après la création d'une notification.
    Il envoie un email au parent (destinataire_email) et/ou à l'administrateur (destinataire).
    """
    if not created:
        return  # uniquement à la création

    sujet = instance.titre or "Nouvelle notification"
    message = instance.message
    expediteur = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@etablissement.com")
    destinataires = []

    # 🔹 Email du parent (si renseigné)
    if instance.destinataire_email:
        destinataires.append(instance.destinataire_email)

    # 🔹 Email de l'utilisateur interne (admin, prof, etc.)
    if instance.destinataire and instance.destinataire.email:
        destinataires.append(instance.destinataire.email)

    # 🔹 Envoi de l'email s'il y a au moins un destinataire
    if destinataires:
        try:
            send_mail(
                sujet,
                message,
                expediteur,
                destinataires,
                fail_silently=False,
            )
            print(f"✅ Email envoyé à : {', '.join(destinataires)}")
        except Exception as e:
            print(f"❌ Erreur lors de l’envoi de l’email : {e}")



def messagerie(request):
    utilisateur = request.user

    # Récupération des notifications de l'utilisateur
    notifications = Notification.objects.filter(destinataire=utilisateur).order_by('-date')

    # Transformation en dictionnaire pour le template
    mails = [
        {
            "expediteur": notif.destinataire.get_full_name() if notif.destinataire else "Inconnu",
            "objet": notif.titre or "Sans titre",
            "heure": notif.date.strftime("%H:%M") if notif.date else "-",
            "lu": notif.lu,
            "starred": False,  # tu peux ajouter un champ starred dans le modèle si besoin
        }
        for notif in notifications
    ]

    context = {
        "mails": mails,
    }
    return render(request, "mailbox.html", context)

@login_required
def listes_totales_notification(request):
    # Tous les notifications
    listes_notifications = Notification.objects.all().order_by('-date')
    
    # Total avant pagination
    total_notification = listes_notifications.count()
    
    # Pagination
    listes_notifications = pagination_liste(request, listes_notifications)
    
    return render(request, 'gestion_notifications/listes_notifications_totale.html', {
        'listes_notifications': listes_notifications,
        'total_notification': total_notification,
    })
    
@login_required
def filtrer_listes_notifications(request):
    """
    Filtre les notiifcations selon la date et l'utilisateur.
    """
    try:
        # Récupération de toutes les notifications
        listes_notifications = Notification.objects.all().order_by("-date")

        # Récupération des filtres GET
        date_debut = request.GET.get("date_debut")
        date_fin = request.GET.get("date_fin")

        # Filtrage initial
        listes_notifications_filtre = listes_notifications

        # Filtre par date si défini
        if date_debut and date_fin:
            listes_notifications_filtre = listes_notifications_filtre.filter(
                date__range=(date_debut, date_fin)
            )

        # Pagination après le filtrage
        listes_notifications_filtre_pagine = pagination_liste(request, listes_notifications_filtre)

        # Total avant pagination
        total_notification = listes_notifications_filtre.count()

    except Exception as ex:
        messages.warning(request, f"Erreur de filtrage des données : {str(ex)}")
        
        listes_notifications_filtre_pagine = []
        total_notification = 0
        date_debut = None
        date_fin = None

    context = {
        "date_debut": date_debut,
        "date_fin": date_fin,
        "listes_notifications_filtre_pagine": listes_notifications_filtre_pagine,
        "total_notification": total_notification,
    }

    return render(request, "gestion_notifications/listes_notifications_totale.html", context)


#================================================================================================
# Fonction pour afficher le formulaire de choix de dates de saisie pour l'impression des Notifications
#================================================================================================
@login_required
def choix_par_dates_notification_impression(request):
    return render(request, 'gestion_notifications/impression_listes/fiches_choix_impression_notifications.html')

#================================================================================================
# Fonction pour imprimer la listes des Notifications
#================================================================================================
@login_required
def listes_notifications_impression(request):
    
    try:
        date_debut = request.POST.get('date_debut')
        date_fin = request.POST.get('date_fin')
    except Exception as ex:
        messages.warning(request, f"Erreur de récupération des dates : {str(ex)}")

    except ValueError as ve:
        messages.warning(request, f"Erreur de type de données : {str(ve)}")
        
    listes_notifications = Notification.objects.filter(
        date__range=[date_debut, date_fin]
    )

    nom_entreprise = Entreprise.objects.first()
    context = {
        'nom_entreprise': nom_entreprise,
        'today': timezone.now(),
        'listes_notifications' : listes_notifications,
    }
    return render(
        request,
        'gestion_notifications/impression_listes/apercue_avant_impression_listes_notifications.html',
        context
    )
