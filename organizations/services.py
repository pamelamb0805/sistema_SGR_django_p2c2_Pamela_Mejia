"""
Capa de servicios de organizations (equivale a las clases CRUD* y Seguridad
del diagrama de clases). Las vistas NO escriben en la base: llaman a estos servicios,
que validan reglas de negocio, usan transacciones y registran auditoría.
"""
import json

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q

from core.exceptions import ReglaNegocioError
from core.mixins import auditar
from core.services import eliminar, guardar, snapshot

from .models import (
    Cargo, Delegacion, Funcionario, FuncionarioRol, ItemMedible, Rol, Usuario,
)

# Helpers compartidos (core.services)
_guardar = guardar
_eliminar = eliminar
_snapshot = snapshot


# ---------------------------------------------------------------------------
# CRUDDelegacion (RF-001)
# ---------------------------------------------------------------------------
class CRUDDelegacion:
    @staticmethod
    def crear_delegacion(delegacion, actor=None):
        return _guardar(delegacion, actor, "delegacion")

    @staticmethod
    def mostrar_todas_delegaciones():
        return Delegacion.objects.all()

    @staticmethod
    def buscar_delegacion_id(id_delegacion):
        return Delegacion.objects.filter(pk=id_delegacion).first()

    @staticmethod
    def modificar_delegacion(delegacion, actor=None):
        return _guardar(delegacion, actor, "delegacion")

    @staticmethod
    def activar_desactivar_delegacion(delegacion, actor=None):
        """Las delegaciones no se eliminan: se desactivan para conservar su historia."""
        delegacion.estado = Delegacion.ESTADO_INACTIVA if delegacion.activa else Delegacion.ESTADO_ACTIVA
        return _guardar(delegacion, actor, "delegacion")


# ---------------------------------------------------------------------------
# CRUDCargo (RF-003)
# ---------------------------------------------------------------------------
class CRUDCargo:
    @staticmethod
    def crear_cargo(cargo, actor=None):
        return _guardar(cargo, actor, "cargo")

    @staticmethod
    def mostrar_todos_cargos():
        return Cargo.objects.all()

    @staticmethod
    def asociar_funcion_al_cargo(item, actor=None):
        """Asocia un ítem medible a un cargo (item.cargo ya debe estar asignado)."""
        if item.cargo_id is None:
            raise ReglaNegocioError("El ítem debe pertenecer a un cargo.")
        return _guardar(item, actor, "item_medible")

    @staticmethod
    def cambiar_vigencia_item(item, actor=None):
        """Un ítem no vigente deja de cargarse a futuro, sin alterar registros históricos."""
        item.vigencia = not item.vigencia
        return _guardar(item, actor, "item_medible")

    @staticmethod
    def modificar_cargo(cargo, actor=None):
        return _guardar(cargo, actor, "cargo")

    @staticmethod
    def eliminar_cargo(cargo, actor=None):
        _eliminar(cargo, actor, "cargo",
                  "No se puede eliminar: el cargo tiene funcionarios o registros asociados. "
                  "Defina una fecha de vigencia final en su lugar.")


# ---------------------------------------------------------------------------
# CRUDRol (RF-002)
# ---------------------------------------------------------------------------
class CRUDRol:
    @staticmethod
    def crear_rol(rol, actor=None):
        return _guardar(rol, actor, "rol")

    @staticmethod
    def mostrar_roles():
        return Rol.objects.all()

    @staticmethod
    def modificar_rol(rol, actor=None):
        return _guardar(rol, actor, "rol")

    @staticmethod
    def eliminar_rol(rol, actor=None):
        _eliminar(rol, actor, "rol", "No se puede eliminar: el rol está asignado a funcionarios.")

    @staticmethod
    def asignar_rol_a_funcionario(funcionario, rol, actor=None):
        vinculo, creado = FuncionarioRol.objects.get_or_create(funcionario=funcionario, rol=rol)
        if creado:
            auditar(actor, "ASIGNAR_ROL", "funcionario_rol", vinculo.pk, None, rol.nombre_rol)
        return vinculo

    @staticmethod
    def sincronizar_roles(funcionario, roles, actor=None):
        """Deja al funcionario con exactamente los roles indicados (uno o más)."""
        nuevos = {r.pk: r for r in roles}
        if not nuevos:
            raise ReglaNegocioError("Debe asignar al menos un rol.")
        with transaction.atomic():
            actuales = set(funcionario.funcionario_roles.values_list("rol_id", flat=True))
            anterior = sorted(funcionario.funcionario_roles.values_list("rol__nombre_rol", flat=True))
            funcionario.funcionario_roles.exclude(rol_id__in=nuevos).delete()
            for rol_id in set(nuevos) - actuales:
                FuncionarioRol.objects.create(funcionario=funcionario, rol=nuevos[rol_id])
            if actuales != set(nuevos):
                auditar(actor, "MODIFICAR_ROLES", "funcionario", funcionario.pk,
                        json.dumps(anterior, ensure_ascii=False),
                        json.dumps(sorted(r.nombre_rol for r in nuevos.values()), ensure_ascii=False))


