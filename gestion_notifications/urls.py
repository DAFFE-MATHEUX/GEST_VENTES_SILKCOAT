from django.urls import include, path
from . import views
from rest_framework.routers import DefaultRouter
from .views import Notification_View_Set
app_name = "notifications"

router = DefaultRouter()
router.register(r'', Notification_View_Set)

urlpatterns = [
    
    #===============================================================================================
    # Urls Django restframework
    #===============================================================================================
    
    path('notification/', include(router.urls)),
    #===============================================================================================

    path('marquer_notification_lue/<int:id>/', views.marquer_notification_lue, name='marquer_notification_lue'),
    path('marquer_tout_lu/', views.marquer_tout_lu, name='marquer_tout_lu'),
    path("listes_totales_notification/", views.listes_totales_notification, name="listes_totales_notification"),
    path("filtrer_listes_notifications/", views.filtrer_listes_notifications, name="filtrer_listes_notifications"),
    path("supprimer_notification/", views.supprimer_notification, name="supprimer_notification"),
    path("liste_notifications_global/<str:utilisateur>/", views.liste_notifications_global, name="liste_notifications_global"),
    
    #==========================================================================
    # Impression listes
    #==========================================================================
    
    path('choix_par_dates_notification_impression/', views.choix_par_dates_notification_impression, name="choix_par_dates_notification_impression"),
    path('listes_notifications_impression/', views.listes_notifications_impression, name="listes_notifications_impression"),
    
]
