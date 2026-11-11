
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from core.mixins import (
    es_transversal,
    get_delegaciones_autorizadas_ids,
)
from organizations.models import Delegacion


class SGRConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        usuario = self.scope.get("user")

        if not usuario or not usuario.is_authenticated:
            await self.close(code=4401)
            return

        activo, transversal, delegaciones = await self.obtener_ambito(
            usuario
        )

        if not activo or (not transversal and not delegaciones):
            await self.close(code=4403)
            return

        self.grupos = ["sgr_usuarios_activos"]

        if transversal:
            self.grupos.append("sgr_global")
            self.grupos.extend(
                f"sgr_delegacion_{delegacion_id}"
                for delegacion_id in delegaciones
            )
        else:
            self.grupos.extend(
                f"sgr_delegacion_{delegacion_id}"
                for delegacion_id in delegaciones
            )

        for grupo in set(self.grupos):
            await self.channel_layer.group_add(
                grupo,
                self.channel_name,
            )

        await self.accept()

    async def disconnect(self, close_code):
        for grupo in getattr(self, "grupos", []):
            await self.channel_layer.group_discard(
                grupo,
                self.channel_name,
            )

    async def crud_event(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def obtener_ambito(self, usuario):
        activo = usuario.is_active

        if not activo:
            return False, False, []

        transversal = es_transversal(usuario)

        if transversal:
            delegaciones = list(
                Delegacion.objects.values_list(
                    "pk",
                    flat=True,
                )
            )
        else:
            delegaciones = [
                delegacion_id
                for delegacion_id in get_delegaciones_autorizadas_ids(
                    usuario
                )
                if delegacion_id is not None
            ]

        return activo, transversal, delegaciones