# ---------------------------------------------------------------------------
# CRUDFuncionario (RF-002)
# ---------------------------------------------------------------------------
class CRUDFuncionario:
    @staticmethod
    def crear_funcionario(funcionario, roles, actor=None):
        roles = list(roles)
        if not roles:
            raise ReglaNegocioError("Debe asignar al menos un rol.")
        with transaction.atomic():
            _guardar(funcionario, actor, "funcionario")
            CRUDRol.sincronizar_roles(funcionario, roles, actor)
        return funcionario

    @staticmethod
    def mostrar_todos_funcionarios():
        return Funcionario.objects.select_related("cargo", "delegacion")

    @staticmethod
    def buscar_funcionario_id(id_funcionario):
        return Funcionario.objects.filter(pk=id_funcionario).first()

    @staticmethod
    def buscar_funcionario_nombre(nombre):
        return Funcionario.objects.filter(
            Q(nombre__icontains=nombre) | Q(identificador_institucional__icontains=nombre))

    @staticmethod
    def modificar_funcionario(funcionario, roles, actor=None):
        roles = list(roles)
        if not roles:
            raise ReglaNegocioError("Debe asignar al menos un rol.")
        with transaction.atomic():
            _guardar(funcionario, actor, "funcionario")
            CRUDRol.sincronizar_roles(funcionario, roles, actor)
        return funcionario

    @staticmethod
    def cambiar_estado(funcionario, actor=None):
        """Activar/desactivar. Un funcionario inactivo no puede iniciar sesión."""
        funcionario.estado = (Funcionario.ESTADO_INACTIVO if funcionario.activo
                              else Funcionario.ESTADO_ACTIVO)
        return _guardar(funcionario, actor, "funcionario")

    @staticmethod
    def eliminar_funcionario(funcionario, actor=None):
        """Solo si no tiene registros operativos; de lo contrario se recomienda desactivar."""
        pk, anterior = funcionario.pk, _snapshot(funcionario)
        try:
            with transaction.atomic():
                Usuario.objects.filter(funcionario=funcionario).delete()
                funcionario.delete()
        except (ProtectedError, IntegrityError):
            raise ReglaNegocioError("No se puede eliminar: el funcionario tiene registros asociados. "
                                    "Desactívelo en su lugar.")
        auditar(actor, "ELIMINAR", "funcionario", pk, anterior, None)


# ---------------------------------------------------------------------------
# Seguridad (RNF-004, RNF-005)
# ---------------------------------------------------------------------------
class Seguridad:
    @staticmethod
    def verificar_usuario(username):
        usuario = Usuario.objects.select_related("funcionario").filter(username=username).first()
        return {"existe": usuario is not None, "activo": bool(usuario and usuario.is_active), "usuario": usuario}

    @staticmethod
    def verificar_credenciales(username, password):
        usuario = authenticate(username=username, password=password)
        return {"valido": usuario is not None, "usuario": usuario}

    @staticmethod
    def cifrar_datos(password):
        return make_password(password)

    @staticmethod
    def crear_usuario(funcionario, username, password, actor=None):
        username = (username or "").strip()
        if not username:
            raise ReglaNegocioError("El nombre de usuario es obligatorio.")
        if Usuario.objects.filter(funcionario=funcionario).exists():
            raise ReglaNegocioError("El funcionario ya tiene un acceso creado.")
        if Usuario.objects.filter(username__iexact=username).exists():
            raise ReglaNegocioError("Ese nombre de usuario ya está en uso.")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise ReglaNegocioError(" ".join(exc.messages))
        with transaction.atomic():
            usuario = Usuario.objects.create_user(username=username, password=password, funcionario=funcionario)
            auditar(actor, "CREAR", "usuario_acceso", usuario.pk, None, _snapshot(usuario))
        return usuario

    @staticmethod
    def cambiar_contrasenia(usuario, password, actor=None):
        try:
            validate_password(password, user=usuario)
        except ValidationError as exc:
            raise ReglaNegocioError(" ".join(exc.messages))
        usuario.set_password(password)
        usuario.save(update_fields=["password"])
        auditar(actor, "CAMBIO_CONTRASENIA", "usuario_acceso", usuario.pk, None, None)  # sin guardar la clave
        return usuario
