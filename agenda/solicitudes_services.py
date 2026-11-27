
import re
import unicodedata

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.mixins import (
    get_funcionario,
    es_transversal,
)
from organizations.models import Funcionario
from social.models import UsuarioSocial

from .models import (
    Compromiso,
    SolicitudVecinal,
    HistorialTransiciones,
)
from datetime import timedelta

def normalizar_rut(valor):
    valor = str(valor or "").strip().upper()

    if not valor or not re.fullmatch(r"[0-9K.\-\s]+", valor):
        return ""

    limpio = re.sub(r"[.\-\s]", "", valor)

    if len(limpio) not in (8, 9):
        return ""

    cuerpo = limpio[:-1]
    dv = limpio[-1]

    if not cuerpo.isdigit() or dv not in "0123456789K":
        return ""

    return f"{cuerpo}-{dv}"


def rut_valido(valor):
    rut = normalizar_rut(valor)

    if not rut:
        return False

    cuerpo, dv = rut.split("-")

    suma = 0
    factor = 2

    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1

    resto = 11 - (suma % 11)

    if resto == 11:
        esperado = "0"
    elif resto == 10:
        esperado = "K"
    else:
        esperado = str(resto)

    return dv == esperado


def tutor_registrado(rut):
    return (
        UsuarioSocial.objects
        .filter(rut=normalizar_rut(rut))
        .select_related("delegacion")
        .first()
    )


def funcionario_responsable(delegacion):
    funcionarios = Funcionario.objects.filter(
        delegacion=delegacion,
        estado=Funcionario.ESTADO_ACTIVO,
    )

    delegado = (
        funcionarios
        .filter(funcionario_roles__rol__nombre_rol="Delegado")
        .distinct()
        .first()
    )

    return delegado or funcionarios.order_by(
        "id_funcionario"
    ).first()


def crear_solicitud(data):
    tipo = data["tipo_solicitud"]
    delegacion = data.get("delegacion")
    rut_solicitante = normalizar_rut(
        data.get("rut_solicitante")
    )

    nombre_solicitante = (
        data.get("nombre_solicitante") or ""
    ).strip()

    territorio = (
        data.get("territorio") or ""
    ).strip()

    categoria = data["categoria_solicitud"]
    rut_menor = None
    nombre_menor = ""

    if tipo == SolicitudVecinal.TIPO_REGALO:
        tutor = tutor_registrado(rut_solicitante)

        if tutor is None:
            raise ValueError(
                "El adulto/tutor debe existir en el registro "
                "social antes de solicitar el regalo."
            )

        delegacion = tutor.delegacion
        nombre_solicitante = tutor.nombre
        territorio = tutor.territorio
        categoria = "Social"

        rut_menor = normalizar_rut(
            data.get("rut_menor")
        )
        nombre_menor = (
            data.get("nombre_menor") or ""
        ).strip()

    if delegacion is None:
        raise ValueError(
            "Debe seleccionar una delegación municipal."
        )

    responsable = funcionario_responsable(delegacion)

    if responsable is None:
        raise ValueError(
            "La delegación seleccionada no tiene funcionarios "
            "activos para recibir la solicitud."
        )

    fecha_propuesta = data.get(
        "fecha_propuesta_solucion"
    )

    descripcion = (
        data["descripcion_solicitud"] or ""
    ).strip()

    with transaction.atomic():
        solicitud = SolicitudVecinal(
            rut_solicitante=rut_solicitante,
            relacion_vecinal=data["relacion_vecinal"],
            canal=SolicitudVecinal.CANAL_PRESENCIAL,
            tipo=tipo,
            categoria=categoria,
            descripcion=descripcion,
            estado_solicitud=SolicitudVecinal.ESTADO_CREADO,
            fecha_propuesta_solucion=fecha_propuesta,
            rut_menor=rut_menor,
            nombre_menor=nombre_menor,
        )

        solicitud.full_clean()
        solicitud.save()

        from measurement.models import Periodo

        fecha_comprometida = (
            fecha_propuesta
            or timezone.localdate() + timedelta(days=30)
        )

        compromiso = Compromiso(
            origen="Solicitud vecinal",
            solicitante=nombre_solicitante,
            territorio=territorio,
            fecha_comprometida=fecha_comprometida,
            area_apoyo=categoria,
            estado=Compromiso.ESTADO_INGRESADO,
            observacion=descripcion,
            funcionario=responsable,
            delegacion=delegacion,
            periodo=Periodo.objects.para_fecha(
                fecha_comprometida
            ),
            solicitud_vecinal=solicitud,
        )

        compromiso.full_clean()
        compromiso.save()

    return solicitud


