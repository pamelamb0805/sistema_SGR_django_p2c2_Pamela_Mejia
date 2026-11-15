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
from core.mixins import auditar, filtrar_por_ambito
from core.services import (
    eliminar,
    guardar,
    snapshot,
    _notificar_crud,
)

from .models import (
    Cargo, Delegacion, Funcionario, FuncionarioRol, ItemMedible, Rol, Usuario,
)
from django.utils import timezone

# Helpers compartidos (core.services)
_guardar = guardar
_eliminar = eliminar
_snapshot = snapshot
def _validar_ambito_asignacion(
    actor,
    queryset,
    campo,
    objeto_id,
    entidad,
    mensaje,
):
    """
    Comprueba que el actor pueda operar sobre el objeto
    según sus delegaciones y alcances autorizados.

    Registra los intentos de asignación fuera del ámbito.
    """

    if actor is None:
        return

    if not getattr(actor, "is_authenticated", False):
        return

    if getattr(actor, "is_superuser", False):
        return

    autorizado = (
        filtrar_por_ambito(
            queryset,
            actor,
            campo,
        )
        .filter(pk=objeto_id)
        .exists()
    )

    if not autorizado:
        auditar(
            actor,
            "ACCESO_DENEGADO",
            entidad,
            objeto_id,
            None,
            mensaje,
        )

        raise ReglaNegocioError(mensaje)


def _validar_delegaciones_asignables(
    actor,
    delegaciones,
):
    """
    Impide asignar delegaciones fuera del ámbito autorizado
    del administrador que realiza la operación.
    """

    for delegacion in delegaciones:
        _validar_ambito_asignacion(
            actor=actor,
            queryset=Delegacion.objects.all(),
            campo="id_delegacion",
            objeto_id=delegacion.pk,
            entidad="delegacion",
            mensaje=(
                "No tienes autorización para asignar "
                "esa delegación."
            ),
        )

# ---------------------------------------------------------------------------
# CRUDDelegacion (RF-001)
# ---------------------------------------------------------------------------

