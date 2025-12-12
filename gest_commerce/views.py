
from django.shortcuts import render

#========================================================

def dashboard(request):
    return render(request, 'dashboard.html')

#========================================================

def calendar(request):
    return render(request, 'calendar.html')

#========================================================

def mailbox(request):
    return render(request, 'mailbox.html')

#========================================================
