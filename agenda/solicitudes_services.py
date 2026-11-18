import re
import unicodedata
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from core.mixins import get_funcionario, tiene_rol, es_transversal
from organizations.models import Funcionario
from social.models import UsuarioSocial
from .models import Compromiso, HistorialTransiciones


def normalizar_rut(valor):
    valor = re.sub(r"[^0-9kK]", "", str(valor or "")).upper()
    if len(valor) < 2:
        return ""
    return f"{valor[:-1]}-{valor[-1]}"


def rut_valido(valor):
    rut = re.sub(r"[^0-9kK]", "", str(valor or "")).upper()
    if len(rut) < 2 or not rut[:-1].isdigit():
        return False
    cuerpo, dv = rut[:-1], rut[-1]
    suma, factor = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    esperado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    return dv == esperado


def tutor_registrado(rut):
    return UsuarioSocial.objects.filter(rut=normalizar_rut(rut)).select_related("delegacion").first()


def funcionario_responsable(delegacion):
    base = Funcionario.objects.filter(delegacion=delegacion, estado=Funcionario.ESTADO_ACTIVO)
    delegado = base.filter(funcionario_roles__rol__nombre_rol="Delegado").distinct().first()
    return delegado or base.order_by("id_funcionario").first()


def crear_solicitud(data):
    tipo = data["tipo_solicitud"]
    tutor = None
    delegacion = data["delegacion"]
    rut_menor = None
    nombre_menor = ""
    nombre_solicitante = data["nombre_solicitante"].strip()
    territorio = data["territorio"].strip()
    categoria = data["categoria_solicitud"]
    if tipo == Compromiso.TIPO_REGALO:
        tutor = tutor_registrado(data["rut_solicitante"])
        if tutor is None:
            raise ValueError("El adulto/tutor debe existir en el registro social antes de solicitar el regalo.")
        delegacion = tutor.delegacion
        nombre_solicitante = tutor.nombre
        territorio = tutor.territorio
        categoria = "Social"
        rut_menor = normalizar_rut(data["rut_menor"])
        nombre_menor = data["nombre_menor"].strip()
    responsable = funcionario_responsable(delegacion)
    if responsable is None:
        raise ValueError("La delegación seleccionada no tiene funcionarios activos para recibir la solicitud.")
    fecha_propuesta = data.get("fecha_propuesta_solucion")
    with transaction.atomic():
        compromiso = Compromiso(
            origen="Solicitud vecinal",
            solicitante=nombre_solicitante,
            territorio=territorio,
            fecha_comprometida=fecha_propuesta or (timezone.localdate() + timedelta(days=30)),
            area_apoyo=categoria,
            estado=Compromiso.ESTADO_INGRESADO,
            observacion=data["descripcion_solicitud"].strip(),
            funcionario=responsable,
            delegacion=delegacion,
            rut_solicitante=normalizar_rut(data["rut_solicitante"]),
            relacion_vecinal=data["relacion_vecinal"],
            canal_solicitud=Compromiso.CANAL_PRESENCIAL,
            tipo_solicitud=tipo,
            categoria_solicitud=categoria,
            descripcion_solicitud=data["descripcion_solicitud"].strip(),
            estado_solicitud=Compromiso.ESTADO_SOLICITUD_CREADO,
            fecha_propuesta_solucion=fecha_propuesta,
            rut_menor=rut_menor,
            nombre_menor=nombre_menor,
        )
        compromiso.full_clean()
        compromiso.save()
        HistorialTransiciones.objects.create(
            compromiso=compromiso,
            funcionario=responsable,
            estado_anterior="",
            estado_nuevo=Compromiso.ESTADO_SOLICITUD_CREADO,
            observacion="Solicitud vecinal ingresada públicamente. Canal: Presencial.",
        )
    return compromiso


