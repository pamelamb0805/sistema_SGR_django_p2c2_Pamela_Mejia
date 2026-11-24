
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import (
    Delegacion,
    Rol,
    Funcionario,
    Usuario,
)

from organizations.models import (
    Delegacion,
    Rol,
    Funcionario,
    ItemMedible,
)

from organizations.services import (
    CRUDDelegacion,
    CRUDRol,
    CRUDFuncionario,
    CRUDCargo,
)

from .serializers import (
    DelegacionSerializer,
    RolSerializer,
    FuncionarioSerializer,
    UsuarioSerializer,
    ItemMedibleSerializer,
    MetaSerializer,
    PeriodoSerializer,
    AjusteSerializer,
    ActividadSerializer,
    EvidenciaSerializer,
    ValidacionSerializer,
)

from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_SUPERVISION,
    ROLES_CONFIGURACION,
    ROLES_MEDICION,
    ROLES_OPERATIVOS,
    ROLES_VALIDACION,
    tiene_rol,
    tiene_permiso,
    filtrar_por_ambito,
    get_funcionario,
)

from measurement.models import (
    Meta as MetaModel,
    Periodo,
    ReglaCalculoVersion,
    Ajuste,
)

from measurement.services import (
    CRUDMeta,
    CRUDPeriodo,
    CalculoIndicadores,
    CRUDAjuste,
)
from django.http import FileResponse
from django.urls import reverse

from rest_framework.decorators import parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from activities.models import (
    Actividad,
    Evidencia,
    Validacion,
)

from activities.services import (
    CRUDActividad,
    CRUDEvidencia,
    CRUDValidacion,
    actividades_visibles,
    evidencias_visibles,
)

from django.utils.dateparse import parse_date

from agenda.models import Compromiso
from agenda.services import (
    CRUDCompromiso,
    CRUDHistorialTransiciones,
    compromisos_visibles,
    puede_gestionar,
    supervisa,
)

from .serializers import (
    CompromisoSerializer,
    HistorialTransicionesSerializer,
)
from social.models import UsuarioSocial, AtencionSocial
from social.services import (
    CRUDUsuarioSocial,
    CRUDAtencionSocial,
    casos_visibles,
    gestiones_visibles,
    puede_escribir,
    estadisticas_atenciones,
)
from .serializers import (
    UsuarioSocialSerializer,
    AtencionSocialSerializer,
)


from catalogs.models import Catalogo, CatalogoVersion
from catalogs.services import CRUDCatalogo

from .serializers import CatalogoSerializer
from django.core.exceptions import PermissionDenied

from audit.models import Auditoria, Notificacion
from audit.services import (
    puede_consultar as puede_consultar_auditoria,
    filtrar_auditoria,
)
from audit.collaboration import (
    obtener_registro_comentable,
    obtener_conversacion,
    crear_comentario,
)

from .serializers import (
    AuditoriaSerializer,
    NotificacionSerializer,
    ComentarioRegistroSerializer,
)
from django.utils import timezone
from organizations.models import Cargo, ItemMedibleVersion
from .serializers import CargoSerializer
from django.core.exceptions import ValidationError

# ---------------------------------------------------------------------
# AUTORIZACIÓN
# ---------------------------------------------------------------------

def _puede_consultar(user):
    return (
        tiene_rol(user, *ROLES_SUPERVISION)
        and tiene_permiso(user, "delegaciones.ver")
    )


def _puede_editar(user):
    return (
        tiene_rol(user, *ROLES_CONFIGURACION)
        and tiene_permiso(user, "delegaciones.editar")
    )


def _delegaciones_autorizadas(user):
    return filtrar_por_ambito(
        Delegacion.objects.all(),
        user,
        campo="id_delegacion",
    )


def _obtener_delegacion_autorizada(user, pk):
    return (
        _delegaciones_autorizadas(user)
        .filter(id_delegacion=pk)
        .first()
    )


