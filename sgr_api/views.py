
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import Delegacion
from organizations.services import CRUDDelegacion

from core.exceptions import ReglaNegocioError
from core.mixins import (
    filtrar_por_ambito,
    tiene_permiso,
    tiene_rol,
    ROLES_SUPERVISION,
    ROLES_CONFIGURACION,
)

from .serializers import DelegacionSerializer


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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def delegacion_list(request):

    if request.method == "GET":

        if not _puede_consultar(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar delegaciones."},
                status=status.HTTP_403_FORBIDDEN,
            )

        delegaciones = _delegaciones_autorizadas(request.user)

        serializer = DelegacionSerializer(
            delegaciones,
            many=True,
        )

        return Response(serializer.data)

    if not _puede_editar(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar delegaciones."},
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


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def delegacion_detail(request, pk):

    delegacion = _delegaciones_autorizadas(
        request.user
    ).filter(
        id_delegacion=pk
    ).first()

    if delegacion is None:
        return Response(
            {"detail": "Delegación no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == "GET":

        if not _puede_consultar(request.user):
            return Response(
                {"detail": "No tienes permiso para consultar delegaciones."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            DelegacionSerializer(delegacion).data
        )

    if not _puede_editar(request.user):
        return Response(
            {"detail": "No tienes permiso para administrar delegaciones."},
            status=status.HTTP_403_FORBIDDEN,
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
