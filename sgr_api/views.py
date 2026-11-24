
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
    ItemMedibleSerializer,
)


from core.exceptions import ReglaNegocioError
from core.mixins import (
    filtrar_por_ambito,
    tiene_permiso,
    tiene_rol,
    ROLES_SUPERVISION,
    ROLES_CONFIGURACION,
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