# ---------------------------------------------------------------------
# LISTAR Y CREAR DELEGACIONES
# GET  /api/delegaciones/
# POST /api/delegaciones/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def delegacion_list(request):

    if request.method == "GET":

        if not _puede_consultar(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar delegaciones."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        delegaciones = _delegaciones_autorizadas(request.user)

        serializer = DelegacionSerializer(
            delegaciones,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar delegaciones."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = DelegacionSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        delegacion = Delegacion(
            **serializer.validated_data
        )

        delegacion = CRUDDelegacion.crear_delegacion(
            delegacion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        DelegacionSerializer(delegacion).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y MODIFICAR UNA DELEGACIÓN
# GET   /api/delegaciones/<pk>/
# PUT   /api/delegaciones/<pk>/
# PATCH /api/delegaciones/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def delegacion_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar delegaciones."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    else:

        if not _puede_editar(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para administrar delegaciones."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    delegacion = _obtener_delegacion_autorizada(
        request.user,
        pk,
    )

    if delegacion is None:
        return Response(
            {"detail": "Delegación no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            DelegacionSerializer(delegacion).data,
            status=status.HTTP_200_OK,
        )

    serializer = DelegacionSerializer(
        delegacion,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(delegacion, campo, valor)

        delegacion = CRUDDelegacion.modificar_delegacion(
            delegacion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        DelegacionSerializer(delegacion).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y CAMBIAR EL ESTADO
# GET  /api/delegaciones/<pk>/estado/
# POST /api/delegaciones/<pk>/estado/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def delegacion_estado(request, pk):

    if request.method == "GET":

        if not _puede_consultar(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar delegaciones."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    else:

        if not _puede_editar(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para administrar delegaciones."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    delegacion = _obtener_delegacion_autorizada(
        request.user,
        pk,
    )

    if delegacion is None:
        return Response(
            {"detail": "Delegación no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # GET solamente consulta. Nunca modifica el estado.
    if request.method == "GET":
        return Response(
            DelegacionSerializer(delegacion).data,
            status=status.HTTP_200_OK,
        )

    # POST cambia el estado utilizando el servicio de negocio.
    try:
        delegacion = CRUDDelegacion.activar_desactivar_delegacion(
            delegacion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        DelegacionSerializer(delegacion).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# AUTORIZACIÓN DE ROLES
# ---------------------------------------------------------------------

def _puede_consultar_roles(user):
    return (
        tiene_rol(user, *ROLES_SUPERVISION)
        and tiene_permiso(user, "roles.ver")
    )


def _puede_editar_roles(user):
    return (
        tiene_rol(user, *ROLES_CONFIGURACION)
        and tiene_permiso(user, "roles.editar")
    )


# ---------------------------------------------------------------------
# LISTAR Y CREAR ROLES
# GET  /api/roles/
# POST /api/roles/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def rol_list(request):

    if request.method == "GET":

        if not _puede_consultar_roles(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        roles = CRUDRol.mostrar_roles()

        serializer = RolSerializer(
            roles,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_roles(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar roles."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = RolSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        rol = Rol(**serializer.validated_data)

        rol = CRUDRol.crear_rol(
            rol,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        RolSerializer(rol).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR, MODIFICAR Y ELIMINAR ROLES
# GET    /api/roles/<pk>/
# PUT    /api/roles/<pk>/
# PATCH  /api/roles/<pk>/
# DELETE /api/roles/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def rol_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_roles(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

    else:

        if not _puede_editar_roles(request.user):
            return Response(
                {"detail": "No tienes permiso para administrar roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

    rol = Rol.objects.filter(pk=pk).first()

    if rol is None:
        return Response(
            {"detail": "Rol no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            RolSerializer(rol).data,
            status=status.HTTP_200_OK,
        )

    if request.method == "DELETE":

        try:
            CRUDRol.eliminar_rol(
                rol,
                request.user,
            )

        except ReglaNegocioError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )

    serializer = RolSerializer(
        rol,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(rol, campo, valor)

        rol = CRUDRol.modificar_rol(
            rol,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        RolSerializer(rol).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# AUTORIZACIÓN DE FUNCIONARIOS
# ---------------------------------------------------------------------

def _puede_consultar_funcionarios(user):
    return (
        tiene_rol(user, *ROLES_SUPERVISION)
        and tiene_permiso(user, "funcionarios.ver")
    )


def _puede_editar_funcionarios(user):
    return (
        tiene_rol(user, *ROLES_CONFIGURACION)
        and tiene_permiso(user, "funcionarios.editar")
    )


def _funcionarios_autorizados(user):
    queryset = (
        CRUDFuncionario.mostrar_todos_funcionarios()
        .select_related("cargo", "delegacion", "usuario")
        .prefetch_related("roles")
    )

    return filtrar_por_ambito(
        queryset,
        user,
        campo="delegacion_id",
    )


def _obtener_funcionario_autorizado(user, pk):
    return _funcionarios_autorizados(user).filter(
        pk=pk
    ).first()


# ---------------------------------------------------------------------
# LISTAR Y CREAR FUNCIONARIOS
# GET  /api/funcionarios/
# POST /api/funcionarios/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def funcionario_list(request):

    if request.method == "GET":

        if not _puede_consultar_funcionarios(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar funcionarios."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        funcionarios = _funcionarios_autorizados(request.user)

        serializer = FuncionarioSerializer(
            funcionarios,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_funcionarios(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar funcionarios."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = FuncionarioSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    datos = dict(serializer.validated_data)
    roles = datos.pop("roles_ids")

    try:
        funcionario = Funcionario(**datos)

        funcionario = CRUDFuncionario.crear_funcionario(
            funcionario,
            roles,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    funcionario = _obtener_funcionario_autorizado(
        request.user,
        funcionario.pk,
    )

    return Response(
        FuncionarioSerializer(funcionario).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR, MODIFICAR Y ELIMINAR FUNCIONARIOS
# GET    /api/funcionarios/<pk>/
# PUT    /api/funcionarios/<pk>/
# PATCH  /api/funcionarios/<pk>/
# DELETE /api/funcionarios/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def funcionario_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_funcionarios(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar funcionarios."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_funcionarios(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar funcionarios."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    funcionario = _obtener_funcionario_autorizado(
        request.user,
        pk,
    )

    if funcionario is None:
        return Response(
            {"detail": "Funcionario no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            FuncionarioSerializer(funcionario).data,
            status=status.HTTP_200_OK,
        )

    if request.method == "DELETE":

        try:
            CRUDFuncionario.eliminar_funcionario(
                funcionario,
                request.user,
            )

        except ReglaNegocioError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )

    serializer = FuncionarioSerializer(
        funcionario,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    datos = dict(serializer.validated_data)

    roles = datos.pop(
        "roles_ids",
        list(funcionario.roles.all()),
    )

    try:
        for campo, valor in datos.items():
            setattr(funcionario, campo, valor)

        funcionario = CRUDFuncionario.modificar_funcionario(
            funcionario,
            roles,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    funcionario = _obtener_funcionario_autorizado(
        request.user,
        funcionario.pk,
    )

    return Response(
        FuncionarioSerializer(funcionario).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y CAMBIAR ESTADO DEL FUNCIONARIO
# GET  /api/funcionarios/<pk>/estado/
# POST /api/funcionarios/<pk>/estado/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def funcionario_estado(request, pk):

    if request.method == "GET":

        if not _puede_consultar_funcionarios(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar funcionarios."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_funcionarios(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para modificar funcionarios."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    funcionario = _obtener_funcionario_autorizado(
        request.user,
        pk,
    )

    if funcionario is None:
        return Response(
            {"detail": "Funcionario no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            {
                "id_funcionario": funcionario.pk,
                "estado": funcionario.estado,
                "activo": funcionario.activo,
            },
            status=status.HTTP_200_OK,
        )

    try:
        funcionario = CRUDFuncionario.cambiar_estado(
            funcionario,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    funcionario = _obtener_funcionario_autorizado(
        request.user,
        funcionario.pk,
    )

    return Response(
        FuncionarioSerializer(funcionario).data,
        status=status.HTTP_200_OK,
    )

# ---------------------------------------------------------------------
# AUTORIZACIÓN DE USUARIOS
# ---------------------------------------------------------------------

def _puede_consultar_usuarios(user):
    return tiene_permiso(user, "usuarios.ver")


def _puede_editar_usuarios(user):
    return tiene_permiso(user, "usuarios.editar")


def _usuarios_autorizados(user):
    queryset = (
        Usuario.objects
        .select_related(
            "funcionario",
            "funcionario__delegacion",
        )
        .prefetch_related(
            "delegaciones_autorizadas",
            "funcionario__roles",
        )
        .filter(funcionario__isnull=False)
    )

    return filtrar_por_ambito(
        queryset,
        user,
        campo="funcionario__delegacion_id",
    )


def _obtener_usuario_autorizado(user, pk):
    return _usuarios_autorizados(user).filter(pk=pk).first()


# ---------------------------------------------------------------------
# LISTAR Y CREAR USUARIOS
# GET  /api/usuarios/
# POST /api/usuarios/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def usuario_list(request):

    if request.method == "GET":

        if not _puede_consultar_usuarios(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar usuarios."},
                status=status.HTTP_403_FORBIDDEN,
            )

        usuarios = _usuarios_autorizados(request.user)

        return Response(
            UsuarioSerializer(usuarios, many=True).data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_usuarios(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar usuarios."},
            status=status.HTTP_403_FORBIDDEN,
        )

    from organizations.forms import UsuarioAdminForm

    form = UsuarioAdminForm(
        data=request.data,
        instance=Usuario(),
        actor=request.user,
    )

    if not form.is_valid():
        return Response(
            {"errors": form.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        usuario = Seguridad.guardar_usuario(
            form,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    usuario = _obtener_usuario_autorizado(
        request.user,
        usuario.pk,
    )

    return Response(
        UsuarioSerializer(usuario).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y MODIFICAR USUARIOS
# GET /api/usuarios/<pk>/
# PUT /api/usuarios/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def usuario_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_usuarios(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar usuarios."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_usuarios(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar usuarios."},
            status=status.HTTP_403_FORBIDDEN,
        )

    usuario = _obtener_usuario_autorizado(
        request.user,
        pk,
    )

    if usuario is None:
        return Response(
            {"detail": "Usuario no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            UsuarioSerializer(usuario).data,
            status=status.HTTP_200_OK,
        )

    from organizations.forms import UsuarioAdminForm

    form = UsuarioAdminForm(
        data=request.data,
        instance=usuario,
        actor=request.user,
    )

    if not form.is_valid():
        return Response(
            {"errors": form.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        usuario = Seguridad.guardar_usuario(
            form,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    usuario = _obtener_usuario_autorizado(
        request.user,
        usuario.pk,
    )

    return Response(
        UsuarioSerializer(usuario).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y CAMBIAR ESTADO DEL ACCESO
# GET  /api/usuarios/<pk>/estado/
# POST /api/usuarios/<pk>/estado/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def usuario_estado(request, pk):

    if request.method == "GET":

        if not _puede_consultar_usuarios(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar usuarios."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_usuarios(request.user):
        return Response(
            {"detail": "No tienes permiso para modificar accesos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    usuario = _obtener_usuario_autorizado(
        request.user,
        pk,
    )

    if usuario is None:
        return Response(
            {"detail": "Usuario no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            {
                "id_usuario": usuario.pk,
                "activo_acceso": usuario.activo_acceso,
                "is_active": usuario.is_active,
            },
            status=status.HTTP_200_OK,
        )

    try:
        usuario = Seguridad.cambiar_estado_acceso(
            usuario,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        UsuarioSerializer(usuario).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CAMBIAR CONTRASEÑA
# POST /api/usuarios/<pk>/contrasenia/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def usuario_contrasenia(request, pk):

    if not _puede_editar_usuarios(request.user):
        return Response(
            {"detail": "No tienes permiso para cambiar contraseñas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    usuario = _obtener_usuario_autorizado(
        request.user,
        pk,
    )

    if usuario is None:
        return Response(
            {"detail": "Usuario no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    password = request.data.get("password")

    if not isinstance(password, str) or not password:
        return Response(
            {"detail": "Debes proporcionar una contraseña."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        Seguridad.cambiar_contrasenia(
            usuario,
            password,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"detail": "Contraseña actualizada correctamente."},
        status=status.HTTP_200_OK,
    )

# ---------------------------------------------------------------------
# AUTORIZACIÓN DE ÍTEMS MEDIBLES
# ---------------------------------------------------------------------

def _puede_consultar_items(user):
    return (
        tiene_rol(user, *ROLES_SUPERVISION)
        and tiene_permiso(user, "items.ver")
    )


def _puede_editar_items(user):
    return (
        tiene_rol(user, *ROLES_CONFIGURACION)
        and tiene_permiso(user, "items.editar")
    )


# ---------------------------------------------------------------------
# LISTAR Y CREAR ÍTEMS
# GET  /api/items/
# POST /api/items/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def item_list(request):

    if request.method == "GET":

        if not _puede_consultar_items(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar ítems."},
                status=status.HTTP_403_FORBIDDEN,
            )

        items = ItemMedible.objects.select_related(
            "cargo"
        ).all()

        serializer = ItemMedibleSerializer(
            items,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_items(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar ítems."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ItemMedibleSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        item = ItemMedible(
            **serializer.validated_data
        )

        item = CRUDCargo.crear_item(
            item,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        ItemMedibleSerializer(item).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y MODIFICAR UN ÍTEM
# GET   /api/items/<pk>/
# PUT   /api/items/<pk>/
# PATCH /api/items/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def item_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_items(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar ítems."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_items(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar ítems."},
            status=status.HTTP_403_FORBIDDEN,
        )

    item = (
        ItemMedible.objects
        .select_related("cargo")
        .filter(pk=pk)
        .first()
    )

    if item is None:
        return Response(
            {"detail": "Ítem medible no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            ItemMedibleSerializer(item).data,
            status=status.HTTP_200_OK,
        )

    serializer = ItemMedibleSerializer(
        item,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(item, campo, valor)

        item = CRUDCargo.modificar_item(
            item,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        ItemMedibleSerializer(item).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y CAMBIAR VIGENCIA DE UN ÍTEM
# GET  /api/items/<pk>/vigencia/
# POST /api/items/<pk>/vigencia/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def item_vigencia(request, pk):

    if request.method == "GET":

        if not _puede_consultar_items(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar ítems."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_items(request.user):
        return Response(
            {"detail": "No tienes permiso para modificar ítems."},
            status=status.HTTP_403_FORBIDDEN,
        )

    item = (
        ItemMedible.objects
        .select_related("cargo")
        .filter(pk=pk)
        .first()
    )

    if item is None:
        return Response(
            {"detail": "Ítem medible no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            {
                "id_item": item.pk,
                "vigencia": item.vigencia,
            },
            status=status.HTTP_200_OK,
        )

    try:
        item = CRUDCargo.cambiar_vigencia_item(
            item,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        ItemMedibleSerializer(item).data,
        status=status.HTTP_200_OK,
    )

# ---------------------------------------------------------------------
# AUTORIZACIÓN DE METAS
# ---------------------------------------------------------------------

def _puede_consultar_metas(user):
    return tiene_permiso(user, "metas.ver")


def _puede_editar_metas(user):
    return tiene_permiso(user, "metas.editar")


def _puede_eliminar_metas(user):
    return tiene_permiso(user, "metas.eliminar")


def _funcionarios_en_ambito(user):
    return filtrar_por_ambito(
        Funcionario.objects.all(),
        user,
        campo="delegacion_id",
    )


def _metas_autorizadas(user):
    queryset = MetaModel.objects.select_related(
        "periodo",
        "funcionario",
        "funcionario__cargo",
        "funcionario__delegacion",
        "item",
        "cargo",
    )

    return filtrar_por_ambito(
        queryset,
        user,
        campo="funcionario__delegacion_id",
    )


def _obtener_meta_autorizada(user, pk):
    return _metas_autorizadas(user).filter(
        pk=pk
    ).first()


def _funcionario_autorizado(user, funcionario):
    return _funcionarios_en_ambito(user).filter(
        pk=funcionario.pk
    ).exists()


# ---------------------------------------------------------------------
# LISTAR Y CREAR METAS
# GET  /api/metas/
# POST /api/metas/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def meta_list(request):

    if request.method == "GET":

        if not _puede_consultar_metas(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar metas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        metas = _metas_autorizadas(request.user)

        return Response(
            MetaSerializer(metas, many=True).data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_metas(request.user):
        return Response(
            {"detail": "No tienes permiso para crear metas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = MetaSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    datos = dict(serializer.validated_data)
    aplicar_a_cargo = datos.pop(
        "aplicar_a_cargo",
        False,
    )

    funcionario = datos.get("funcionario")

    if funcionario is None:
        return Response(
            {"detail": "Debes indicar un funcionario."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not _funcionario_autorizado(
        request.user,
        funcionario,
    ):
        return Response(
            {
                "detail": (
                    "No puedes crear metas para funcionarios "
                    "fuera de tu ámbito autorizado."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        meta = MetaModel(**datos)

        if aplicar_a_cargo:

            # El servicio aplica la meta a todos los funcionarios
            # activos del cargo. Solo se permite si todos están
            # dentro del ámbito autorizado del usuario.
            candidatos = Funcionario.objects.filter(
                cargo=funcionario.cargo,
                estado=Funcionario.ESTADO_ACTIVO,
            )

            autorizados = _funcionarios_en_ambito(
                request.user
            ).filter(
                cargo=funcionario.cargo,
                estado=Funcionario.ESTADO_ACTIVO,
            )

            if candidatos.count() != autorizados.count():
                return Response(
                    {
                        "detail": (
                            "No puedes aplicar una meta a todo el cargo "
                            "porque existen funcionarios fuera de tu "
                            "ámbito autorizado."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            resultado = CRUDMeta.crear_meta_para_cargo(
                meta,
                request.user,
            )

            return Response(
                {
                    "creadas": MetaSerializer(
                        resultado["creadas"],
                        many=True,
                    ).data,
                    "cantidad_creadas": len(
                        resultado["creadas"]
                    ),
                    "omitidas": [
                        {
                            "id_funcionario": funcionario_omitido.pk,
                            "nombre": funcionario_omitido.nombre,
                            "motivo": motivo,
                        }
                        for funcionario_omitido, motivo
                        in resultado["omitidas"]
                    ],
                    "cantidad_omitidas": len(
                        resultado["omitidas"]
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        meta = CRUDMeta.crear_meta(
            meta,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        MetaSerializer(meta).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR, MODIFICAR Y ELIMINAR METAS
# GET    /api/metas/<pk>/
# PUT    /api/metas/<pk>/
# PATCH  /api/metas/<pk>/
# DELETE /api/metas/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def meta_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_metas(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar metas."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif request.method == "DELETE":

        if not _puede_eliminar_metas(request.user):
            return Response(
                {"detail": "No tienes permiso para eliminar metas."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_metas(request.user):
        return Response(
            {"detail": "No tienes permiso para modificar metas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    meta = _obtener_meta_autorizada(
        request.user,
        pk,
    )

    if meta is None:
        return Response(
            {"detail": "Meta no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            MetaSerializer(meta).data,
            status=status.HTTP_200_OK,
        )

    if request.method == "DELETE":

        try:
            CRUDMeta.eliminar_meta(
                meta,
                request.user,
            )

        except ReglaNegocioError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )

    serializer = MetaSerializer(
        meta,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            if campo == "aplicar_a_cargo":
                continue

            setattr(meta, campo, valor)

        meta = CRUDMeta.modificar_meta(
            meta,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        MetaSerializer(meta).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# AUTORIZACIÓN DE PERÍODOS
# ---------------------------------------------------------------------

def _puede_consultar_periodos(user):
    return tiene_permiso(user, "periodos.ver")


def _puede_editar_periodos(user):
    return tiene_permiso(user, "periodos.editar")


def _puede_cerrar_periodos(user):
    return tiene_permiso(user, "periodos.cerrar")


def _puede_reabrir_periodos(user):
    return tiene_permiso(user, "periodos.reabrir")


def _obtener_periodo(pk):
    return Periodo.objects.filter(pk=pk).first()


# ---------------------------------------------------------------------
# LISTAR Y CREAR PERÍODOS
# GET  /api/periodos/
# POST /api/periodos/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def periodo_list(request):

    if request.method == "GET":

        if not _puede_consultar_periodos(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar períodos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        periodos = CRUDPeriodo.mostrar_todos_periodos()

        estado = request.query_params.get("estado")
        if estado in dict(Periodo.ESTADOS):
            periodos = periodos.filter(estado=estado)

        return Response(
            PeriodoSerializer(periodos, many=True).data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_periodos(request.user):
        return Response(
            {"detail": "No tienes permiso para crear períodos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = PeriodoSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        periodo = Periodo(
            **serializer.validated_data
        )

        periodo = CRUDPeriodo.crear_periodo(
            periodo,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        PeriodoSerializer(periodo).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y MODIFICAR UN PERÍODO
# GET   /api/periodos/<pk>/
# PUT   /api/periodos/<pk>/
# PATCH /api/periodos/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def periodo_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_periodos(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar períodos."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_periodos(request.user):
        return Response(
            {"detail": "No tienes permiso para modificar períodos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    periodo = _obtener_periodo(pk)

    if periodo is None:
        return Response(
            {"detail": "Período no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            PeriodoSerializer(periodo).data,
            status=status.HTTP_200_OK,
        )

    serializer = PeriodoSerializer(
        periodo,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(periodo, campo, valor)

        periodo = CRUDPeriodo.modificar_periodo(
            periodo,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        PeriodoSerializer(periodo).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CERRAR PERÍODO
# POST /api/periodos/<pk>/cerrar/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def periodo_cerrar(request, pk):

    if not _puede_cerrar_periodos(request.user):
        return Response(
            {"detail": "No tienes permiso para cerrar períodos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    periodo = _obtener_periodo(pk)

    if periodo is None:
        return Response(
            {"detail": "Período no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        periodo = CRUDPeriodo.cerrar_periodo(
            periodo,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        PeriodoSerializer(periodo).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# REABRIR PERÍODO
# POST /api/periodos/<pk>/reabrir/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def periodo_reabrir(request, pk):

    if not _puede_reabrir_periodos(request.user):
        return Response(
            {"detail": "No tienes permiso para reabrir períodos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    periodo = _obtener_periodo(pk)

    if periodo is None:
        return Response(
            {"detail": "Período no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    motivo = request.data.get("motivo", "")

    if not isinstance(motivo, str) or not motivo.strip():
        return Response(
            {"detail": "Debes indicar el motivo de la reapertura."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        periodo = CRUDPeriodo.reabrir_periodo(
            periodo,
            motivo,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        PeriodoSerializer(periodo).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y ACTUALIZAR REGLAS DEL PERÍODO
# GET /api/periodos/<pk>/reglas/
# PUT /api/periodos/<pk>/reglas/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def periodo_reglas(request, pk):

    if request.method == "GET":

        if not _puede_consultar_periodos(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar reglas."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_periodos(request.user):
        return Response(
            {"detail": "No tienes permiso para modificar reglas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    periodo = _obtener_periodo(pk)

    if periodo is None:
        return Response(
            {"detail": "Período no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    version = (
        ReglaCalculoVersion.objects
        .filter(periodo=periodo)
        .order_by("-numero_version")
        .first()
    )

    if request.method == "GET":
        configuracion = (
            version.datos
            if version
            else CRUDPeriodo._datos_reglas_actuales()
        )

        return Response(
            {
                "id_periodo": periodo.pk,
                "numero_version": (
                    version.numero_version if version else 0
                ),
                "vigente_desde": (
                    version.vigente_desde if version else None
                ),
                "reglas": configuracion,
            },
            status=status.HTTP_200_OK,
        )

    datos = request.data

    try:
        nueva_version = CRUDPeriodo.actualizar_reglas_periodo(
            periodo,
            datos,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "id_periodo": periodo.pk,
            "numero_version": nueva_version.numero_version,
            "vigente_desde": nueva_version.vigente_desde,
            "reglas": nueva_version.datos,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# HISTORIAL DE REGLAS DEL PERÍODO
# GET /api/periodos/<pk>/reglas/historial/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def periodo_reglas_historial(request, pk):

    if not _puede_consultar_periodos(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar el historial."},
            status=status.HTTP_403_FORBIDDEN,
        )

    periodo = _obtener_periodo(pk)

    if periodo is None:
        return Response(
            {"detail": "Período no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    versiones = (
        ReglaCalculoVersion.objects
        .filter(periodo=periodo)
        .select_related("creado_por")
        .order_by("-numero_version")
    )

    resultado = [
        {
            "numero_version": version.numero_version,
            "vigente_desde": version.vigente_desde,
            "vigente_hasta": version.vigente_hasta,
            "datos": version.datos,
            "creado_por": (
                version.creado_por.username
                if version.creado_por
                else None
            ),
        }
        for version in versiones
    ]

    return Response(
        {
            "id_periodo": periodo.pk,
            "total_versiones": len(resultado),
            "versiones": resultado,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# RECALCULAR INDICADORES DEL PERÍODO
# POST /api/periodos/<pk>/recalcular/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def periodo_recalcular(request, pk):

    if not _puede_editar_periodos(request.user):
        return Response(
            {"detail": "No tienes permiso para recalcular períodos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    periodo = _obtener_periodo(pk)

    if periodo is None:
        return Response(
            {"detail": "Período no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not periodo.abierto:
        return Response(
            {
                "detail": (
                    "El período está cerrado: sus resultados "
                    "no se pueden recalcular."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        cantidad = CalculoIndicadores.recalcular_periodo(
            periodo
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "detail": "Indicadores recalculados correctamente.",
            "id_periodo": periodo.pk,
            "indicadores_recalculados": cantidad,
        },
        status=status.HTTP_200_OK,
    )

# ---------------------------------------------------------------------
# AJUSTES: INCENTIVOS Y PENALIZACIONES
# GET  /api/ajustes/
# POST /api/ajustes/
# ---------------------------------------------------------------------

def _puede_consultar_ajustes(user):
    return (
        tiene_rol(user, *ROLES_SUPERVISION)
        and tiene_permiso(user, "ajustes.ver")
    )


def _puede_editar_ajustes(user):
    return (
        tiene_rol(user, *ROLES_MEDICION)
        and tiene_permiso(user, "ajustes.editar")
    )


def _ajustes_autorizados(user):
    return filtrar_por_ambito(
        Ajuste.objects.select_related(
            "funcionario",
            "funcionario__delegacion",
            "periodo",
            "meta",
            "meta__item",
        ),
        user,
        campo="funcionario__delegacion_id",
    )


def _obtener_ajuste_autorizado(user, pk):
    return (
        _ajustes_autorizados(user)
        .filter(pk=pk)
        .first()
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ajuste_list(request):

    if request.method == "GET":

        if not _puede_consultar_ajustes(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar ajustes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ajustes = _ajustes_autorizados(request.user)

        # Filtros equivalentes al listado web.
        periodo = request.query_params.get("periodo", "").strip()
        if periodo:
            ajustes = ajustes.filter(periodo_id=periodo)

        funcionario = request.query_params.get(
            "funcionario",
            "",
        ).strip()

        if funcionario:
            ajustes = ajustes.filter(
                funcionario_id=funcionario,
            )

        efecto = request.query_params.get("efecto", "").strip()

        if efecto in dict(Ajuste.EFECTOS):
            ajustes = ajustes.filter(efecto=efecto)

        q = request.query_params.get("q", "").strip()

        if q:
            from django.db.models import Q

            ajustes = ajustes.filter(
                Q(motivo__icontains=q)
                | Q(funcionario__nombre__icontains=q)
                | Q(meta__item__nombre_item__icontains=q)
            )

        ajustes = ajustes.order_by("-id_ajuste")

        serializer = AjusteSerializer(
            ajustes,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_ajustes(request.user):
        return Response(
            {"detail": "No tienes permiso para registrar ajustes."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AjusteSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        ajuste = Ajuste(**serializer.validated_data)

        # No permitir crear ajustes fuera del ámbito autorizado.
        funcionario_autorizado = filtrar_por_ambito(
            Funcionario.objects.all(),
            request.user,
            campo="delegacion_id",
        ).filter(
            pk=ajuste.funcionario_id,
        ).exists()

        if not funcionario_autorizado:
            return Response(
                {
                    "detail": (
                        "No puedes registrar ajustes para "
                        "funcionarios fuera de tu ámbito."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        ajuste = CRUDAjuste.crear_ajuste(
            ajuste,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        AjusteSerializer(ajuste).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR, MODIFICAR Y ELIMINAR UN AJUSTE
# GET    /api/ajustes/<pk>/
# PUT    /api/ajustes/<pk>/
# PATCH  /api/ajustes/<pk>/
# DELETE /api/ajustes/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def ajuste_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_ajustes(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar ajustes."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_ajustes(request.user):
        return Response(
            {"detail": "No tienes permiso para modificar ajustes."},
            status=status.HTTP_403_FORBIDDEN,
        )

    ajuste = _obtener_ajuste_autorizado(
        request.user,
        pk,
    )

    if ajuste is None:
        return Response(
            {"detail": "Ajuste no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            AjusteSerializer(ajuste).data,
            status=status.HTTP_200_OK,
        )

    if request.method == "DELETE":

        try:
            CRUDAjuste.eliminar_ajuste(
                ajuste,
                request.user,
            )

        except ReglaNegocioError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Ajuste eliminado correctamente."},
            status=status.HTTP_200_OK,
        )

    serializer = AjusteSerializer(
        ajuste,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(ajuste, campo, valor)

        # Verificar que el funcionario de destino también
        # pertenezca al ámbito autorizado.
        funcionario_autorizado = filtrar_por_ambito(
            Funcionario.objects.all(),
            request.user,
            campo="delegacion_id",
        ).filter(
            pk=ajuste.funcionario_id,
        ).exists()

        if not funcionario_autorizado:
            return Response(
                {
                    "detail": (
                        "No puedes asignar el ajuste a un funcionario "
                        "fuera de tu ámbito."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        ajuste = CRUDAjuste.modificar_ajuste(
            ajuste,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        AjusteSerializer(ajuste).data,
        status=status.HTTP_200_OK,
    )

# =====================================================================
# API DE ACTIVIDADES, EVIDENCIAS Y VALIDACIONES
# RF-009 a RF-014
# =====================================================================


# ---------------------------------------------------------------------
# AUTORIZACIÓN DE ACTIVIDADES
# ---------------------------------------------------------------------

def _puede_consultar_actividades(user):
    return tiene_permiso(
        user,
        "actividades.ver",
    )


def _puede_registrar_actividades(user):
    return (
        tiene_rol(user, *ROLES_OPERATIVOS)
        and tiene_permiso(user, "actividades.registrar")
    )


def _puede_editar_actividades(user):
    return (
        tiene_rol(user, *ROLES_OPERATIVOS)
        and tiene_permiso(user, "actividades.editar")
    )


def _puede_consultar_evidencias(user):
    return tiene_permiso(
        user,
        "evidencias.ver",
    )


def _puede_registrar_evidencias(user):
    return (
        tiene_rol(user, *ROLES_OPERATIVOS)
        and tiene_permiso(user, "evidencias.registrar")
    )


def _puede_consultar_validaciones(user):
    return (
        tiene_rol(user, *ROLES_VALIDACION)
        and tiene_permiso(user, "validaciones.ver")
    )


def _puede_gestionar_validaciones(user):
    return (
        tiene_rol(user, *ROLES_VALIDACION)
        and tiene_permiso(user, "validaciones.gestionar")
    )


def _actividades_autorizadas(user):
    return (
        actividades_visibles(user)
        .select_related(
            "funcionario",
            "funcionario__delegacion",
            "funcionario__cargo",
            "item",
            "catalogo",
            "periodo",
        )
        .prefetch_related("evidencias")
    )


def _evidencias_autorizadas(user):
    return (
        evidencias_visibles(user)
        .select_related(
            "actividad",
            "actividad__funcionario",
            "actividad__item",
            "actividad__catalogo",
            "actividad__periodo",
            "funcionario",
        )
        .prefetch_related("validaciones")
    )


def _obtener_actividad_autorizada(user, pk):
    return _actividades_autorizadas(user).filter(
        pk=pk,
    ).first()


def _obtener_evidencia_autorizada(user, pk):
    return _evidencias_autorizadas(user).filter(
        pk=pk,
    ).first()


def _es_autor_actividad(user, actividad):
    funcionario = get_funcionario(user)

    return (
        funcionario is not None
        and funcionario.pk == actividad.funcionario_id
    )


def _puede_anular_actividad(user, actividad):
    if actividad.estado == Actividad.ESTADO_ANULADA:
        return False

    if not tiene_permiso(user, "actividades.anular"):
        return False

    if tiene_rol(user, *ROLES_SUPERVISION):
        return True

    return (
        _es_autor_actividad(user, actividad)
        and actividad.estado != Actividad.ESTADO_VALIDADA
    )


# ---------------------------------------------------------------------
# LISTAR Y REGISTRAR ACTIVIDADES
#
# GET  /api/actividades/
# POST /api/actividades/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def actividad_list(request):

    if request.method == "GET":

        if not _puede_consultar_actividades(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar actividades."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        actividades = _actividades_autorizadas(request.user)

        filtros = request.query_params

        for campo in (
            "estado",
            "tipo_registro",
        ):
            valor = filtros.get(campo)

            if valor:
                actividades = actividades.filter(
                    **{campo: valor}
                )

        for campo, filtro in (
            ("item", "item_id"),
            ("periodo", "periodo_id"),
            ("funcionario", "funcionario_id"),
            ("delegacion", "funcionario__delegacion_id"),
        ):
            valor = filtros.get(campo)

            if valor and valor.isdigit():
                actividades = actividades.filter(
                    **{filtro: valor}
                )

        from django.utils.dateparse import parse_date

        fecha_desde_texto = filtros.get("fecha_desde", "").strip()
        fecha_hasta_texto = filtros.get("fecha_hasta", "").strip()

        fecha_desde = (
            parse_date(fecha_desde_texto)
            if fecha_desde_texto
            else None
        )
        fecha_hasta = (
            parse_date(fecha_hasta_texto)
            if fecha_hasta_texto
            else None
        )

        if fecha_desde_texto and fecha_desde is None:
            return Response(
                {"fecha_desde": "Formato inválido. Utiliza YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fecha_hasta_texto and fecha_hasta is None:
            return Response(
                {"fecha_hasta": "Formato inválido. Utiliza YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            return Response(
                {
                    "detail": (
                        "La fecha desde no puede ser posterior "
                        "a la fecha hasta."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if fecha_desde:
            actividades = actividades.filter(fecha__gte=fecha_desde)

        if fecha_hasta:
            actividades = actividades.filter(fecha__lte=fecha_hasta)

        termino = filtros.get("q", "").strip()

        if termino:
            import re
            from django.db.models import Q

            # Buscar códigos completos: ACT-0000123 o ACT-0000123-E01.
            coincidencia = re.fullmatch(
                r"ACT-(\d+)(?:-E\d+)?",
                termino.strip(),
                re.IGNORECASE,
            )

            if coincidencia:
                actividades = actividades.filter(
                    id_actividad=int(coincidencia.group(1))
                )
            else:
                actividades = actividades.filter(
                    Q(accion__icontains=termino)
                    | Q(contacto__icontains=termino)
                    | Q(funcionario__nombre__icontains=termino)
                    | Q(item__nombre_item__icontains=termino)
                    | Q(catalogo_nombre__icontains=termino)
                )

        actividades = actividades.order_by(
            "-fecha",
            "-id_actividad",
        )

        return Response(
            ActividadSerializer(
                actividades,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # POST: crear actividad.

    if not _puede_registrar_actividades(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para registrar actividades."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    funcionario = get_funcionario(request.user)

    if funcionario is None:
        return Response(
            {
                "detail": (
                    "Tu usuario no tiene un funcionario asociado."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = ActividadSerializer(
        data=request.data,
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        actividad = Actividad(
            funcionario=funcionario,
            **serializer.validated_data,
        )

        actividad = CRUDActividad.crear_actividad(
            actividad,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        ActividadSerializer(
            actividad,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y MODIFICAR ACTIVIDAD
#
# GET   /api/actividades/<pk>/
# PUT   /api/actividades/<pk>/
# PATCH /api/actividades/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def actividad_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_actividades(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar actividades."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not _puede_editar_actividades(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para editar actividades."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    actividad = _obtener_actividad_autorizada(
        request.user,
        pk,
    )

    if actividad is None:
        return Response(
            {"detail": "Actividad no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            ActividadSerializer(
                actividad,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    if not _es_autor_actividad(request.user, actividad):
        return Response(
            {
                "detail": (
                    "Solo el funcionario autor puede modificar "
                    "esta actividad."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ActividadSerializer(
        actividad,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(actividad, campo, valor)

        actividad = CRUDActividad.modificar_actividad(
            actividad,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        ActividadSerializer(
            actividad,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# ANULAR ACTIVIDAD
#
# POST /api/actividades/<pk>/anular/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def actividad_anular(request, pk):

    actividad = _obtener_actividad_autorizada(
        request.user,
        pk,
    )

    if actividad is None:
        return Response(
            {"detail": "Actividad no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not _puede_anular_actividad(
        request.user,
        actividad,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para anular esta actividad."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    motivo = request.data.get("motivo", "")

    if not isinstance(motivo, str) or not motivo.strip():
        return Response(
            {
                "detail": (
                    "Debes indicar el motivo de la anulación."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        actividad = CRUDActividad.anular_actividad(
            actividad,
            motivo,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        ActividadSerializer(
            actividad,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# LISTAR Y ADJUNTAR EVIDENCIAS A UNA ACTIVIDAD
#
# GET  /api/actividades/<pk>/evidencias/
# POST /api/actividades/<pk>/evidencias/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def actividad_evidencias(request, pk):

    actividad = _obtener_actividad_autorizada(
        request.user,
        pk,
    )

    if actividad is None:
        return Response(
            {"detail": "Actividad no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":

        if not _puede_consultar_evidencias(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar evidencias."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        evidencias = (
            _evidencias_autorizadas(request.user)
            .filter(actividad=actividad)
            .order_by("id_evidencia")
        )

        return Response(
            EvidenciaSerializer(
                evidencias,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    if not _puede_registrar_evidencias(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para adjuntar evidencias."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if not _es_autor_actividad(request.user, actividad):
        return Response(
            {
                "detail": (
                    "Solo el funcionario autor puede adjuntar "
                    "evidencias a esta actividad."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    archivo = (
        request.FILES.get("archivo")
        or request.FILES.get("archivo_vinculo")
    )

    if archivo is None:
        return Response(
            {
                "detail": (
                    "Debes adjuntar un archivo en el campo archivo."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        evidencia = CRUDEvidencia.adjuntar_evidencia(
            actividad,
            archivo,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        EvidenciaSerializer(
            evidencia,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR UNA EVIDENCIA
#
# GET /api/evidencias/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evidencia_detail(request, pk):

    if not _puede_consultar_evidencias(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para consultar evidencias."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    evidencia = _obtener_evidencia_autorizada(
        request.user,
        pk,
    )

    if evidencia is None:
        return Response(
            {"detail": "Evidencia no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        EvidenciaSerializer(
            evidencia,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# DESCARGAR O VISUALIZAR ARCHIVO DE EVIDENCIA
#
# GET /api/evidencias/<pk>/archivo/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evidencia_archivo(request, pk):

    if not _puede_consultar_evidencias(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para consultar archivos."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    evidencia = _obtener_evidencia_autorizada(
        request.user,
        pk,
    )

    if evidencia is None or not evidencia.archivo_vinculo:
        return Response(
            {"detail": "Archivo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    tipos_mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "pdf": "application/pdf",
    }

    extension = evidencia.extension

    respuesta = FileResponse(
        evidencia.archivo_vinculo.open("rb"),
        content_type=tipos_mime.get(
            extension,
            "application/octet-stream",
        ),
    )

    modo = (
        "attachment"
        if request.query_params.get("descargar")
        else "inline"
    )

    respuesta["Content-Disposition"] = (
        f'{modo}; filename="{evidencia.codigo_evidencia}.{extension}"'
    )

    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, no-store"

    return respuesta


# ---------------------------------------------------------------------
# LISTAR EVIDENCIAS PENDIENTES DE VALIDACIÓN
#
# GET /api/validaciones/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def validacion_list(request):

    if not _puede_consultar_validaciones(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para consultar validaciones."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    funcionario = get_funcionario(request.user)

    evidencias = (
        _evidencias_autorizadas(request.user)
        .filter(
            estado_revision=Evidencia.ESTADO_PENDIENTE,
        )
        .exclude(
            actividad__funcionario=funcionario,
        )
    )

    filtros = request.query_params

    funcionario_id = filtros.get("funcionario")
    item_id = filtros.get("item")

    if funcionario_id and funcionario_id.isdigit():
        evidencias = evidencias.filter(
            actividad__funcionario_id=funcionario_id,
        )

    if item_id and item_id.isdigit():
        evidencias = evidencias.filter(
            actividad__item_id=item_id,
        )

    fecha_desde = filtros.get("fecha_desde")
    fecha_hasta = filtros.get("fecha_hasta")

    if fecha_desde:
        evidencias = evidencias.filter(
            fecha_carga__date__gte=fecha_desde,
        )

    if fecha_hasta:
        evidencias = evidencias.filter(
            fecha_carga__date__lte=fecha_hasta,
        )

    termino = filtros.get("q", "").strip()

    if termino:
        from django.db.models import Q

        evidencias = evidencias.filter(
            Q(codigo_evidencia__icontains=termino)
            | Q(actividad__accion__icontains=termino)
            | Q(actividad__funcionario__nombre__icontains=termino)
            | Q(actividad__item__nombre_item__icontains=termino)
        )

    evidencias = evidencias.order_by(
        "fecha_carga",
        "id_evidencia",
    )

    return Response(
        EvidenciaSerializer(
            evidencias,
            many=True,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# HISTORIAL DE VALIDACIONES DE UNA EVIDENCIA
#
# GET /api/evidencias/<pk>/validaciones/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def evidencia_validaciones(request, pk):

    if not _puede_consultar_validaciones(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para consultar "
                    "el historial de validaciones."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    evidencia = _obtener_evidencia_autorizada(
        request.user,
        pk,
    )

    if evidencia is None:
        return Response(
            {"detail": "Evidencia no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    historial = (
        CRUDValidacion.mostrar_historial_validacion(
            evidencia.codigo_evidencia,
        )
    )

    return Response(
        ValidacionSerializer(
            historial,
            many=True,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# APROBAR, RECHAZAR O SOLICITAR CORRECCIÓN
#
# POST /api/evidencias/<pk>/validar/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def evidencia_validar(request, pk):

    if not _puede_gestionar_validaciones(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para validar evidencias."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    evidencia = _obtener_evidencia_autorizada(
        request.user,
        pk,
    )

    if evidencia is None:
        return Response(
            {"detail": "Evidencia no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if evidencia.estado_revision != Evidencia.ESTADO_PENDIENTE:
        return Response(
            {
                "detail": (
                    "Esta evidencia ya fue revisada."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if _es_autor_actividad(
        request.user,
        evidencia.actividad,
    ):
        return Response(
            {
                "detail": (
                    "No puedes validar evidencias de tus "
                    "propias actividades."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    decision = request.data.get("decision")
    observacion = request.data.get("observacion", "")

    if decision not in dict(Validacion.DECISIONES):
        return Response(
            {
                "decision": (
                    "Debes seleccionar Aprobar, Rechazar "
                    "o Corrección."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(observacion, str):
        return Response(
            {
                "observacion": (
                    "La observación debe ser texto."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    observacion = observacion.strip()

    if (
        decision != Validacion.DECISION_APROBADA
        and not observacion
    ):
        return Response(
            {
                "observacion": (
                    "La observación es obligatoria para "
                    "rechazar o solicitar corrección."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    acciones = {
        Validacion.DECISION_APROBADA:
            CRUDValidacion.aprobar_evidencia,

        Validacion.DECISION_RECHAZADA:
            CRUDValidacion.rechazar_evidencia,

        Validacion.DECISION_CORRECCION:
            CRUDValidacion.solicitar_correccion,
    }

    try:
        evidencia = acciones[decision](
            evidencia,
            observacion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    validacion = (
        Validacion.objects
        .filter(evidencia=evidencia)
        .order_by("-version")
        .first()
    )

    return Response(
        {
            "evidencia": EvidenciaSerializer(
                evidencia,
                context={"request": request},
            ).data,
            "validacion": ValidacionSerializer(
                validacion,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


# =====================================================================
# API AGENDA COLECTIVA - COMPROMISOS
# =====================================================================


def _puede_consultar_compromisos(user):
    return tiene_permiso(user, "agenda.ver")


def _compromisos_autorizados(user):
    return (
        compromisos_visibles(user)
        .select_related(
            "funcionario",
            "funcionario__cargo",
            "delegacion",
            "item_medible",
            "periodo",
        )
        .prefetch_related("historial")
    )


def _obtener_compromiso_autorizado(user, pk):
    return _compromisos_autorizados(user).filter(
        pk=pk
    ).first()


def _filtrar_compromisos_api(queryset, filtros):
    """
    Aplica los mismos criterios de búsqueda de la agenda web.
    Devuelve (queryset, error).
    """

    for campo, filtro in (
        ("funcionario", "funcionario_id"),
        ("periodo", "periodo_id"),
        ("delegacion", "delegacion_id"),
    ):
        valor = filtros.get(campo)

        if valor:
            if not valor.isdigit():
                return None, {
                    campo: "Debe ingresar un identificador numérico."
                }

            queryset = queryset.filter(
                **{filtro: valor}
            )

    estado = filtros.get("estado")

    if estado:
        estados_validos = dict(Compromiso.ESTADOS)

        if estado not in estados_validos:
            return None, {
                "estado": "El estado indicado no es válido."
            }

        queryset = queryset.filter(estado=estado)

    fecha_desde_texto = filtros.get("fecha_desde", "").strip()
    fecha_hasta_texto = filtros.get("fecha_hasta", "").strip()

    fecha_desde = (
        parse_date(fecha_desde_texto)
        if fecha_desde_texto
        else None
    )

    fecha_hasta = (
        parse_date(fecha_hasta_texto)
        if fecha_hasta_texto
        else None
    )

    if fecha_desde_texto and fecha_desde is None:
        return None, {
            "fecha_desde": "Formato inválido. Utiliza YYYY-MM-DD."
        }

    if fecha_hasta_texto and fecha_hasta is None:
        return None, {
            "fecha_hasta": "Formato inválido. Utiliza YYYY-MM-DD."
        }

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        return None, {
            "detail": (
                "La fecha desde no puede ser posterior "
                "a la fecha hasta."
            )
        }

    if fecha_desde:
        queryset = queryset.filter(
            fecha_comprometida__gte=fecha_desde
        )

    if fecha_hasta:
        queryset = queryset.filter(
            fecha_comprometida__lte=fecha_hasta
        )

    territorio = filtros.get("territorio", "").strip()

    if territorio:
        queryset = queryset.filter(
            territorio__icontains=territorio
        )

    termino = filtros.get("q", "").strip()

    if termino:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(solicitante__icontains=termino)
            | Q(origen__icontains=termino)
            | Q(territorio__icontains=termino)
            | Q(funcionario__nombre__icontains=termino)
        )

    plazo = filtros.get("plazo", "").strip()

    if plazo == "vencido":
        queryset = queryset.vencidos()

    elif plazo == "por_vencer":
        queryset = queryset.por_vencer()

    elif plazo == "abiertos":
        queryset = queryset.abiertos()

    elif plazo:
        return None, {
            "plazo": (
                "Utiliza vencido, por_vencer o abiertos."
            )
        }

    return queryset.order_by(
        "fecha_comprometida",
        "id_compromiso",
    ), None


# ---------------------------------------------------------------------
# LISTAR Y REGISTRAR COMPROMISOS
#
# GET  /api/compromisos/
# POST /api/compromisos/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def compromiso_list(request):

    if request.method == "GET":

        if not _puede_consultar_compromisos(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar "
                        "la agenda colectiva."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset, error = _filtrar_compromisos_api(
            _compromisos_autorizados(request.user),
            request.query_params,
        )

        if error:
            return Response(
                error,
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            CompromisoSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # POST: registrar compromiso.

    if not tiene_permiso(request.user, "agenda.registrar"):
        return Response(
            {
                "detail": (
                    "No tienes permiso para registrar compromisos."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = CompromisoSerializer(
        data=request.data,
        context={"request": request},
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        compromiso = Compromiso(
            **serializer.validated_data
        )

        compromiso = CRUDCompromiso.crear_compromiso(
            compromiso,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CompromisoSerializer(
            compromiso,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y MODIFICAR COMPROMISO
#
# GET   /api/compromisos/<pk>/
# PUT   /api/compromisos/<pk>/
# PATCH /api/compromisos/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def compromiso_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_compromisos(request.user):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para consultar compromisos."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not tiene_permiso(request.user, "agenda.editar"):
        return Response(
            {
                "detail": (
                    "No tienes permiso para editar compromisos."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    compromiso = _obtener_compromiso_autorizado(
        request.user,
        pk,
    )

    if compromiso is None:
        return Response(
            {"detail": "Compromiso no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            CompromisoSerializer(
                compromiso,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    if not puede_gestionar(request.user, compromiso):
        return Response(
            {
                "detail": (
                    "No tienes autorización para modificar "
                    "este compromiso."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if compromiso.realizado:
        return Response(
            {
                "detail": (
                    "Un compromiso realizado no puede modificarse."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CompromisoSerializer(
        compromiso,
        data=request.data,
        partial=(request.method == "PATCH"),
        context={"request": request},
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(compromiso, campo, valor)

        compromiso = CRUDCompromiso.modificar_compromiso(
            compromiso,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CompromisoSerializer(
            compromiso,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CAMBIAR ESTADO DEL COMPROMISO
#
# POST /api/compromisos/<pk>/estado/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def compromiso_estado(request, pk):

    if not tiene_permiso(request.user, "agenda.estado"):
        return Response(
            {
                "detail": (
                    "No tienes permiso para cambiar estados."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    compromiso = _obtener_compromiso_autorizado(
        request.user,
        pk,
    )

    if compromiso is None:
        return Response(
            {"detail": "Compromiso no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    nuevo_estado = request.data.get(
        "estado",
        request.data.get("nuevo_estado"),
    )

    observacion = request.data.get("observacion", "")

    if nuevo_estado not in dict(Compromiso.ESTADOS):
        return Response(
            {
                "estado": "Debe seleccionar un estado válido."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(observacion, str):
        return Response(
            {
                "observacion": "La observación debe ser texto."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        compromiso = CRUDCompromiso.actualizar_estado(
            compromiso,
            nuevo_estado,
            observacion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CompromisoSerializer(
            compromiso,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# REASIGNAR RESPONSABLE
#
# POST /api/compromisos/<pk>/reasignar/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def compromiso_reasignar(request, pk):

    if not tiene_permiso(request.user, "agenda.reasignar"):
        return Response(
            {
                "detail": (
                    "No tienes permiso para reasignar compromisos."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    compromiso = _obtener_compromiso_autorizado(
        request.user,
        pk,
    )

    if compromiso is None:
        return Response(
            {"detail": "Compromiso no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not supervisa(
        request.user,
        compromiso.delegacion_id,
    ):
        return Response(
            {
                "detail": (
                    "Solo la supervisión autorizada puede "
                    "reasignar este compromiso."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    funcionario_id = request.data.get(
        "funcionario",
        request.data.get("nuevo_responsable"),
    )

    motivo = request.data.get("motivo", "")

    if not str(funcionario_id or "").isdigit():
        return Response(
            {
                "funcionario": (
                    "Debe indicar el identificador del nuevo responsable."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(motivo, str) or not motivo.strip():
        return Response(
            {
                "motivo": (
                    "Debe indicar el motivo de la reasignación."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    from agenda.services import funcionarios_asignables

    nuevo_responsable = (
        funcionarios_asignables(request.user)
        .filter(pk=funcionario_id)
        .first()
    )

    if nuevo_responsable is None:
        return Response(
            {
                "funcionario": (
                    "El funcionario no está disponible "
                    "para esta reasignación."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        compromiso = CRUDCompromiso.reasignar_responsable(
            compromiso,
            nuevo_responsable,
            motivo,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CompromisoSerializer(
            compromiso,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# HISTORIAL DE TRANSICIONES
#
# GET /api/compromisos/<pk>/historial/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compromiso_historial(request, pk):

    if not _puede_consultar_compromisos(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para consultar el historial."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    compromiso = _obtener_compromiso_autorizado(
        request.user,
        pk,
    )

    if compromiso is None:
        return Response(
            {"detail": "Compromiso no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    historial = CRUDHistorialTransiciones.mostrar_historial_por_compromiso(
        compromiso.pk
    )

    return Response(
        HistorialTransicionesSerializer(
            historial,
            many=True,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# RESUMEN COLECTIVO Y CONTROL DE PLAZOS
#
# GET /api/compromisos/resumen/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compromiso_resumen(request):

    if not _puede_consultar_compromisos(request.user):
        return Response(
            {
                "detail": (
                    "No tienes permiso para consultar el resumen."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    queryset, error = _filtrar_compromisos_api(
        _compromisos_autorizados(request.user),
        request.query_params,
    )

    if error:
        return Response(
            error,
            status=status.HTTP_400_BAD_REQUEST,
        )

    resumen = CRUDCompromiso.resumen_colectivo(queryset)

    plazos = CRUDCompromiso.controlar_plazos(
        queryset=queryset
    )

    contexto = {"request": request}

    return Response(
        {
            "resumen": resumen,
            "plazos": {
                "dias_alerta": plazos["dias_alerta"],
                "vencidos": CompromisoSerializer(
                    plazos["vencidos"],
                    many=True,
                    context=contexto,
                ).data,
                "por_vencer": CompromisoSerializer(
                    plazos["por_vencer"],
                    many=True,
                    context=contexto,
                ).data,
                "realizados_fuera_de_plazo": CompromisoSerializer(
                    plazos["realizados_fuera_de_plazo"],
                    many=True,
                    context=contexto,
                ).data,
            },
        },
        status=status.HTTP_200_OK,
    )

# =====================================================================
# API DE ATENCIÓN SOCIAL
# CASOS Y GESTIONES
# =====================================================================


def _puede_consultar_social(user):
    return tiene_permiso(user, "atenciones.ver")


def _casos_sociales_autorizados(user):
    return (
        casos_visibles(user)
        .select_related("delegacion")
        .prefetch_related(
            "gestiones",
            "gestiones__tipo_atencion",
            "gestiones__subatencion",
            "gestiones__funcionario",
            "gestiones__delegacion",
        )
    )


def _obtener_caso_social_autorizado(user, pk):
    return _casos_sociales_autorizados(user).filter(
        pk=pk
    ).first()


def _filtrar_casos_sociales(queryset, filtros):
    q = filtros.get("q", "").strip()

    if q:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(nombre__icontains=q)
            | Q(territorio__icontains=q)
            | Q(rut__icontains=q)
        )

    territorio = filtros.get("territorio", "").strip()

    if territorio:
        queryset = queryset.filter(
            territorio__icontains=territorio
        )

    estado = filtros.get("estado_caso", "").strip()

    if estado:
        if estado not in dict(UsuarioSocial.ESTADOS):
            return None, {
                "estado_caso": "El estado indicado no es válido."
            }

        queryset = queryset.filter(
            estado_caso=estado
        )

    delegacion = filtros.get("delegacion", "").strip()

    if delegacion:
        if not delegacion.isdigit():
            return None, {
                "delegacion": "Debe ingresar un identificador numérico."
            }

        queryset = queryset.filter(
            delegacion_id=delegacion
        )

    fecha_desde_texto = filtros.get(
        "fecha_desde",
        "",
    ).strip()

    fecha_hasta_texto = filtros.get(
        "fecha_hasta",
        "",
    ).strip()

    fecha_desde = (
        parse_date(fecha_desde_texto)
        if fecha_desde_texto
        else None
    )

    fecha_hasta = (
        parse_date(fecha_hasta_texto)
        if fecha_hasta_texto
        else None
    )

    if fecha_desde_texto and fecha_desde is None:
        return None, {
            "fecha_desde": "Formato inválido. Utiliza YYYY-MM-DD."
        }

    if fecha_hasta_texto and fecha_hasta is None:
        return None, {
            "fecha_hasta": "Formato inválido. Utiliza YYYY-MM-DD."
        }

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        return None, {
            "detail": (
                "La fecha desde no puede ser posterior "
                "a la fecha hasta."
            )
        }

    if fecha_desde:
        queryset = queryset.filter(
            fecha_primer_registro__gte=fecha_desde
        )

    if fecha_hasta:
        queryset = queryset.filter(
            fecha_primer_registro__lte=fecha_hasta
        )

    return queryset.order_by(
        "-fecha_primer_registro",
        "nombre",
    ), None


# ---------------------------------------------------------------------
# LISTAR Y CREAR CASOS
#
# GET  /api/casos/
# POST /api/casos/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def caso_social_list(request):

    if request.method == "GET":

        if not _puede_consultar_social(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar casos sociales."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset, error = _filtrar_casos_sociales(
            _casos_sociales_autorizados(request.user),
            request.query_params,
        )

        if error:
            return Response(
                error,
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            UsuarioSocialSerializer(
                queryset,
                many=True,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    if not tiene_permiso(request.user, "atenciones.registrar"):
        return Response(
            {"detail": "No tienes permiso para registrar casos sociales."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = UsuarioSocialSerializer(
        data=request.data,
        context={"request": request},
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    delegacion_id = get_delegacion_activa(request.user)

    if not delegacion_id:
        return Response(
            {
                "detail": (
                    "Debes tener una delegación activa para "
                    "registrar un caso social."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    delegacion = Delegacion.objects.filter(
        pk=delegacion_id
    ).first()

    if delegacion is None:
        return Response(
            {"detail": "La delegación activa no existe."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    datos = dict(serializer.validated_data)
    primera_gestion_data = datos.pop("primera_gestion")

    caso = UsuarioSocial(**datos)

    gestion_serializer = AtencionSocialSerializer(
        data=primera_gestion_data,
        context={
            "request": request,
            "caso": caso,
            "area": delegacion.ambito,
        },
    )

    if not gestion_serializer.is_valid():
        return Response(
            {"primera_gestion": gestion_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        primera_gestion = AtencionSocial(
            **gestion_serializer.validated_data
        )

        caso = CRUDUsuarioSocial.crear_caso(
            caso,
            primera_gestion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    caso = _obtener_caso_social_autorizado(
        request.user,
        caso.pk,
    )

    return Response(
        UsuarioSocialSerializer(
            caso,
            context={"request": request},
        ).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y EDITAR UN CASO
#
# GET   /api/casos/<pk>/
# PUT   /api/casos/<pk>/
# PATCH /api/casos/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def caso_social_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_social(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar casos sociales."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not tiene_permiso(request.user, "atenciones.editar"):
        return Response(
            {"detail": "No tienes permiso para editar casos sociales."},
            status=status.HTTP_403_FORBIDDEN,
        )

    caso = _obtener_caso_social_autorizado(
        request.user,
        pk,
    )

    if caso is None:
        return Response(
            {"detail": "Caso social no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            UsuarioSocialSerializer(
                caso,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    if caso.cerrado:
        return Response(
            {
                "detail": (
                    "El caso está cerrado. Debes reabrirlo "
                    "antes de modificar sus datos."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not puede_escribir(
        request.user,
        caso.delegacion_id,
    ):
        return Response(
            {"detail": "No tienes autorización sobre este caso."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = UsuarioSocialSerializer(
        caso,
        data=request.data,
        partial=(request.method == "PATCH"),
        context={"request": request},
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(caso, campo, valor)

        caso = CRUDUsuarioSocial.modificar_caso(
            caso,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        UsuarioSocialSerializer(
            caso,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CAMBIAR ESTADO DE UN CASO
#
# POST /api/casos/<pk>/estado/
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def caso_social_estado(request, pk):

    if not tiene_permiso(request.user, "atenciones.estado"):
        return Response(
            {"detail": "No tienes permiso para cambiar estados de casos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    caso = _obtener_caso_social_autorizado(
        request.user,
        pk,
    )

    if caso is None:
        return Response(
            {"detail": "Caso social no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    nuevo_estado = request.data.get("estado_caso")

    if nuevo_estado not in dict(UsuarioSocial.ESTADOS):
        return Response(
            {"estado_caso": "Debes seleccionar un estado válido."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        caso = CRUDUsuarioSocial.cambiar_estado_caso(
            caso,
            nuevo_estado,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        UsuarioSocialSerializer(
            caso,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# LISTAR Y REGISTRAR GESTIONES DE UN CASO
#
# GET  /api/casos/<pk>/gestiones/
# POST /api/casos/<pk>/gestiones/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def caso_social_gestiones(request, pk):

    caso = _obtener_caso_social_autorizado(
        request.user,
        pk,
    )

    if caso is None:
        return Response(
            {"detail": "Caso social no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":

        if not _puede_consultar_social(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar gestiones."},
                status=status.HTTP_403_FORBIDDEN,
            )

        gestiones = CRUDAtencionSocial.mostrar_gestiones_por_caso(
            caso.pk
        )

        return Response(
            AtencionSocialSerializer(
                gestiones,
                many=True,
                context={
                    "request": request,
                    "caso": caso,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    if not tiene_permiso(request.user, "atenciones.gestionar"):
        return Response(
            {"detail": "No tienes permiso para registrar gestiones."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not puede_escribir(
        request.user,
        caso.delegacion_id,
    ):
        return Response(
            {"detail": "No tienes autorización sobre este caso."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AtencionSocialSerializer(
        data=request.data,
        context={
            "request": request,
            "caso": caso,
        },
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        gestion = AtencionSocial(
            usuario=caso,
            **serializer.validated_data,
        )

        gestion = CRUDAtencionSocial.registrar_gestion(
            gestion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        AtencionSocialSerializer(
            gestion,
            context={
                "request": request,
                "caso": caso,
            },
        ).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------
# CONSULTAR Y CORREGIR UNA GESTIÓN
#
# GET   /api/gestiones/<pk>/
# PUT   /api/gestiones/<pk>/
# PATCH /api/gestiones/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def gestion_social_detail(request, pk):

    if request.method == "GET":

        if not _puede_consultar_social(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar gestiones."},
                status=status.HTTP_403_FORBIDDEN,
            )

    elif not tiene_permiso(request.user, "atenciones.gestionar"):
        return Response(
            {"detail": "No tienes permiso para corregir gestiones."},
            status=status.HTTP_403_FORBIDDEN,
        )

    gestion = (
        gestiones_visibles(request.user)
        .filter(pk=pk)
        .select_related(
            "usuario",
            "usuario__delegacion",
            "tipo_atencion",
            "subatencion",
            "funcionario",
            "delegacion",
        )
        .first()
    )

    if gestion is None:
        return Response(
            {"detail": "Gestión social no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    caso = gestion.usuario

    if request.method == "GET":
        return Response(
            AtencionSocialSerializer(
                gestion,
                context={
                    "request": request,
                    "caso": caso,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    if caso.cerrado:
        return Response(
            {"detail": "No se pueden modificar gestiones de un caso cerrado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not puede_escribir(
        request.user,
        caso.delegacion_id,
    ):
        return Response(
            {"detail": "No tienes autorización sobre esta gestión."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AtencionSocialSerializer(
        gestion,
        data=request.data,
        partial=(request.method == "PATCH"),
        context={
            "request": request,
            "caso": caso,
        },
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(gestion, campo, valor)

        gestion = CRUDAtencionSocial.modificar_gestion(
            gestion,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        AtencionSocialSerializer(
            gestion,
            context={
                "request": request,
                "caso": caso,
            },
        ).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# ESTADÍSTICAS DE ATENCIÓN SOCIAL
#
# GET /api/atenciones/estadisticas/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def atencion_social_estadisticas(request):

    if not _puede_consultar_social(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar estadísticas sociales."},
            status=status.HTTP_403_FORBIDDEN,
        )

    queryset = gestiones_visibles(request.user)

    fecha_desde_texto = request.query_params.get(
        "fecha_desde",
        "",
    ).strip()

    fecha_hasta_texto = request.query_params.get(
        "fecha_hasta",
        "",
    ).strip()

    fecha_desde = (
        parse_date(fecha_desde_texto)
        if fecha_desde_texto
        else None
    )

    fecha_hasta = (
        parse_date(fecha_hasta_texto)
        if fecha_hasta_texto
        else None
    )

    if fecha_desde_texto and fecha_desde is None:
        return Response(
            {"fecha_desde": "Formato inválido. Utiliza YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if fecha_hasta_texto and fecha_hasta is None:
        return Response(
            {"fecha_hasta": "Formato inválido. Utiliza YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        return Response(
            {
                "detail": (
                    "La fecha desde no puede ser posterior "
                    "a la fecha hasta."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if fecha_desde:
        queryset = queryset.filter(fecha__gte=fecha_desde)

    if fecha_hasta:
        queryset = queryset.filter(fecha__lte=fecha_hasta)

    estadisticas = estadisticas_atenciones(queryset)

    return Response(
        estadisticas,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# CATÁLOGOS
# ---------------------------------------------------------------------

def _puede_consultar_catalogos(user):
    return tiene_permiso(user, "catalogos.ver")


def _puede_editar_catalogos(user):
    return tiene_permiso(user, "catalogos.editar")


def _catalogos_autorizados():
    return Catalogo.objects.select_related(
        "tipo_atencion_padre"
    ).all()


def _filtrar_catalogos_api(queryset, filtros):
    termino = filtros.get("q", "").strip()

    if termino:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(nombre__icontains=termino)
            | Q(codigo__icontains=termino)
            | Q(descripcion__icontains=termino)
        )

    for campo in ("tipo_catalogo", "area", "estado"):
        valor = filtros.get(campo, "").strip()

        if not valor:
            continue

        if campo == "tipo_catalogo":
            if valor not in dict(Catalogo.TIPOS):
                return None, {
                    campo: "El tipo de catálogo indicado no es válido."
                }

        elif campo == "estado":
            if valor not in dict(Catalogo.ESTADOS):
                return None, {
                    campo: "El estado indicado no es válido."
                }

        queryset = queryset.filter(**{campo: valor})

    return queryset, None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def catalogo_list(request):
    """
    GET  /api/catalogos/
    POST /api/catalogos/
    """

    if request.method == "GET":
        if not _puede_consultar_catalogos(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar catálogos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset, error = _filtrar_catalogos_api(
            _catalogos_autorizados(),
            request.query_params,
        )

        if error:
            return Response(
                error,
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            CatalogoSerializer(queryset, many=True).data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_catalogos(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar catálogos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = CatalogoSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        elemento = Catalogo(**serializer.validated_data)

        elemento = CRUDCatalogo.crear_elemento_catalogo(
            elemento,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CatalogoSerializer(elemento).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def catalogo_detail(request, pk):
    """
    GET   /api/catalogos/<pk>/
    PUT   /api/catalogos/<pk>/
    PATCH /api/catalogos/<pk>/
    """

    if request.method == "GET":
        if not _puede_consultar_catalogos(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar catálogos."},
                status=status.HTTP_403_FORBIDDEN,
            )
    elif not _puede_editar_catalogos(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar catálogos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    elemento = _catalogos_autorizados().filter(
        pk=pk
    ).first()

    if elemento is None:
        return Response(
            {"detail": "Elemento de catálogo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            CatalogoSerializer(elemento).data,
            status=status.HTTP_200_OK,
        )

    serializer = CatalogoSerializer(
        elemento,
        data=request.data,
        partial=(request.method == "PATCH"),
    )

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(elemento, campo, valor)

        elemento = CRUDCatalogo.modificar_elemento_catalogo(
            elemento,
            request.user,
        )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CatalogoSerializer(elemento).data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def catalogo_estado(request, pk):
    """
    GET  /api/catalogos/<pk>/estado/
    POST /api/catalogos/<pk>/estado/

    POST alterna entre Activo e Inactivo utilizando el servicio existente.
    """

    if request.method == "GET":
        if not _puede_consultar_catalogos(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar catálogos."},
                status=status.HTTP_403_FORBIDDEN,
            )
    elif not _puede_editar_catalogos(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar catálogos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    elemento = _catalogos_autorizados().filter(
        pk=pk
    ).first()

    if elemento is None:
        return Response(
            {"detail": "Elemento de catálogo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(
            CatalogoSerializer(elemento).data,
            status=status.HTTP_200_OK,
        )

    try:
        if elemento.activo:
            elemento = CRUDCatalogo.desactivar_elemento_catalogo(
                elemento,
                request.user,
            )
        else:
            elemento = CRUDCatalogo.activar_elemento_catalogo(
                elemento,
                request.user,
            )

    except ReglaNegocioError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CatalogoSerializer(elemento).data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def catalogo_historial(request, pk):
    """
    GET /api/catalogos/<pk>/historial/
    """

    if not _puede_consultar_catalogos(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar catálogos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    elemento = _catalogos_autorizados().filter(
        pk=pk
    ).first()

    if elemento is None:
        return Response(
            {"detail": "Elemento de catálogo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    versiones = (
        CatalogoVersion.objects
        .filter(objeto_id=elemento.pk)
        .select_related("creado_por")
        .order_by("-numero_version")
    )

    resultados = []

    for version in versiones:
        resultados.append({
            "id": version.pk,
            "numero_version": version.numero_version,
            "vigente_desde": version.vigente_desde,
            "vigente_hasta": version.vigente_hasta,
            "datos": version.datos,
            "creado_por": (
                version.creado_por.username
                if version.creado_por_id
                else None
            ),
        })

    return Response(
        {
            "catalogo": CatalogoSerializer(elemento).data,
            "total_versiones": len(resultados),
            "versiones": resultados,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def catalogo_por_area_api(request):
    """
    GET /api/catalogos/por-area/?area=...&tipo=...
    Devuelve solo elementos activos y compatibles con el área.
    """

    if not _puede_consultar_catalogos(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar catálogos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    area = request.query_params.get("area") or None
    tipo = request.query_params.get("tipo") or None

    if tipo and tipo not in dict(Catalogo.TIPOS):
        return Response(
            {"tipo": "El tipo de catálogo indicado no es válido."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    elementos = CRUDCatalogo.mostrar_catalogo_por_area(
        area,
        tipo,
    ).select_related("tipo_atencion_padre")

    return Response(
        CatalogoSerializer(elementos, many=True).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# AUDITORÍA
# GET /api/auditoria/
# GET /api/auditoria/<pk>/
# GET /api/auditoria/historial/<entidad>/<pk>/
# ---------------------------------------------------------------------

def _puede_consultar_auditoria_api(user):
    return (
        puede_consultar_auditoria(user)
        and tiene_permiso(user, "auditoria.ver")
    )


def _auditoria_filtrada_api(request):
    """
    Aplica los mismos filtros del historial web mediante
    el servicio filtrar_auditoria.
    """
    datos = {}

    for campo in ("evento", "entidad"):
        valor = request.query_params.get(campo, "").strip()
        if valor:
            datos[campo] = valor

    id_entidad = request.query_params.get("id_entidad", "").strip()
    if id_entidad:
        if not id_entidad.isdigit():
            return None, "El ID de entidad debe ser numérico."
        datos["id_entidad"] = int(id_entidad)

    funcionario = request.query_params.get("funcionario", "").strip()
    if funcionario:
        if not funcionario.isdigit():
            return None, "El funcionario debe ser un ID numérico."
        datos["funcionario"] = int(funcionario)

    for campo in ("fecha_desde", "fecha_hasta"):
        valor = request.query_params.get(campo, "").strip()
        if valor:
            fecha = parse_date(valor)
            if fecha is None:
                return None, (
                    f"El parámetro {campo} debe tener formato YYYY-MM-DD."
                )
            datos[campo] = fecha

    if (
        datos.get("fecha_desde")
        and datos.get("fecha_hasta")
        and datos["fecha_hasta"] < datos["fecha_desde"]
    ):
        return None, (
            "La fecha_hasta no puede ser anterior a fecha_desde."
        )

    q = request.query_params.get("q", "").strip()
    if q:
        datos["q"] = q

    queryset = Auditoria.objects.select_related("funcionario")

    queryset, _ = filtrar_auditoria(queryset, datos)

    return queryset.order_by("-fecha", "-id_auditoria"), None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auditoria_list(request):
    if not _puede_consultar_auditoria_api(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar la auditoría."},
            status=status.HTTP_403_FORBIDDEN,
        )

    queryset, error = _auditoria_filtrada_api(request)

    if error:
        return Response(
            {"detail": error},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = AuditoriaSerializer(
        queryset,
        many=True,
    )

    return Response(
        serializer.data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auditoria_detail(request, pk):
    if not _puede_consultar_auditoria_api(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar la auditoría."},
            status=status.HTTP_403_FORBIDDEN,
        )

    evento = (
        Auditoria.objects
        .select_related("funcionario")
        .filter(pk=pk)
        .first()
    )

    if evento is None:
        return Response(
            {"detail": "Evento de auditoría no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        AuditoriaSerializer(evento).data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auditoria_historial_entidad(request, entidad, pk):
    if not _puede_consultar_auditoria_api(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar la auditoría."},
            status=status.HTTP_403_FORBIDDEN,
        )

    queryset = (
        Auditoria.objects
        .select_related("funcionario")
        .filter(
            entidad_afectada=entidad,
            id_entidad_afectada=pk,
        )
        .order_by("-fecha", "-id_auditoria")
    )

    return Response(
        AuditoriaSerializer(queryset, many=True).data,
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# NOTIFICACIONES
# GET  /api/notificaciones/
# POST /api/notificaciones/marcar-leidas/
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notificacion_list(request):
    queryset = (
        Notificacion.objects
        .filter(usuario=request.user)
        .select_related(
            "auditoria",
            "auditoria__funcionario",
            "delegacion",
        )
        .order_by("-fecha_creacion", "-id_notificacion")
    )

    leida = request.query_params.get("leida")

    if leida in ("true", "1"):
        queryset = queryset.filter(leida=True)
    elif leida in ("false", "0"):
        queryset = queryset.filter(leida=False)

    pendientes = Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    ).count()

    return Response(
        {
            "pendientes": pendientes,
            "total": queryset.count(),
            "notificaciones": NotificacionSerializer(
                queryset,
                many=True,
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notificacion_marcar_leidas(request):
    """
    Marca como leídas las notificaciones propias.
    Si se entrega una lista de IDs, solo marca esas notificaciones.
    """
    ids = request.data.get("ids")

    queryset = Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    )

    if ids is not None:
        if not isinstance(ids, list) or not all(
            isinstance(pk, int) and pk > 0 for pk in ids
        ):
            return Response(
                {"detail": "El campo ids debe ser una lista de IDs positivos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = queryset.filter(pk__in=ids)

    actualizadas = queryset.update(
        leida=True,
        fecha_lectura=timezone.now(),
    )

    pendientes = Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    ).count()

    return Response(
        {
            "detail": "Notificaciones actualizadas.",
            "actualizadas": actualizadas,
            "pendientes": pendientes,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------
# COMENTARIOS DE REGISTROS
# GET  /api/comentarios/<app_label>/<model_name>/<pk>/
# POST /api/comentarios/<app_label>/<model_name>/<pk>/
# ---------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def comentarios_registro_api(request, app_label, model_name, pk):
    try:
        registro, delegacion_id = obtener_registro_comentable(
            request.user,
            app_label,
            model_name,
            pk,
        )

        if request.method == "GET":
            conversacion = obtener_conversacion(
                registro,
                delegacion_id,
            )

            serializer = ComentarioRegistroSerializer(
                conversacion,
                many=True,
            )

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        serializer = ComentarioRegistroSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        respuesta_a = None
        respuesta_id = serializer.validated_data.get("respuesta_a")

        if respuesta_id is not None:
            conversacion = obtener_conversacion(
                registro,
                delegacion_id,
            )

            respuesta_a = conversacion.filter(
                pk=respuesta_id.pk,
            ).first()

            if respuesta_a is None:
                return Response(
                    {
                        "respuesta_a": (
                            "La respuesta seleccionada no pertenece "
                            "a esta conversación."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        comentario = crear_comentario(
            registro=registro,
            delegacion_id=delegacion_id,
            usuario=request.user,
            mensaje=serializer.validated_data["mensaje"],
            respuesta_a=respuesta_a,
        )

        return Response(
            ComentarioRegistroSerializer(comentario).data,
            status=status.HTTP_201_CREATED,
        )

    except PermissionDenied as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )

# ---------------------------------------------------------------------
# CARGOS
# ---------------------------------------------------------------------

def _puede_consultar_cargos(user):
    return (
        tiene_rol(user, *ROLES_SUPERVISION)
        and tiene_permiso(user, "cargos.ver")
    )


def _puede_editar_cargos(user):
    return (
        tiene_rol(user, *ROLES_CONFIGURACION)
        and tiene_permiso(user, "cargos.editar")
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def cargo_list(request):
    if request.method == "GET":
        if not _puede_consultar_cargos(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar cargos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = Cargo.objects.all().order_by("nombre_cargo")
        return Response(
            CargoSerializer(queryset, many=True).data,
            status=status.HTTP_200_OK,
        )

    if not _puede_editar_cargos(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar cargos."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = CargoSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        cargo = CRUDCargo.crear_cargo(
            Cargo(**serializer.validated_data),
            request.user,
        )
    except (ReglaNegocioError, ValidationError) as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        CargoSerializer(cargo).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def cargo_detail(request, pk):
    if request.method == "GET":
        permitido = _puede_consultar_cargos(request.user)
    else:
        permitido = _puede_editar_cargos(request.user)

    if not permitido:
        return Response(
            {"detail": "No tienes permiso para esta operación."},
            status=status.HTTP_403_FORBIDDEN,
        )

    cargo = Cargo.objects.filter(pk=pk).first()
    if cargo is None:
        return Response(
            {"detail": "Cargo no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":
        return Response(CargoSerializer(cargo).data)

    if request.method == "DELETE":
        try:
            CRUDCargo.eliminar_cargo(cargo, request.user)
        except (ReglaNegocioError, ValidationError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = CargoSerializer(
        cargo,
        data=request.data,
        partial=request.method == "PATCH",
    )
    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        for campo, valor in serializer.validated_data.items():
            setattr(cargo, campo, valor)
        cargo = CRUDCargo.modificar_cargo(cargo, request.user)
    except (ReglaNegocioError, ValidationError) as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(CargoSerializer(cargo).data)


# ---------------------------------------------------------------------
# HISTORIAL DE VERSIONES DE ÍTEMS MEDIBLES
# ---------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def item_historial(request, pk):
    if not _puede_consultar_items(request.user):
        return Response(
            {"detail": "No tienes permiso para consultar ítems."},
            status=status.HTTP_403_FORBIDDEN,
        )

    item = ItemMedible.objects.filter(pk=pk).first()
    if item is None:
        return Response(
            {"detail": "Ítem medible no encontrado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    versiones = (
        ItemMedibleVersion.objects
        .filter(objeto_id=item.pk)
        .select_related("creado_por")
        .order_by("-numero_version")
    )

    datos = [
        {
            "objeto_id": version.objeto_id,
            "numero_version": version.numero_version,
            "vigente_desde": version.vigente_desde,
            "vigente_hasta": version.vigente_hasta,
            "datos": version.datos,
            "creado_por": (
                version.creado_por.username
                if version.creado_por else None
            ),
        }
        for version in versiones
    ]

    return Response(datos, status=status.HTTP_200_OK)