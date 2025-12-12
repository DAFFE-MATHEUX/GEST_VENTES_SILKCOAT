from django.urls import include, path
from . import views
from rest_framework.routers import DefaultRouter
from .views import Notification_View_Set
app_name = "notifications"

router = DefaultRouter()
router.register(r'notification', Notification_View_Set)

urlpatterns = [
    
    #===============================================================================================
    # Urls Django restframework
    #===============================================================================================
    
    path('', include(router.urls)),
    #===============================================================================================
    
    
    path('marquer_notification_lue/<int:id>/', views.marquer_notification_lue, name='marquer_notification_lue'),
    path('marquer_tout_lu/', views.marquer_tout_lu, name='marquer_tout_lu'),
    path("dashboard_notification/", views.Dashboard_Notification, name="dashboard_notification"),
    path("listes_totales_notification/", views.listes_totales_notification, name="listes_totales_notification"),
    path("filtrer_listes_notifications/", views.filtrer_listes_notifications, name="filtrer_listes_notifications"),
    path("liste_notifications_global/<str:utilisateur>/", views.liste_notifications_global, name="liste_notifications_global"),
    
]
