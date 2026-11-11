
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from core.mixins import (
    es_transversal,
    get_delegaciones_autorizadas_ids,
    get_roles,
    ROL_ADMINISTRADOR,
    ROL_COORDINADOR,
    ROL_DELEGADO,
    ROL_FUNCIONARIO,
    ROL_VERIFICADOR,
)
from organizations.models import Delegacion


class SGRConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        usuario = self.scope.get("user")

        if not usuario or not usuario.is_authenticated:
            await self.close(code=4401)
            return

        datos = await self.obtener_ambito(usuario)

        activo = datos["activo"]
        transversal = datos["transversal"]
        delegaciones = datos["delegaciones"]

        if not activo:
            await self.close(code=4403)
            return

        if not transversal and not delegaciones:
            await self.close(code=4403)
            return

        self.delegaciones_autorizadas = set(delegaciones)
        self.transversal = transversal
        self.roles = set(datos["roles"])

        self.grupos = ["sgr_usuarios_activos"]

        if transversal:
            self.grupos.append("sgr_global")

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
        payload = event.get("payload", {})

        autorizado = await self.puede_recibir_evento(
            payload
        )

        if not autorizado:
            return

        await self.send_json(payload)

    @database_sync_to_async
    def obtener_ambito(self, usuario):
        activo = usuario.is_active

        if not activo:
            return {
                "activo": False,
                "transversal": False,
                "delegaciones": [],
                "roles": [],
            }

        funcionario = getattr(
            usuario,
            "funcionario",
            None,
        )

        if funcionario is not None and not funcionario.activo:
            return {
                "activo": False,
                "transversal": False,
                "delegaciones": [],
                "roles": [],
            }

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

        return {
            "activo": True,
            "transversal": transversal,
            "delegaciones": delegaciones,
            "roles": list(get_roles(usuario)),
        }

    async def puede_recibir_evento(self, payload):
        modulo = payload.get("module", "")
        delegacion_id = payload.get("delegacion_id")

        # Comprobar primero el ámbito territorial.
        if delegacion_id:
            try:
                delegacion_id = int(delegacion_id)
            except (TypeError, ValueError):
                return False

            if (
                not self.transversal
                and delegacion_id not in self.delegaciones_autorizadas
            ):
                return False

        # Eventos sin delegación: solo roles autorizados.
        permisos_modulo = {
            "organizations": {
                ROL_ADMINISTRADOR,
            },
            "catalogs": {
                ROL_ADMINISTRADOR,
            },
            "measurement": {
                ROL_ADMINISTRADOR,
                ROL_COORDINADOR,
            },
            "activities": {
                ROL_ADMINISTRADOR,
                ROL_COORDINADOR,
                ROL_DELEGADO,
                ROL_FUNCIONARIO,
                ROL_VERIFICADOR,
            },
            "agenda": {
                ROL_ADMINISTRADOR,
                ROL_COORDINADOR,
                ROL_DELEGADO,
                ROL_FUNCIONARIO,
            },
            "social": {
                ROL_ADMINISTRADOR,
                ROL_COORDINADOR,
                ROL_DELEGADO,
                ROL_FUNCIONARIO,
            },
        }

        roles_permitidos = permisos_modulo.get(modulo)

        if roles_permitidos is None:
            return False

        return bool(self.roles.intersection(roles_permitidos))
