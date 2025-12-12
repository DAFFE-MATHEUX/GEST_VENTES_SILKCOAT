from rest_framework import serializers
from .models import *

class DepartementSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'