class CRUDDelegacion:

    @staticmethod
    def _datos_version(delegacion):
        return delegacion.obtener_datos_actuales()

    @staticmethod
    def crear_delegacion(delegacion, actor=None):
        delegacion.nombre = (delegacion.nombre or "").strip()
        delegacion.codigo = (delegacion.codigo or "").strip()
        delegacion.direccion = (delegacion.direccion or "").strip()
        delegacion.comuna = (delegacion.comuna or "").strip()
        delegacion.ambito = (delegacion.ambito or "").strip()

        if not delegacion.nombre:
            raise ReglaNegocioError(
                "El nombre de la delegación es obligatorio."
            )

        if not delegacion.codigo:
            raise ReglaNegocioError(
                "El código de la delegación es obligatorio."
            )

        if Delegacion.objects.filter(
            nombre__iexact=delegacion.nombre
        ).exists():
            raise ReglaNegocioError(
                "Ya existe una delegación con ese nombre."
            )

        if Delegacion.objects.filter(
            codigo__iexact=delegacion.codigo
        ).exists():
            raise ReglaNegocioError(
                "Ya existe una delegación con ese código."
            )

        ahora = timezone.now()

        delegacion.historial_versiones = [{
            "numero_version": 1,
            "vigente_desde": ahora.isoformat(),
            "vigente_hasta": None,
            "datos": CRUDDelegacion._datos_version(delegacion),
        }]

        return _guardar(delegacion, actor, "delegacion")

    @staticmethod
    def mostrar_todas_delegaciones():
        return Delegacion.objects.all()

    @staticmethod
    def buscar_delegacion_id(id_delegacion):
        return Delegacion.objects.filter(
            pk=id_delegacion
        ).first()

    @staticmethod
    def modificar_delegacion(delegacion, actor=None):
        with transaction.atomic():
            original = (
                Delegacion.objects
                .select_for_update()
                .get(pk=delegacion.pk)
            )

            delegacion.nombre = (delegacion.nombre or "").strip()
            delegacion.codigo = (delegacion.codigo or "").strip()
            delegacion.direccion = (delegacion.direccion or "").strip()
            delegacion.comuna = (delegacion.comuna or "").strip()
            delegacion.ambito = (delegacion.ambito or "").strip()

            if not delegacion.nombre:
                raise ReglaNegocioError(
                    "El nombre de la delegación es obligatorio."
                )

            if not delegacion.codigo:
                raise ReglaNegocioError(
                    "El código de la delegación es obligatorio."
                )

            if Delegacion.objects.filter(
                nombre__iexact=delegacion.nombre
            ).exclude(pk=delegacion.pk).exists():
                raise ReglaNegocioError(
                    "Ya existe una delegación con ese nombre."
                )

            if Delegacion.objects.filter(
                codigo__iexact=delegacion.codigo
            ).exclude(pk=delegacion.pk).exists():
                raise ReglaNegocioError(
                    "Ya existe una delegación con ese código."
                )

            campos = (
                "codigo",
                "nombre",
                "direccion",
                "comuna",
                "ambito",
                "estado",
            )

            datos_anteriores = original.obtener_datos_actuales()
            datos_nuevos = delegacion.obtener_datos_actuales()

            cambio = any(
                datos_anteriores.get(campo) != datos_nuevos.get(campo)
                for campo in campos
            )

            historial = list(original.historial_versiones or [])

            if cambio:
                ahora = timezone.now()
                ahora_iso = ahora.isoformat()

                if not historial:
                    historial.append({
                        "numero_version": 1,
                        "vigente_desde": None,
                        "vigente_hasta": ahora_iso,
                        "datos": datos_anteriores,
                    })
                    numero = 2
                else:
                    ultima = dict(historial[-1])
                    ultima["vigente_hasta"] = ahora_iso
                    historial[-1] = ultima

                    numero = max(
                        int(version.get("numero_version", 0))
                        for version in historial
                    ) + 1

                historial.append({
                    "numero_version": numero,
                    "vigente_desde": ahora_iso,
                    "vigente_hasta": None,
                    "datos": datos_nuevos,
                })

            delegacion.historial_versiones = historial

            return _guardar(
                delegacion,
                actor,
                "delegacion",
            )

    @staticmethod
    def activar_desactivar_delegacion(delegacion, actor=None):
        with transaction.atomic():
            original = (
                Delegacion.objects
                .select_for_update()
                .get(pk=delegacion.pk)
            )

            original.estado = (
                Delegacion.ESTADO_INACTIVA
                if original.activa
                else Delegacion.ESTADO_ACTIVA
            )

            return CRUDDelegacion.modificar_delegacion(
                original,
                actor,
            )

# ---------------------------------------------------------------------------
# CRUDCargo (RF-003 y versionamiento RF-038)
# ---------------------------------------------------------------------------