def solicitudes_visibles(user):
    if not getattr(user, "is_authenticated", False):
        return SolicitudVecinal.objects.none()

    qs = (
        SolicitudVecinal.objects
        .filter(compromisos__isnull=False)
        .prefetch_related(
            "compromisos__funcionario",
            "compromisos__delegacion",
            "compromisos__item_medible",
            "compromisos__periodo",
        )
        .distinct()
    )

    if getattr(user, "is_superuser", False):
        return qs

    funcionario = get_funcionario(user)

    if funcionario is None or not funcionario.activo:
        return qs.none()

    roles = set(
        funcionario.roles.values_list(
            "nombre_rol",
            flat=True,
        )
    )

    cargo_nombre = (
        funcionario.cargo.nombre_cargo
        if funcionario.cargo_id
        else ""
    )

    cargo = (
        unicodedata.normalize("NFKD", cargo_nombre)
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )

    if "Delegado" in roles:
        return qs.filter(
            compromisos__delegacion_id=funcionario.delegacion_id
        ).distinct()

    if es_transversal(user):
        return qs

    qs = qs.filter(
        compromisos__delegacion_id=funcionario.delegacion_id
    )

    if roles.intersection({"Administrador", "Coordinador"}):
        return qs.distinct()

    if "gestor social" in cargo:
        return qs.filter(
            Q(categoria__icontains="social")
            | Q(compromisos__funcionario=funcionario)
        ).distinct()

    if "organizaciones comunitarias" in cargo:
        return qs.filter(
            categoria__icontains="organizacion"
        ).distinct()

    if "coordinador de servicios comunitarios" in cargo:
        return qs.filter(
            Q(categoria__icontains="aseo")
            | Q(categoria__icontains="ornato")
            | Q(categoria__icontains="espacios")
            | Q(categoria__icontains="servicios comunitarios")
        ).distinct()

    if (
        "apoyo administrativo" in cargo
        or "gestion y planificacion" in cargo
    ):
        return qs.distinct()

    return qs.none()


def puede_gestionar_solicitud(user, solicitud):
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    funcionario = get_funcionario(user)

    if funcionario is None or not funcionario.activo:
        return False

    compromisos = solicitud.compromisos.all()

    if not es_transversal(user):
        compromisos = compromisos.filter(
            delegacion_id=funcionario.delegacion_id
        )

    if not compromisos.exists():
        return False

    if compromisos.filter(
        funcionario=funcionario
    ).exists():
        return True

    roles = set(
        funcionario.roles.values_list(
            "nombre_rol",
            flat=True,
        )
    )

    if roles.intersection({
        "Administrador",
        "Coordinador",
        "Delegado",
    }):
        return True

    cargo_nombre = (
        funcionario.cargo.nombre_cargo
        if funcionario.cargo_id
        else ""
    )

    cargo = (
        unicodedata.normalize("NFKD", cargo_nombre)
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )

    categoria = (solicitud.categoria or "").lower()

    if "gestor social" in cargo:
        return "social" in categoria

    if "organizaciones comunitarias" in cargo:
        return "organizacion" in categoria

    if "coordinador de servicios comunitarios" in cargo:
        return any(
            palabra in categoria
            for palabra in (
                "aseo",
                "ornato",
                "espacios",
                "servicios comunitarios",
            )
        )

    return False


