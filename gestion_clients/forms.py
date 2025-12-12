from django import forms
from .models import Clients

class FormClients(forms.ModelForm):
    
    class Meta:
        model = Clients
        fields = ('__all__',)
        labels = {
            'nomclt' : 'Nom du Client',
            'prenomclt' : 'Prénom du Client',
            'adresseclt' : 'Prénom du Client',
            'telclt' : 'Téléphone du Client',
            'emailclt' : 'Email du Client',
            'photoclt' : 'Photo du Client',
        }
        widgets = {
            'nomclt' : forms.TextInput(attrib={
                'class': 'form-control', 'placeholder': 'Veuillez entrer le nom', 'tilte' : 'Nom du Client'
                }, ),
            'prenomclt' : forms.TextInput(attrib={
                'class': 'form-control', 'placeholder': 'Veuillez entrer le prénom', 'tilte' : 'Prénom du Client'
                }, ),
            'adresseclt' : forms.TextInput(attrib={
                'class': 'form-control', 'placeholder': 'Veuillez entrer l\'adresse', 'tilte' : 'Adresse du Client'
                }, ),
            'telclt' : forms.TextInput(attrib={
                'class': 'form-control', 'placeholder': 'Veuillez entrer le Téléphone', 'tilte' : 'Téléphone du Client'
                }, ),
            'emailclt' : forms.EmailInput(attrib={
                'class': 'form-control', 'placeholder': 'Veuillez entrer l\'email', 'tilte' : 'Email du Client'
                }, ),
            'photoclt' : forms.FileInput(attrib={
                'class': 'form-control', 'placeholder': 'Veuillez séléctionner la photo', 'tilte' : 'Photo du Client'
                }, ),
        }
    def __init__(self, *args, **kwargs):
        super(FormClients, self).__init__(*args, **kwargs)
        
        
        
