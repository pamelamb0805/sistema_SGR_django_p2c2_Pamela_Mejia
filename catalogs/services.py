"""Servicios de catalogs (equivale a CRUDCatalogo del diagrama de clases)."""
from core.exceptions import ReglaNegocioError
from core.services import guardar

from .models import Catalogo


class CRUDCatalogo:
    @staticmethod
    def crear_elemento_catalogo(elemento, actor=None):
        return guardar(elemento, actor, "catalogo")

    @staticmethod
    def mostrar_catalogo_por_area(area, tipo=None):
        """Elementos activos aplicables al área (incluye los de área General)."""
        return Catalogo.objects.disponibles(area=area, tipo=tipo)

    @staticmethod
    def modificar_elemento_catalogo(elemento, actor=None):
        """
        No altera registros históricos: si el elemento ya está en uso,
        no se permite cambiar su tipo ni su área (desactívelo y cree uno nuevo).
        """
        original = Catalogo.objects.get(pk=elemento.pk)
        if original.en_uso() and (original.tipo_catalogo != elemento.tipo_catalogo
                                  or original.area != elemento.area):
            raise ReglaNegocioError(
                "El elemento ya está en uso: no se puede cambiar su tipo ni su área. "
                "Desactívelo y cree uno nuevo.")
        return guardar(elemento, actor, "catalogo")

    @staticmethod
    def desactivar_elemento_catalogo(elemento, actor=None):
        elemento.estado = Catalogo.ESTADO_INACTIVO
        return guardar(elemento, actor, "catalogo")

    @staticmethod
    def activar_elemento_catalogo(elemento, actor=None):
        elemento.estado = Catalogo.ESTADO_ACTIVO
        return guardar(elemento, actor, "catalogo")
