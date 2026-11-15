
"""Servicios de catalogs (equivale a CRUDCatalogo del diagrama de clases)."""

from django.db import transaction
from django.utils import timezone

from core.exceptions import ReglaNegocioError
from core.services import guardar

from .models import Catalogo, CatalogoVersion


class CRUDCatalogo:

    @staticmethod
    def _datos_version(elemento):
        return {
            "codigo": elemento.codigo,
            "tipo_catalogo": elemento.tipo_catalogo,
            "nombre": elemento.nombre,
            "descripcion": elemento.descripcion,
            "tipo_atencion_padre_id": elemento.tipo_atencion_padre_id,
            "tipo_atencion_padre_nombre": (
                elemento.tipo_atencion_padre.nombre
                if elemento.tipo_atencion_padre_id
                else None
            ),
            "area": elemento.area,
            "estado": elemento.estado,
        }

    @staticmethod
    def _registrar_version(elemento, actor=None):
        ultima = (
            CatalogoVersion.objects
            .select_for_update()
            .filter(objeto_id=elemento.pk)
            .order_by("-numero_version")
            .first()
        )

        ahora = timezone.now()

        if ultima:
            ultima.vigente_hasta = ahora
            ultima.save(update_fields=["vigente_hasta"])
            numero = ultima.numero_version + 1
        else:
            numero = 1

        CatalogoVersion.objects.create(
            objeto_id=elemento.pk,
            numero_version=numero,
            vigente_desde=ahora,
            datos=CRUDCatalogo._datos_version(elemento),
            creado_por=(
                actor
                if getattr(actor, "is_authenticated", False)
                else None
            ),
        )

    @staticmethod
    def _crear_version_base_si_no_existe(elemento, actor=None):
        """
        Conserva los datos anteriores de catálogos que ya existían
        antes de implementar el versionamiento.
        """
        existe = CatalogoVersion.objects.filter(
            objeto_id=elemento.pk
        ).exists()

        if existe:
            return

        ahora = timezone.now()

        CatalogoVersion.objects.create(
            objeto_id=elemento.pk,
            numero_version=1,
            vigente_desde=ahora,
            vigente_hasta=ahora,
            datos=CRUDCatalogo._datos_version(elemento),
            creado_por=(
                actor
                if getattr(actor, "is_authenticated", False)
                else None
            ),
        )

    @staticmethod
    def crear_elemento_catalogo(elemento, actor=None):
        with transaction.atomic():
            elemento = guardar(
                elemento,
                actor,
                "catalogo",
            )

            CRUDCatalogo._registrar_version(
                elemento,
                actor,
            )

        return elemento

    @staticmethod
    def mostrar_catalogo_por_area(area, tipo=None):
        return Catalogo.objects.disponibles(
            area=area,
            tipo=tipo,
        )

    @staticmethod
    def modificar_elemento_catalogo(elemento, actor=None):
        with transaction.atomic():
            original = (
                Catalogo.objects
                .select_for_update()
                .get(pk=elemento.pk)
            )

            if (
                original.en_uso()
                and (
                    original.tipo_catalogo != elemento.tipo_catalogo
                    or original.area.casefold()
                    != elemento.area.casefold()
                )
            ):
                raise ReglaNegocioError(
                    "El elemento ya está en uso: no se puede cambiar "
                    "su tipo ni su área. Desactívelo y cree uno nuevo."
                )

            # Si es un catálogo antiguo sin versiones, primero se
            # conserva su estado anterior.
            CRUDCatalogo._crear_version_base_si_no_existe(
                original,
                actor,
            )

            elemento = guardar(
                elemento,
                actor,
                "catalogo",
            )

            CRUDCatalogo._registrar_version(
                elemento,
                actor,
            )

        return elemento

    @staticmethod
    def desactivar_elemento_catalogo(elemento, actor=None):
        with transaction.atomic():
            elemento = (
                Catalogo.objects
                .select_for_update()
                .get(pk=elemento.pk)
            )

            if not elemento.activo:
                return elemento

            CRUDCatalogo._crear_version_base_si_no_existe(
                elemento,
                actor,
            )

            elemento.estado = Catalogo.ESTADO_INACTIVO

            elemento = guardar(
                elemento,
                actor,
                "catalogo",
            )

            CRUDCatalogo._registrar_version(
                elemento,
                actor,
            )

        return elemento

    @staticmethod
    def activar_elemento_catalogo(elemento, actor=None):
        with transaction.atomic():
            elemento = (
                Catalogo.objects
                .select_for_update()
                .get(pk=elemento.pk)
            )

            if elemento.activo:
                return elemento

            CRUDCatalogo._crear_version_base_si_no_existe(
                elemento,
                actor,
            )

            elemento.estado = Catalogo.ESTADO_ACTIVO

            elemento = guardar(
                elemento,
                actor,
                "catalogo",
            )

            CRUDCatalogo._registrar_version(
                elemento,
                actor,
            )

        return elemento