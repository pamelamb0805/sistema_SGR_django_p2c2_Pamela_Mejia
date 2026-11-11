
"""
Consumer de notificaciones CRUD del SGR.

No recibe mensajes de escritura desde el navegador.
Solo distribuye notificaciones a usuarios autenticados y autorizados.
"""
from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer

from organizations.models import Delegacion
from core.mixins import (
    ROLES_SUPERVISION,
    ROLES_OPERATIVOS,
    ROLES_VALIDACION,
    get_delegaciones_autorizadas_ids,
    es_transversal,
    tiene_rol,
)


ROLES_ACTIVIDADES = (
    ROLES_SUPERVISION
    + ROLES_OPERATIVOS
    + ROLES_VALIDACION
)

ROLES_AGENDA = ROLES_SUPERVISION + ROLES_OPERATIVOS

ROLES_POR_MODULO = {
    "organizations": ROLES_SUPERVISION,
    "catalogs": ROLES_SUPERVISION,
    "measurement": ROLES_SUPERVISION,
    "activities": ROLES_ACTIVIDADES,
    "agenda": ROLES_AGENDA,
    "social": ROLES_SUPERVISION + ROLES_OPERATIVOS,
}


class SGRCrudConsumer(JsonWebsocketConsumer):
    """
    Canal de notificaciones CRUD del SGR.

    Grupos:
    - sgr_global: cambios de entidades globales.
    - sgr_delegacion_ID: cambios correspondientes a una delegación.
    """

    def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated or not user.is_active:
            self.close()
            return

        self.grupos = set()

        # Los usuarios de supervisión pueden recibir cambios globales.
        if tiene_rol(user, *ROLES_SUPERVISION):
            self.grupos.add("sgr_global")

        # El alcance global permite observar todas las delegaciones.
        if es_transversal(user):
            ids = Delegacion.objects.values_list(
                "pk",
                flat=True,
            )
        else:
            ids = get_delegaciones_autorizadas_ids(user)

        for delegacion_id in ids:
            if delegacion_id:
                self.grupos.add(
                    f"sgr_delegacion_{delegacion_id}"
                )

        if not self.grupos:
            self.close()
            return

        for grupo in self.grupos:
            async_to_sync(self.channel_layer.group_add)(
                grupo,
                self.channel_name,
            )

        self.accept()

    def disconnect(self, close_code):
        for grupo in getattr(self, "grupos", set()):
            async_to_sync(self.channel_layer.group_discard)(
                grupo,
                self.channel_name,
            )

    def crud_event(self, event):
        """
        Recibe una notificación publicada por el servidor.
        Comprueba nuevamente el rol antes de enviarla al navegador.
        """
        user = self.scope.get("user")
        modulo = event.get("module")

        roles_permitidos = ROLES_POR_MODULO.get(modulo, ())

        if not user or not tiene_rol(user, *roles_permitidos):
            return

        self.send_json(event.get("payload", {}))
