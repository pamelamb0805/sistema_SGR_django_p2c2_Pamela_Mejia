from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import Delegacion
from core.mixins import (
    filtrar_por_ambito,
    tiene_permiso,
)

from .serializers import DelegacionSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def delegacion_list(request):
    """
    GET /api/delegaciones/

    Lista las delegaciones visibles para el usuario autenticado.
    """

    if not tiene_permiso(request.user, "delegaciones.ver"):
        return Response(
            {"detail": "No tienes permiso para consultar delegaciones."},
            status=status.HTTP_403_FORBIDDEN,
        )

    delegaciones = filtrar_por_ambito(
        Delegacion.objects.all(),
        request.user,
        campo="id_delegacion",
    )

    serializer = DelegacionSerializer(
        delegaciones,
        many=True,
    )

    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def delegacion_detail(request, pk):
    """
    GET /api/delegaciones/<pk>/

    Consulta una delegación dentro del ámbito autorizado.
    """

    if not tiene_permiso(request.user, "delegaciones.ver"):
        return Response(
            {"detail": "No tienes permiso para consultar delegaciones."},
            status=status.HTTP_403_FORBIDDEN,
        )

    delegaciones = filtrar_por_ambito(
        Delegacion.objects.all(),
        request.user,
        campo="id_delegacion",
    )

    delegacion = delegaciones.filter(
        id_delegacion=pk,
    ).first()

    if delegacion is None:
        return Response(
            {"detail": "Delegación no encontrada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = DelegacionSerializer(delegacion)

    return Response(serializer.data)