class CRUDCargo:

    @staticmethod
    def _datos_version_item(item):
        return {
            "codigo": item.codigo,
            "nombre_item": item.nombre_item,
            "descripcion": item.descripcion,
            "tipo": item.tipo,
            "vigencia": item.vigencia,
            "cargo_id": item.cargo_id,
            "cargo_nombre": (
                item.cargo.nombre_cargo
                if item.cargo_id
                else None
            ),
        }

    @staticmethod
    def _registrar_version_item(item, actor=None):
        from django.utils import timezone
        from .models import ItemMedibleVersion

        ultima = (
            ItemMedibleVersion.objects
            .select_for_update()
            .filter(objeto_id=item.pk)
            .order_by("-numero_version")
            .first()
        )

        ahora = timezone.now()

        if ultima:
            ultima.vigente_hasta = ahora
            ultima.save(update_fields=["vigente_hasta"])
            numero = ultima.numero_version + 1
        else:
            numero = 1

        ItemMedibleVersion.objects.create(
            objeto_id=item.pk,
            numero_version=numero,
            vigente_desde=ahora,
            datos=CRUDCargo._datos_version_item(item),
            creado_por=(
                actor
                if getattr(actor, "is_authenticated", False)
                else None
            ),
        )

    @staticmethod
    def crear_cargo(cargo, actor=None):
        return _guardar(cargo, actor, "cargo")

    @staticmethod
    def mostrar_todos_cargos():
        return Cargo.objects.all()

    @staticmethod
    def asociar_funcion_al_cargo(item, actor=None):
        """Registra el ítem y su primera versión histórica."""

        if item.cargo_id is None:
            raise ReglaNegocioError(
                "El ítem debe pertenecer a un cargo."
            )

        with transaction.atomic():
            item = _guardar(item, actor, "item_medible")
            CRUDCargo._registrar_version_item(item, actor)

        return item

    @staticmethod
    def modificar_item(item, actor=None):
        """Modifica el ítem conservando su versión anterior."""

        with transaction.atomic():
            original = (
                ItemMedible.objects
                .select_for_update()
                .get(pk=item.pk)
            )

            if original.cargo_id != item.cargo_id:
                raise ReglaNegocioError(
                    "No se puede cambiar el cargo de un ítem medible "
                    "que ya está registrado. Cree un nuevo ítem."
                )

            item = _guardar(item, actor, "item_medible")
            CRUDCargo._registrar_version_item(item, actor)

        return item

    @staticmethod
    def cambiar_vigencia_item(item, actor=None):
        """Cambia la vigencia y conserva el historial."""

        with transaction.atomic():
            item = (
                ItemMedible.objects
                .select_for_update()
                .get(pk=item.pk)
            )

            item.vigencia = not item.vigencia
            item = _guardar(item, actor, "item_medible")

            CRUDCargo._registrar_version_item(item, actor)

        return item

    @staticmethod
    def modificar_cargo(cargo, actor=None):
        return _guardar(cargo, actor, "cargo")

    @staticmethod
    def eliminar_cargo(cargo, actor=None):
        _eliminar(
            cargo,
            actor,
            "cargo",
            "No se puede eliminar: el cargo tiene funcionarios "
            "o registros asociados. Defina una fecha de vigencia "
            "final en su lugar.",
        )

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
        with transaction.atomic():
            vinculo, creado = FuncionarioRol.objects.get_or_create(
                funcionario=funcionario,
                rol=rol,
            )

            if creado:
                auditar(
                    actor,
                    "ASIGNAR_ROL",
                    "funcionario_rol",
                    vinculo.pk,
                    None,
                    rol.nombre_rol,
                )

                _notificar_crud(
                    "funcionario_rol",
                    "crear",
                    actor,
                    vinculo,
                    delegacion_id=funcionario.delegacion_id,
                )

        return vinculo

    @staticmethod
    def sincronizar_roles(funcionario, roles, actor=None):
        """Deja al funcionario con exactamente los roles indicados."""
        nuevos = {rol.pk: rol for rol in roles}

        if not nuevos:
            raise ReglaNegocioError(
                "Debe asignar al menos un rol."
            )

        with transaction.atomic():
            actuales = set(
                funcionario.funcionario_roles.values_list(
                    "rol_id",
                    flat=True,
                )
            )

            anterior = sorted(
                funcionario.funcionario_roles.values_list(
                    "rol__nombre_rol",
                    flat=True,
                )
            )

            ids_nuevos = set(nuevos)

            if actuales == ids_nuevos:
                return

            funcionario.funcionario_roles.exclude(
                rol_id__in=ids_nuevos
            ).delete()

            for rol_id in ids_nuevos - actuales:
                FuncionarioRol.objects.create(
                    funcionario=funcionario,
                    rol=nuevos[rol_id],
                )

            auditar(
                actor,
                "MODIFICAR_ROLES",
                "funcionario",
                funcionario.pk,
                json.dumps(
                    anterior,
                    ensure_ascii=False,
                ),
                json.dumps(
                    sorted(
                        rol.nombre_rol
                        for rol in nuevos.values()
                    ),
                    ensure_ascii=False,
                ),
            )

            _notificar_crud(
                "funcionario",
                "actualizar",
                actor,
                funcionario,
                delegacion_id=funcionario.delegacion_id,
            )

