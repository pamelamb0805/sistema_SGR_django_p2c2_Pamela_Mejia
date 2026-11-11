
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from core.mixins import (
    es_transversal,
    get_delegaciones_autorizadas_ids,
)


class SGRConsumer(AsyncJsonWebsocketConsumer):
    """
    Conexión WebSocket del SGR.

    Cada usuario recibe eventos únicamente de las delegaciones
    correspondientes a su ámbito autorizado.
    """

    async def connect(self):
        usuario = self.scope.get("user")

        if not usuario or not usuario.is_authenticated:
            await self.close(code=4401)
            return

        activo, transversal, delegaciones = await self.obtener_ambito(usuario)

        if not activo or (not transversal and not delegaciones):
            await self.close(code=4403)
            return

        self.grupos = []

        if transversal:
            self.grupos.append("sgr_global")
        else:
            self.grupos.extend(
                f"sgr_delegacion_{delegacion_id}"
                for delegacion_id in delegaciones
            )

        for grupo in self.grupos:
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

    async def sgr_evento(self, event):
        await self.send_json(event["datos"])

    @database_sync_to_async
    def obtener_ambito(self, usuario):
        activo = usuario.is_active

        if not activo:
            return False, False, []

        transversal = es_transversal(usuario)

        delegaciones = [
            delegacion_id
            for delegacion_id in get_delegaciones_autorizadas_ids(usuario)
            if delegacion_id is not None
        ]

        return activo, transversal, delegaciones
