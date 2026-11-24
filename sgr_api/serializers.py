
from rest_framework import serializers

from organizations.models import (
    Usuario,
    Delegacion,
    Rol,
    Funcionario,
    Cargo,
    ItemMedible,
)
from measurement.models import Meta as MetaModel, Periodo

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
class UsuarioSerializer(serializers.ModelSerializer):

    funcionario_nombre = serializers.CharField(
        source="funcionario.nombre",
        read_only=True,
    )

    funcionario_identificador = serializers.CharField(
        source="funcionario.identificador_institucional",
        read_only=True,
    )

    delegaciones_autorizadas = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "email",
            "funcionario",
            "funcionario_nombre",
            "funcionario_identificador",
            "delegaciones_autorizadas",
            "roles",
            "activo_acceso",
            "is_active",
            "fecha_creacion",
        ]

        read_only_fields = [
            "id",
            "funcionario_nombre",
            "funcionario_identificador",
            "roles",
            "is_active",
            "fecha_creacion",
        ]

    def get_delegaciones_autorizadas(self, obj):
        return [
            {
                "id_delegacion": delegacion.pk,
                "nombre": delegacion.nombre,
            }
            for delegacion in obj.delegaciones_autorizadas.all()
        ]

    def get_roles(self, obj):
        if not obj.funcionario_id:
            return []

        return [
            {
                "id_rol": rol.pk,
                "nombre_rol": rol.nombre_rol,
            }
            for rol in obj.funcionario.roles.all().order_by(
                "nombre_rol"
            )
        ]

class ItemMedibleSerializer(serializers.ModelSerializer):
    cargo_nombre = serializers.CharField(
        source="cargo.nombre_cargo",
        read_only=True,
    )

    class Meta:
        model = ItemMedible
        fields = [
            "id_item",
            "codigo",
            "nombre_item",
            "descripcion",
            "tipo",
            "vigencia",
            "contabiliza_compromisos",
            "cargo",
            "cargo_nombre",
        ]
        read_only_fields = [
            "id_item",
            "cargo_nombre",
        ]

    def validate_codigo(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El código del ítem es obligatorio."
            )

        return value

    def validate_nombre_item(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El nombre del ítem es obligatorio."
            )

        return value

class MetaSerializer(serializers.ModelSerializer):
    funcionario_nombre = serializers.CharField(
        source="funcionario.nombre",
        read_only=True,
    )

    item_nombre = serializers.CharField(
        source="item.nombre_item",
        read_only=True,
    )

    periodo_descripcion = serializers.SerializerMethodField()

    cargo = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )

    aplicar_a_cargo = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )

    class Meta:
        model = MetaModel
        fields = [
            "id_meta",
            "periodo",
            "funcionario",
            "funcionario_nombre",
            "item",
            "item_nombre",
            "valor_objetivo",
            "unidad",
            "ponderador",
            "umbral_minimo",
            "maximo_computable",
            "fecha_version",
            "cargo",
            "aplicar_a_cargo",
            "periodo_descripcion",
        ]

        read_only_fields = [
            "id_meta",
            "fecha_version",
            "cargo",
            "funcionario_nombre",
            "item_nombre",
            "periodo_descripcion",
        ]

    def get_periodo_descripcion(self, obj):
        return str(obj.periodo)

    def validate(self, attrs):
        funcionario = attrs.get(
            "funcionario",
            getattr(self.instance, "funcionario", None),
        )

        item = attrs.get(
            "item",
            getattr(self.instance, "item", None),
        )

        if funcionario and item:
            if funcionario.cargo_id != item.cargo_id:
                raise serializers.ValidationError({
                    "item": (
                        "El ítem medible no pertenece "
                        "al cargo del funcionario."
                    )
                })

        if self.instance:
            for campo in ("periodo", "funcionario", "item"):
                if campo in attrs:
                    valor_original = getattr(
                        self.instance,
                        f"{campo}_id",
                    )

                    if attrs[campo].pk != valor_original:
                        raise serializers.ValidationError({
                            campo: (
                                "No se puede cambiar esta relación "
                                "en una meta existente."
                            )
                        })

        return attrs
