from rest_framework import serializers

from organizations.models import Delegacion


class DelegacionSerializer(serializers.ModelSerializer):
    """
    Representación JSON de una delegación.
    En esta primera etapa se utiliza para consultas.
    """

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
        read_only_fields = fields