def solicitudes_visibles(user):
    funcionario = get_funcionario(user)
    qs = Compromiso.objects.filter(tipo_solicitud__in=[Compromiso.TIPO_GENERAL, Compromiso.TIPO_REGALO]).select_related("delegacion", "funcionario")
    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if getattr(user, "is_superuser", False):
        return qs
    if funcionario is None or not funcionario.activo:
        return qs.none()
    roles = set(funcionario.roles.values_list("nombre_rol", flat=True))
    cargo = unicodedata.normalize("NFKD", funcionario.cargo.nombre_cargo).encode("ascii", "ignore").decode().lower()
    # El Delegado siempre queda acotado a su delegación, incluso si otro rol
    # asociado al usuario tiene alcance transversal.
    if "Delegado" in roles:
        return qs.filter(delegacion_id=funcionario.delegacion_id)
    if es_transversal(user):
        return qs
    qs = qs.filter(delegacion_id=funcionario.delegacion_id)
    if "Administrador" in roles or "Coordinador" in roles:
        return qs
    if "gestor social" in cargo:
        return qs.filter(Q(categoria_solicitud__icontains="social") | Q(funcionario=funcionario))
    if "organizaciones comunitarias" in cargo:
        return qs.filter(categoria_solicitud__icontains="organizacion")
    if "coordinador de servicios comunitarios" in cargo:
        return qs.filter(Q(categoria_solicitud__icontains="aseo") | Q(categoria_solicitud__icontains="ornato") | Q(categoria_solicitud__icontains="espacios") | Q(categoria_solicitud__icontains="servicios comunitarios"))
    if "apoyo administrativo" in cargo or "gestion y planificacion" in cargo:
        return qs
    return qs.none()


def puede_gestionar_solicitud(user, solicitud):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    funcionario = get_funcionario(user)
    if funcionario is None or not funcionario.activo:
        return False
    if funcionario.delegacion_id != solicitud.delegacion_id and not es_transversal(user):
        return False
    if funcionario.pk == solicitud.funcionario_id:
        return True
    roles = set(funcionario.roles.values_list("nombre_rol", flat=True))
    if roles.intersection({"Administrador", "Coordinador", "Delegado"}):
        return True
    cargo = unicodedata.normalize("NFKD", funcionario.cargo.nombre_cargo).encode("ascii", "ignore").decode().lower()
    categoria = (solicitud.categoria_solicitud or "").lower()
    if "gestor social" in cargo:
        return "social" in categoria
    if "organizaciones comunitarias" in cargo:
        return "organizacion" in categoria
    if "coordinador de servicios comunitarios" in cargo:
        return any(x in categoria for x in ("aseo", "ornato", "espacios", "servicios comunitarios"))
    return False


def cambiar_estado(compromiso, nuevo_estado, actor, observacion=""):
    permitidos = dict(Compromiso.ESTADOS_SOLICITUD)
    if nuevo_estado not in permitidos:
        raise ValueError("Estado de solicitud no válido.")
    transiciones = {
        Compromiso.ESTADO_SOLICITUD_CREADO: {Compromiso.ESTADO_SOLICITUD_PENDIENTE},
        Compromiso.ESTADO_SOLICITUD_PENDIENTE: {Compromiso.ESTADO_SOLICITUD_PROCESO},
        Compromiso.ESTADO_SOLICITUD_PROCESO: {Compromiso.ESTADO_SOLICITUD_PENDIENTE, Compromiso.ESTADO_SOLICITUD_CONCLUIDO},
        Compromiso.ESTADO_SOLICITUD_CONCLUIDO: set(),
    }
    with transaction.atomic():
        compromiso = Compromiso.objects.select_for_update().get(pk=compromiso.pk)
        anterior = compromiso.estado_solicitud
        if nuevo_estado != anterior and nuevo_estado not in transiciones.get(anterior, set()):
            raise ValueError("La transición de estado solicitada no está permitida.")
        compromiso.estado_solicitud = nuevo_estado
        compromiso.save(update_fields=["estado_solicitud"])
        funcionario = get_funcionario(actor)
        if funcionario is None:
            raise ValueError("No se pudo identificar al funcionario que realiza el cambio.")
        HistorialTransiciones.objects.create(compromiso=compromiso, funcionario=funcionario, estado_anterior=anterior, estado_nuevo=nuevo_estado, observacion=(observacion or "Cambio de estado").strip())
    return compromiso


def agregar_evento(compromiso, actor, observacion):
    funcionario = get_funcionario(actor)
    if funcionario is None or not observacion.strip():
        raise ValueError("El evento y el funcionario responsable son obligatorios.")
    return HistorialTransiciones.objects.create(compromiso=compromiso, funcionario=funcionario, estado_anterior=compromiso.estado_solicitud, estado_nuevo=compromiso.estado_solicitud, observacion=observacion.strip())