# ---------------------------------------------------------------------------
# CRUDFuncionario (RF-002)
# ---------------------------------------------------------------------------
class CRUDFuncionario:
    @staticmethod
    def crear_funcionario(funcionario, roles, actor=None):
        roles = list(roles)

        if not roles:
            raise ReglaNegocioError(
                "Debe asignar al menos un rol."
            )

        if not funcionario.delegacion.activa:
            raise ReglaNegocioError(
                "No se puede asignar un funcionario a una "
                "delegación inactiva."
            )

        _validar_ambito_asignacion(
            actor=actor,
            queryset=Delegacion.objects.all(),
            campo="id_delegacion",
            objeto_id=funcionario.delegacion_id,
            entidad="funcionario",
            mensaje=(
                "No tienes autorización para registrar "
                "funcionarios en esa delegación."
            ),
        )

        with transaction.atomic():
            _guardar(
                funcionario,
                actor,
                "funcionario",
            )

            CRUDRol.sincronizar_roles(
                funcionario,
                roles,
                actor,
            )

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
            raise ReglaNegocioError(
                "Debe asignar al menos un rol."
            )

        with transaction.atomic():
            original = (
                Funcionario.objects
                .select_for_update()
                .get(pk=funcionario.pk)
            )

            cambio_de_delegacion = (
                original.delegacion_id
                != funcionario.delegacion_id
            )

            if (
                cambio_de_delegacion
                and not funcionario.delegacion.activa
            ):
                raise ReglaNegocioError(
                    "No se puede cambiar un funcionario a una "
                    "delegación inactiva."
                )

            _validar_ambito_asignacion(
                actor=actor,
                queryset=Delegacion.objects.all(),
                campo="id_delegacion",
                objeto_id=funcionario.delegacion_id,
                entidad="funcionario",
                mensaje=(
                    "No tienes autorización para asignar "
                    "ese funcionario a esa delegación."
                ),
            )

            _guardar(
                funcionario,
                actor,
                "funcionario",
            )

            CRUDRol.sincronizar_roles(
                funcionario,
                roles,
                actor,
            )

        return funcionario
    @staticmethod
    def cambiar_estado(funcionario, actor=None):
        """
        Activa o desactiva un funcionario.

        El estado del funcionario también determina
        si su usuario puede iniciar sesión.
        """

        _validar_ambito_asignacion(
            actor=actor,
            queryset=Delegacion.objects.all(),
            campo="id_delegacion",
            objeto_id=funcionario.delegacion_id,
            entidad="funcionario",
            mensaje=(
                "No tienes autorización para modificar "
                "este funcionario."
            ),
        )

        funcionario.estado = (
            Funcionario.ESTADO_INACTIVO
            if funcionario.activo
            else Funcionario.ESTADO_ACTIVO
        )

        return _guardar(
            funcionario,
            actor,
            "funcionario",
        )
    @staticmethod
    def eliminar_funcionario(funcionario, actor=None):
        """
        Elimina un funcionario y su cuenta de acceso cuando no existen
        relaciones operativas que impidan la eliminación.

        Conserva la auditoría y publica el evento WebSocket después
        de confirmar la transacción.
        """
        pk = funcionario.pk
        anterior = _snapshot(funcionario)
        etiqueta = str(funcionario)

        delegacion_id = funcionario.delegacion_id

        try:
            with transaction.atomic():

                # Eliminar la cuenta asociada, si existe.
                Usuario.objects.filter(
                    funcionario=funcionario
                ).delete()

                # Eliminar el funcionario.
                funcionario.delete()

                # Registrar auditoría dentro de la transacción.
                auditar(
                    actor,
                    "ELIMINAR",
                    "funcionario",
                    pk,
                    anterior,
                    None,
                )

                # Publicar solamente después del COMMIT.
                _notificar_crud(
                    entidad="funcionario",
                    accion="eliminar",
                    actor=actor,
                    instancia=funcionario,
                    object_id=pk,
                    object_label=etiqueta,
                    delegacion_id=delegacion_id,
                )

        except (ProtectedError, IntegrityError):
            raise ReglaNegocioError(
                "No se puede eliminar: el funcionario tiene "
                "registros asociados. Desactívelo en su lugar."
            )

        return True

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
    def crear_usuario(
        funcionario,
        username,
        password,
        actor=None,
        email=None,
        delegaciones=None,
    ):
        username = (username or "").strip()
        email = (email or "").strip().lower()
        delegaciones = list(delegaciones or [])

        if funcionario is None:
            raise ReglaNegocioError(
                "Debes asociar la cuenta a un funcionario."
            )

        if not funcionario.activo:
            raise ReglaNegocioError(
                "No se puede crear acceso para un funcionario inactivo."
            )

        if not funcionario.delegacion.activa:
            raise ReglaNegocioError(
                "La delegación del funcionario está inactiva."
            )

        if not username:
            raise ReglaNegocioError(
                "El nombre de usuario es obligatorio."
            )

        if not password:
            raise ReglaNegocioError(
                "La contraseña es obligatoria."
            )

        if Usuario.objects.filter(
            funcionario=funcionario
        ).exists():
            raise ReglaNegocioError(
                "El funcionario ya tiene un acceso creado."
            )

        if Usuario.objects.filter(
            username__iexact=username
        ).exists():
            raise ReglaNegocioError(
                "Ese nombre de usuario ya está en uso."
            )

        if email and Usuario.objects.filter(
            email__iexact=email
        ).exists():
            raise ReglaNegocioError(
                "Ese correo ya está asociado a otra cuenta."
            )

        # La validación se hace contra la delegación,
        # no contra el identificador del funcionario.
        _validar_ambito_asignacion(
            actor=actor,
            queryset=Delegacion.objects.all(),
            campo="id_delegacion",
            objeto_id=funcionario.delegacion_id,
            entidad="usuario",
            mensaje=(
                "No tienes autorización para crear "
                "accesos en esa delegación."
            ),
        )

        _validar_delegaciones_asignables(
            actor,
            delegaciones,
        )

        Seguridad.validar_delegaciones(
            funcionario,
            delegaciones,
        )

        try:
            validate_password(password)
        except ValidationError as exc:
            raise ReglaNegocioError(
                " ".join(exc.messages)
            )

        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                username=username,
                email=email,
                password=password,
                funcionario=funcionario,
                activo_acceso=True,
            )

            usuario.delegaciones_autorizadas.set(
                delegaciones
            )

            auditar(
                actor,
                "CREAR",
                "usuario_acceso",
                usuario.pk,
                None,
                _snapshot(usuario),
            )

            _notificar_crud(
                "usuario",
                "crear",
                actor,
                usuario,
                delegacion_id=funcionario.delegacion_id,
            )

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



    @staticmethod
    def guardar_usuario(form, actor=None):
        """
        Crea o modifica un usuario de acceso.

        Permite conservar relaciones históricas con funcionarios
        o delegaciones inactivas, pero impide crear o reasignar
        cuentas nuevas a entidades inactivas.
        """

        usuario = form.instance
        es_nuevo = not bool(usuario.pk)

        funcionario = form.cleaned_data.get("funcionario")
        roles = list(form.cleaned_data.get("roles") or [])
        delegaciones = list(
            form.cleaned_data.get("delegaciones_autorizadas") or []
        )
        password = form.cleaned_data.get("password1")

        if funcionario is None:
            raise ReglaNegocioError(
                "Debe asociar la cuenta a un funcionario."
            )

        if not roles:
            raise ReglaNegocioError(
                "Debe asignar al menos un rol."
            )

        if es_nuevo and not password:
            raise ReglaNegocioError(
                "Debe establecer una contraseña."
            )

        funcionario_original_id = None
        delegaciones_existentes_ids = set()
        anterior = None

        if not es_nuevo:
            original = (
                Usuario.objects
                .prefetch_related("delegaciones_autorizadas")
                .get(pk=usuario.pk)
            )

            funcionario_original_id = original.funcionario_id

            delegaciones_existentes_ids = set(
                original.delegaciones_autorizadas.values_list(
                    "pk",
                    flat=True,
                )
            )

            anterior = _snapshot(original)

        cambio_funcionario = (
            es_nuevo
            or funcionario_original_id != funcionario.pk
        )

        # Solo se permite una asignación nueva a un funcionario activo.
        if cambio_funcionario and not funcionario.activo:
            raise ReglaNegocioError(
                "No se puede asignar una cuenta nueva "
                "a un funcionario inactivo."
            )

        # Una delegación inactiva puede conservarse en una relación
        # existente, pero no utilizarse para una nueva asignación.
        if (
            cambio_funcionario
            and not funcionario.delegacion.activa
        ):
            raise ReglaNegocioError(
                "No se puede asignar una cuenta "
                "a una delegación inactiva."
            )

        _validar_ambito_asignacion(
            actor=actor,
            queryset=Delegacion.objects.all(),
            campo="id_delegacion",
            objeto_id=funcionario.delegacion_id,
            entidad="usuario",
            mensaje=(
                "No tienes autorización para administrar "
                "usuarios de esa delegación."
            ),
        )

        _validar_delegaciones_asignables(
            actor,
            delegaciones,
        )

        inactivas_nuevas = [
            delegacion.nombre
            for delegacion in delegaciones
            if (
                not delegacion.activa
                and delegacion.pk not in delegaciones_existentes_ids
            )
        ]

        if inactivas_nuevas:
            raise ReglaNegocioError(
                "No se pueden asignar delegaciones inactivas: "
                + ", ".join(inactivas_nuevas)
            )

        alcances = {
            rol.alcance_autorizado
            for rol in roles
        }

        if (
            delegaciones
            and not ({"global", "multiples"} & alcances)
        ):
            raise ReglaNegocioError(
                "Los roles asignados no permiten "
                "delegaciones adicionales."
            )

        if password:
            try:
                validate_password(
                    password,
                    user=usuario,
                )
            except ValidationError as exc:
                raise ReglaNegocioError(
                    " ".join(exc.messages)
                )

        with transaction.atomic():
            usuario = form.save(commit=False)

            if password:
                usuario.set_password(password)

            # Un funcionario inactivo nunca puede conservar
            # el acceso habilitado.
            if not funcionario.activo:
                usuario.activo_acceso = False

            usuario.save()
            form.save_m2m()

            CRUDRol.sincronizar_roles(
                funcionario,
                roles,
                actor,
            )

            auditar(
                actor,
                "CREAR" if es_nuevo else "MODIFICAR",
                "usuario",
                usuario.pk,
                anterior,
                _snapshot(usuario),
            )

            _notificar_crud(
                "usuario",
                "crear" if es_nuevo else "actualizar",
                actor,
                usuario,
                delegacion_id=funcionario.delegacion_id,
            )

        return usuario

    @staticmethod
    def cambiar_estado_acceso(usuario, actor=None):
        with transaction.atomic():
            usuario = Usuario.objects.select_for_update().select_related(
                "funcionario"
            ).get(pk=usuario.pk)

            if not usuario.funcionario_id:
                raise ReglaNegocioError(
                    "Asocia la cuenta a un funcionario antes de habilitarla."
                )

            if not usuario.funcionario.activo:
                raise ReglaNegocioError(
                    "No se puede habilitar el acceso de un funcionario inactivo."
                )

            anterior = _snapshot(usuario)

            usuario.activo_acceso = not usuario.activo_acceso
            usuario.save(
                update_fields=["activo_acceso"]
            )

            auditar(
                actor,
                "CAMBIAR_ESTADO",
                "usuario",
                usuario.pk,
                anterior,
                _snapshot(usuario),
            )

            _notificar_crud(
                "usuario",
                "actualizar",
                actor,
                usuario,
                delegacion_id=usuario.funcionario.delegacion_id,
            )

        return usuario
    @staticmethod
    def validar_delegaciones(
        funcionario,
        delegaciones,
        delegaciones_existentes_ids=None,
        validar_principal=True,
    ):
        """
        Impide asignaciones nuevas a delegaciones inactivas.

        Permite conservar delegaciones inactivas que ya estaban
        asociadas a una cuenta, sin permitir nuevas asignaciones.
        """

        delegaciones = list(delegaciones or [])
        existentes = set(delegaciones_existentes_ids or [])

        if funcionario is None:
            if delegaciones:
                raise ReglaNegocioError(
                    "Una cuenta sin funcionario no puede tener "
                    "delegaciones autorizadas."
                )
            return

        if validar_principal and not funcionario.delegacion.activa:
            raise ReglaNegocioError(
                "No se puede crear o reasignar una cuenta a un "
                "funcionario perteneciente a una delegación inactiva."
            )

        inactivas_nuevas = [
            delegacion.nombre
            for delegacion in delegaciones
            if not delegacion.activa
            and delegacion.pk not in existentes
        ]

        if inactivas_nuevas:
            raise ReglaNegocioError(
                "No se pueden asignar delegaciones inactivas: "
                + ", ".join(inactivas_nuevas)
            )

        alcances = set(
            funcionario.roles.values_list(
                "alcance_autorizado",
                flat=True,
            )
        )

        if "global" in alcances or "multiples" in alcances:
            return

        if delegaciones:
            raise ReglaNegocioError(
                "El funcionario tiene alcance propio y no puede "
                "recibir delegaciones adicionales."
            )
