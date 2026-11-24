
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
)

from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_SUPERVISION,
    ROLES_CONFIGURACION,
    ROLES_MEDICION,
    tiene_rol,
    tiene_permiso,
    filtrar_por_ambito,
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