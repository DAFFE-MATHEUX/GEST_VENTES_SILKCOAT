from django.contrib import admin

from .models import Produits, CategorieProduit, Commandes, Livraisons
# Register your models here.

admin.register(Produits)
admin.register(CategorieProduit)
admin.register(Commandes)
admin.register(Livraisons)