def cambiar_estado(
    solicitud,
    nuevo_estado,
    actor,
    observacion="",
):
    transiciones = {
        SolicitudVecinal.ESTADO_CREADO: {
            SolicitudVecinal.ESTADO_PENDIENTE,
        },
        SolicitudVecinal.ESTADO_PENDIENTE: {
            SolicitudVecinal.ESTADO_PROCESO,
        },
        SolicitudVecinal.ESTADO_PROCESO: {
            SolicitudVecinal.ESTADO_PENDIENTE,
            SolicitudVecinal.ESTADO_CONCLUIDO,
        },
        SolicitudVecinal.ESTADO_CONCLUIDO: set(),
    }

    if nuevo_estado not in dict(SolicitudVecinal.ESTADOS):
        raise ValueError("Estado de solicitud no válido.")

    funcionario = get_funcionario(actor)

    if funcionario is None:
        raise ValueError(
            "No se pudo identificar al funcionario que realiza el cambio."
        )

    with transaction.atomic():
        solicitud = (
            SolicitudVecinal.objects
            .select_for_update()
            .get(pk=solicitud.pk)
        )

        anterior = solicitud.estado_solicitud

        if nuevo_estado == anterior:
            return solicitud

        if nuevo_estado not in transiciones.get(anterior, set()):
            raise ValueError(
                "La transición de estado solicitada no está permitida."
            )

        if (
            nuevo_estado == SolicitudVecinal.ESTADO_CONCLUIDO
            and not (solicitud.solucion or "").strip()
        ):
            raise ValueError(
                "Para concluir la solicitud debe registrar la solución."
            )

        equivalencias = {
            SolicitudVecinal.ESTADO_PENDIENTE:
                Compromiso.ESTADO_PENDIENTE,
            SolicitudVecinal.ESTADO_PROCESO:
                Compromiso.ESTADO_EN_PROCESO,
            SolicitudVecinal.ESTADO_CONCLUIDO:
                Compromiso.ESTADO_REALIZADO,
        }

        estado_compromiso = equivalencias.get(nuevo_estado)

        if estado_compromiso:
            from .services import CRUDCompromiso
            from core.exceptions import ReglaNegocioError

            for compromiso in solicitud.compromisos.select_related(
                "funcionario",
                "delegacion",
                "periodo",
                "item_medible",
            ):
                if compromiso.estado == estado_compromiso:
                    continue

                try:
                    CRUDCompromiso.actualizar_estado(
                        compromiso,
                        estado_compromiso,
                        observacion or (
                            f"Estado actualizado desde la solicitud "
                            f"vecinal #{solicitud.pk}."
                        ),
                        actor,
                        sincronizar_solicitud=False,
                    )
                except ReglaNegocioError as exc:
                    raise ValueError(str(exc)) from exc

        solicitud.estado_solicitud = nuevo_estado
        solicitud.save(update_fields=["estado_solicitud"])

        HistorialTransiciones.objects.create(
            compromiso=solicitud.compromisos.order_by(
                "id_compromiso"
            ).first(),
            funcionario=funcionario,
            estado_anterior=anterior,
            estado_nuevo=nuevo_estado,
            observacion=(
                observacion.strip()
                or "Cambio de estado de solicitud vecinal."
            ),
        )

    return solicitud


def actualizar_datos_solicitud(
    solicitud,
    solucion,
    fecha_propuesta,
    actor,
):
    funcionario = get_funcionario(actor)

    if funcionario is None:
        raise ValueError(
            "No se pudo identificar al funcionario."
        )

    with transaction.atomic():
        solicitud = (
            SolicitudVecinal.objects
            .select_for_update()
            .get(pk=solicitud.pk)
        )

        if solicitud.estado_solicitud == SolicitudVecinal.ESTADO_CONCLUIDO:
            raise ValueError(
                "La solicitud concluida no admite modificaciones."
            )

        solucion_anterior = solicitud.solucion
        fecha_anterior = solicitud.fecha_propuesta_solucion

        solicitud.solucion = (solucion or "").strip()
        solicitud.fecha_propuesta_solucion = fecha_propuesta

        solicitud.save(update_fields=[
            "solucion",
            "fecha_propuesta_solucion",
        ])

        if fecha_propuesta != fecha_anterior:
            from measurement.models import Periodo

            for compromiso in solicitud.compromisos.select_related(
                "periodo"
            ):
                compromiso.fecha_comprometida = (
                    fecha_propuesta or timezone.localdate()
                )
                compromiso.periodo = Periodo.objects.para_fecha(
                    compromiso.fecha_comprometida
                )
                compromiso.save(update_fields=[
                    "fecha_comprometida",
                    "periodo",
                ])

        if (
            solucion_anterior != solicitud.solucion
            or fecha_anterior != fecha_propuesta
        ):
            detalle = (
                "Se actualizaron los datos de la solicitud. "
                f"Solución anterior: {solucion_anterior or 'Sin asignar'}. "
                f"Nueva solución: {solicitud.solucion or 'Sin asignar'}. "
                f"Fecha anterior: {fecha_anterior or 'Sin definir'}. "
                f"Nueva fecha: {fecha_propuesta or 'Sin definir'}."
            )

            agregar_evento(
                solicitud,
                actor,
                detalle,
            )

    return solicitud


def agregar_evento(solicitud, actor, observacion):
    funcionario = get_funcionario(actor)
    observacion = (observacion or "").strip()

    if funcionario is None or not observacion:
        raise ValueError(
            "El evento y el funcionario responsable son obligatorios."
        )

    compromisos = list(
        solicitud.compromisos.all().order_by("id_compromiso")
    )

    if not compromisos:
        raise ValueError(
            "La solicitud no tiene compromisos asociados."
        )

    eventos = []

    for compromiso in compromisos:
        eventos.append(
            HistorialTransiciones.objects.create(
                compromiso=compromiso,
                funcionario=funcionario,
                estado_anterior=compromiso.estado,
                estado_nuevo=compromiso.estado,
                observacion=observacion,
            )
        )

    return eventos[0]
