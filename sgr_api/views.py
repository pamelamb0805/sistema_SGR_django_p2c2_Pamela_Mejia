
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import Delegacion, Rol, Funcionario
from organizations.services import (
    CRUDDelegacion,
    CRUDRol,
    CRUDFuncionario,
)

from core.exceptions import ReglaNegocioError
from core.mixins import (
    filtrar_por_ambito,
    tiene_permiso,
    tiene_rol,
    ROLES_SUPERVISION,
    ROLES_CONFIGURACION,
)

from .serializers import DelegacionSerializer, RolSerializer


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
