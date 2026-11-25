
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

from core.mixins import (
    es_transversal,
    get_delegaciones_autorizadas_ids,
    get_permisos,
)
from organizations.models import Delegacion


# Un usuario solo recibe eventos de módulos que puede consultar.
# Se usa cualquier permiso de lectura aplicable al módulo.
PERMISOS_LECTURA_MODULO = {
    "organizations": {
        "delegaciones.ver",
        "cargos.ver",
        "items.ver",
        "roles.ver",
        "funcionarios.ver",
        "usuarios.ver",
    },
    "catalogs": {
        "catalogos.ver",
    },
    "measurement": {
        "periodos.ver",
        "metas.ver",
        "ajustes.ver",
        "indicadores.ver",
    },
    "activities": {
        "actividades.ver",
        "evidencias.ver",
        "validaciones.ver",
    },
    "agenda": {
        "agenda.ver",
    },
    "social": {
        "atenciones.ver",
    },
}



class SGRConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        # Inicializar siempre los atributos antes de cualquier validación.
        self.permisos = set()
        self.delegaciones_autorizadas = set()
        self.transversal = False
        self.grupos = []

        usuario = self.scope.get("user")

        if not usuario or not usuario.is_authenticated:
            await self.close(code=4401)
            return

        datos = await self.obtener_ambito(usuario)

        if not datos["activo"]:
            await self.close(code=4403)
            return

        self.transversal = datos["transversal"]
        self.delegaciones_autorizadas = set(datos["delegaciones"])
        self.permisos = set(datos["permisos"])

        if not self.transversal and not self.delegaciones_autorizadas:
            await self.close(code=4403)
            return

        if not self.permisos:
            await self.close(code=4403)
            return

        self.grupos = ["sgr_usuarios_activos"]

        if self.transversal:
            self.grupos.append("sgr_global")

        self.grupos.extend(
            f"sgr_delegacion_{delegacion_id}"
            for delegacion_id in self.delegaciones_autorizadas
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

        if await self.puede_recibir_evento(payload):
            await self.send_json(payload)

    @database_sync_to_async
    def obtener_ambito(self, usuario):
        if not usuario.is_active:
            return {
                "activo": False,
                "transversal": False,
                "delegaciones": [],
                "permisos": [],
            }

        funcionario = getattr(usuario, "funcionario", None)

        if funcionario is not None and not funcionario.activo:
            return {
                "activo": False,
                "transversal": False,
                "delegaciones": [],
                "permisos": [],
            }

        transversal = es_transversal(usuario)

        if transversal:
            delegaciones = list(
                Delegacion.objects.values_list("pk", flat=True)
            )
        else:
            delegaciones = [
                delegacion_id
                for delegacion_id in get_delegaciones_autorizadas_ids(usuario)
                if delegacion_id is not None
            ]

        return {
            "activo": True,
            "transversal": transversal,
            "delegaciones": delegaciones,
            "permisos": list(get_permisos(usuario)),
        }

    async def puede_recibir_evento(self, payload):
        modulo = payload.get("module", "")
        delegacion_id = payload.get("delegacion_id")

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

        permisos_requeridos = PERMISOS_LECTURA_MODULO.get(modulo)

        if not permisos_requeridos:
            return False

        if "*" in self.permisos:
            return True

        return bool(
            self.permisos.intersection(permisos_requeridos)
        )
