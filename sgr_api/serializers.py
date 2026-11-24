
from rest_framework import serializers

from organizations.models import (
    Delegacion,
    Rol,
    Funcionario,
    Cargo,
)


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
        read_only_fields = ["id_delegacion"]


class RolSerializer(serializers.ModelSerializer):

    permisos = serializers.ListField(
        child=serializers.CharField(
            allow_blank=False,
            trim_whitespace=True,
        ),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Rol
        fields = [
            "id_rol",
            "nombre_rol",
            "descripcion",
            "permisos",
            "alcance_autorizado",
        ]
        read_only_fields = ["id_rol"]

    def validate_nombre_rol(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El nombre del rol es obligatorio."
            )

        return value

    def validate_permisos(self, value):
        permisos_limpios = [
            permiso.strip()
            for permiso in value
            if permiso.strip()
        ]

        return list(dict.fromkeys(permisos_limpios))


class FuncionarioSerializer(serializers.ModelSerializer):

    cargo_nombre = serializers.CharField(
        source="cargo.nombre_cargo",
        read_only=True,
    )

    delegacion_nombre = serializers.CharField(
        source="delegacion.nombre",
        read_only=True,
    )

    roles = serializers.SerializerMethodField()

    roles_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Rol.objects.all(),
        write_only=True,
        required=True,
    )

    usuario_acceso = serializers.SerializerMethodField()

    class Meta:
        model = Funcionario
        fields = [
            "id_funcionario",
            "identificador_institucional",
            "nombre",
            "estado",
            "cargo",
            "cargo_nombre",
            "delegacion",
            "delegacion_nombre",
            "roles",
            "roles_ids",
            "usuario_acceso",
        ]

        read_only_fields = [
            "id_funcionario",
            "cargo_nombre",
            "delegacion_nombre",
            "roles",
            "usuario_acceso",
        ]

    def validate_identificador_institucional(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El identificador institucional es obligatorio."
            )

        return value

    def validate_nombre(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El nombre del funcionario es obligatorio."
            )

        return value

    def validate_roles_ids(self, value):
        if not value:
            raise serializers.ValidationError(
                "Debe asignar al menos un rol."
            )

        return value

    def get_roles(self, obj):
        return [
            {
                "id_rol": rol.pk,
                "nombre_rol": rol.nombre_rol,
            }
            for rol in obj.roles.all().order_by("nombre_rol")
        ]

    def get_usuario_acceso(self, obj):
        usuario = getattr(obj, "usuario", None)

        if usuario is None:
            return None

        return {
            "id_usuario": usuario.pk,
            "username": usuario.username,
            "email": usuario.email,
            "activo_acceso": usuario.activo_acceso,
            "is_active": usuario.is_active,
        }
