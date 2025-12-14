
from django.core.paginator import (Paginator, PageNotAnInteger, EmptyPage)
from django.shortcuts import render
from django.contrib import messages
#==============1ère Méthode de la pagination en Django====================

def pagination_liste(request, listes):
    default_page = 1 # Spécifie la page par défaut
    items_per_page = 14 # 5 elements dans chaque page
    la_page = request.GET.get('pages') # Permet de recuperer la page 
    pagination = Paginator(listes, items_per_page)
    try:
        items_page = pagination.page(la_page) # items_page est un dictionnaire de liste
    except PageNotAnInteger: #Lorque la page n'est pas un entier ou un nombre
        items_page = pagination.page(default_page)
    except EmptyPage :
        # items_page = pagination.page(pagination.num_pages) #Lorsque la page demmadé est vide renvoyé la même page
        items_page = pagination.page(default_page) #Lorsque la page demmadé est vide renvoyé la 1ère page
        messages.error(request, "Les informations demmandé est vide")
    return items_page
#==================================================================================
#=============2eme Méthode de la pagination en Django==========================
def pagination_lis(request, liste):
    default_page = 1
    pageformat = Paginator(liste, 14)
    numero_page = request.GET.get('pages')
    try:
        items_page = pageformat.page(numero_page) # items_page est un dictionnaire de liste
    except PageNotAnInteger:
        items_page = pageformat.page(default_page)
    except EmptyPage :
        items_page = pageformat.page(pageformat.num_pages)
    liste = pageformat.get_page(items_page)
    return liste 
#==================================================================================