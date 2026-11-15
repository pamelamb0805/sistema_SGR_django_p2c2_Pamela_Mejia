
from datetime import datetime, time

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def inicio_del_dia(fecha):
    fecha_hora = datetime.combine(fecha, time.min)

    return timezone.make_aware(
        fecha_hora,
        timezone.get_current_timezone(),
    )


def inicializar_versiones(apps, schema_editor):
    Meta = apps.get_model("measurement", "Meta")
    Periodo = apps.get_model("measurement", "Periodo")
    MetaVersion = apps.get_model("measurement", "MetaVersion")
    ReglaCalculoVersion = apps.get_model(
        "measurement",
        "ReglaCalculoVersion",
    )

    ItemMedible = apps.get_model(
        "organizations",
        "ItemMedible",
    )
    ItemMedibleVersion = apps.get_model(
        "organizations",
        "ItemMedibleVersion",
    )

    Catalogo = apps.get_model(
        "catalogs",
        "Catalogo",
    )
    CatalogoVersion = apps.get_model(
        "catalogs",
        "CatalogoVersion",
    )

    ahora = timezone.now()

    # ---------------------------------------------------------
    # VERSIONES INICIALES DE ÍTEMS MEDIBLES
    # ---------------------------------------------------------

    for item in ItemMedible.objects.select_related(
        "cargo"
    ).iterator():

        existe = ItemMedibleVersion.objects.filter(
            objeto_id=item.pk
        ).exists()

        if existe:
            continue

        primera_fecha = (
            Meta.objects.filter(
                item_id=item.pk
            )
            .order_by("periodo__fecha_inicio")
            .values_list(
                "periodo__fecha_inicio",
                flat=True,
            )
            .first()
        )

        vigente_desde = (
            inicio_del_dia(primera_fecha)
            if primera_fecha
            else ahora
        )

        ItemMedibleVersion.objects.create(
            objeto_id=item.pk,
            numero_version=1,
            vigente_desde=vigente_desde,
            datos={
                "codigo": item.codigo,
                "nombre_item": item.nombre_item,
                "descripcion": item.descripcion,
                "tipo": item.tipo,
                "vigencia": item.vigencia,
                "cargo_id": item.cargo_id,
                "cargo_nombre": item.cargo.nombre_cargo,
            },
        )

    # ---------------------------------------------------------
    # VERSIONES INICIALES DE CATÁLOGOS
    # ---------------------------------------------------------

    for elemento in Catalogo.objects.select_related(
        "tipo_atencion_padre"
    ).iterator():

        existe = CatalogoVersion.objects.filter(
            objeto_id=elemento.pk
        ).exists()

        if existe:
            continue

        CatalogoVersion.objects.create(
            objeto_id=elemento.pk,
            numero_version=1,
            vigente_desde=ahora,
            datos={
                "codigo": elemento.codigo,
                "tipo_catalogo": elemento.tipo_catalogo,
                "nombre": elemento.nombre,
                "descripcion": elemento.descripcion,
                "tipo_atencion_padre_id": (
                    elemento.tipo_atencion_padre_id
                ),
                "tipo_atencion_padre_nombre": (
                    elemento.tipo_atencion_padre.nombre
                    if elemento.tipo_atencion_padre_id
                    else None
                ),
                "area": elemento.area,
                "estado": elemento.estado,
            },
        )

    # ---------------------------------------------------------
    # VERSIONES INICIALES DE METAS Y PONDERACIONES
    # ---------------------------------------------------------

    for meta in Meta.objects.select_related(
        "item",
        "periodo",
    ).iterator():

        existe = MetaVersion.objects.filter(
            objeto_id=meta.pk
        ).exists()

        if existe:
            continue

        MetaVersion.objects.create(
            meta_id=meta.pk,
            objeto_id=meta.pk,
            numero_version=1,
            vigente_desde=inicio_del_dia(
                meta.periodo.fecha_inicio
            ),
            datos={
                "valor_objetivo": str(meta.valor_objetivo),
                "unidad": meta.unidad,
                "ponderador": str(meta.ponderador),
                "umbral_minimo": str(meta.umbral_minimo),
                "maximo_computable": str(
                    meta.maximo_computable
                ),
                "item_id": meta.item_id,
                "funcionario_id": meta.funcionario_id,
                "periodo_id": meta.periodo_id,
                "cargo_id": meta.cargo_id,
                "item_codigo": meta.item.codigo,
                "item_nombre": meta.item.nombre_item,
                "item_descripcion": meta.item.descripcion,
                "item_tipo": meta.item.tipo,
            },
        )

    # ---------------------------------------------------------
    # VERSIONES INICIALES DE REGLAS POR PERÍODO
    # ---------------------------------------------------------

    for periodo in Periodo.objects.all().iterator():

        existe = ReglaCalculoVersion.objects.filter(
            periodo_id=periodo.pk
        ).exists()

        if existe:
            continue

        ReglaCalculoVersion.objects.create(
            periodo_id=periodo.pk,
            numero_version=max(
                1,
                periodo.version_parametros or 1,
            ),
            vigente_desde=inicio_del_dia(
                periodo.fecha_inicio
            ),
            datos={
                "tope_cumplimiento": str(
                    settings.SGR_TOPE_CUMPLIMIENTO
                ),
                "umbral_colectivo": str(
                    settings.SGR_UMBRAL_COLECTIVO
                ),
                "umbral_ambar": str(
                    settings.SGR_SEMAFORO_AMBAR
                ),
                "suma_ponderadores": str(
                    settings.SGR_SUMA_PONDERADORES
                ),
                "version_formula_cumplimiento": 1,
                "version_formula_ponderacion": 1,
                "version_formula_meta_esperada": 1,
                "version_formula_semaforo": 1,
                "version_formula_dias": 1,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("measurement", "0003_reglacalculoversion"),
        ("organizations", "0003_itemmedibleversion"),
        ("catalogs", "0002_catalogoversion"),
    ]

    operations = [
        migrations.RunPython(
            inicializar_versiones,
            migrations.RunPython.noop,
        ),
    ]
