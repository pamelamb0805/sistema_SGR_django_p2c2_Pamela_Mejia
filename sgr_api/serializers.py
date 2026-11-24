
from rest_framework import serializers

from organizations.models import Delegacion


class DelegacionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Delegacion

        fields = [
            "id_delegacion",
            "codigo",
            "nombre",
            "direccion",
            "comuna",
            "estado",
            "ambito",
        ]

        read_only_fields = [
            "id_delegacion",
        ]
