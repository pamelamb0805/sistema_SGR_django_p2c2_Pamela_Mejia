import calendar
import hashlib
import secrets
import time
from datetime import date, timedelta

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, render
from django.utils import timezone

from core.mixins import (
    ROLES_SUPERVISION,
    es_transversal,
    filtrar_por_ambito,
    get_funcionario,
    tiene_rol,
)
from organizations.forms import PerfilUsuarioForm

from .auth_forms import (
    NuevaClaveForm,
    RegistroUsuarioForm,
    SGRAuthenticationForm,
    SolicitarCodigoForm,
    VerificarCodigoForm,
)
from .mixins import (
    ROL_VERIFICADOR,
    registrar_auditoria,
)
import hmac

from django.db import transaction

from organizations.models import PasswordResetCode
from core.activity_metrics import construir_resumen_actividad_reciente
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

class SGRLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True
    authentication_form = SGRAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        funcionario = get_funcionario(self.request.user)
        nombre = funcionario.nombre if funcionario else self.request.user.get_username()
        messages.success(self.request, f"Bienvenido/a, {nombre}.")
        registrar_auditoria(self.request, evento="LOGIN", entidad="usuario",
                            id_entidad=self.request.user.pk)
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Usuario o contraseña incorrectos, o usuario inactivo.")
        return super().form_invalid(form)




def _modelo(app_label, nombre):
    """Devuelve el modelo o None si esa app aún no está instalada (desarrollo por etapas)."""
    try:
        return apps.get_model(app_label, nombre)
    except LookupError:
        return None


def construir_alertas_operativas(user, periodo=None, hoy=None):
    """
    Construye alertas operativas respetando los permisos y el ámbito
    territorial del usuario.

    RF-037:
    - Compromisos vencidos y próximos a vencer.
    - Evidencias pendientes de revisión.
    - Ausencia de registros válidos.
    - Avance de metas bajo el umbral configurado.

    Cada alerta incluye motivo, responsable, fecha y enlace al elemento.
    """
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Max
    from django.urls import reverse
    from django.utils import timezone

    from activities.models import Actividad, Evidencia
    from activities.services import evidencias_visibles
    from agenda.models import Compromiso
    from agenda.services import compromisos_visibles
    from measurement.services import CalculoIndicadores
    from organizations.models import Funcionario

    hoy = hoy or timezone.localdate()

    funcionario_actual = get_funcionario(user)
    es_supervisor = tiene_rol(user, *ROLES_SUPERVISION)

    dias_vencimiento = getattr(
        settings,
        "SGR_DIAS_ALERTA_VENCIMIENTO",
        3,
    )

    dias_sin_registro = getattr(
        settings,
        "SGR_DIAS_SIN_REGISTRO_ALERTA",
        7,
    )

    alertas = []

    def agregar_alerta(
        tipo,
        titulo,
        motivo,
        responsable,
        fecha,
        url,
        nivel="warning",
        prioridad=10,
    ):
        alertas.append({
            "tipo": tipo,
            "titulo": titulo,
            "motivo": motivo,
            "responsable": responsable or "Sin responsable",
            "fecha": fecha or hoy,
            "url": url,
            "nivel": nivel,
            "prioridad": prioridad,
        })

    # ---------------------------------------------------------
    # FUNCIONARIOS VISIBLES
    # ---------------------------------------------------------

    funcionarios = filtrar_por_ambito(
        Funcionario.objects.filter(
            estado=Funcionario.ESTADO_ACTIVO,
        ).select_related(
            "delegacion",
            "cargo",
        ),
        user,
        "delegacion_id",
    )

    if not es_supervisor:
        if funcionario_actual:
            funcionarios = funcionarios.filter(
                pk=funcionario_actual.pk,
            )
        else:
            funcionarios = funcionarios.none()

    funcionarios_lista = list(funcionarios)

    # Enlace al detalle del desempeño.
    def url_desempeno(funcionario):
        if es_supervisor:
            return reverse(
                "measurement:desempeno_funcionario",
                args=[funcionario.pk],
            )

        return reverse("measurement:mi_desempeno")

    # ---------------------------------------------------------
    # 1. VENCIMIENTOS
    # ---------------------------------------------------------

    limite = hoy + timedelta(days=dias_vencimiento)

    compromisos = compromisos_visibles(user).exclude(
        estado=Compromiso.ESTADO_REALIZADO,
    )

    if not es_supervisor:
        if funcionario_actual:
            compromisos = compromisos.filter(
                funcionario=funcionario_actual,
            )
        else:
            compromisos = compromisos.none()

    vencidos = compromisos.filter(
        fecha_comprometida__lt=hoy,
    ).select_related(
        "funcionario",
        "delegacion",
    ).order_by(
        "fecha_comprometida",
    )[:15]

    for compromiso in vencidos:
        agregar_alerta(
            tipo="vencimiento",
            titulo="Compromiso vencido",
            motivo=(
                f"El compromiso #{compromiso.pk} venció el "
                f"{compromiso.fecha_comprometida:%d/%m/%Y} "
                "y todavía no está realizado."
            ),
            responsable=compromiso.funcionario.nombre,
            fecha=compromiso.fecha_comprometida,
            url=reverse(
                "agenda:compromiso_detail",
                args=[compromiso.pk],
            ),
            nivel="danger",
            prioridad=1,
        )

    por_vencer = compromisos.filter(
        fecha_comprometida__gte=hoy,
        fecha_comprometida__lte=limite,
    ).select_related(
        "funcionario",
        "delegacion",
    ).order_by(
        "fecha_comprometida",
    )[:15]

    for compromiso in por_vencer:
        agregar_alerta(
            tipo="vencimiento",
            titulo="Compromiso próximo a vencer",
            motivo=(
                f"El compromiso #{compromiso.pk} vence el "
                f"{compromiso.fecha_comprometida:%d/%m/%Y}."
            ),
            responsable=compromiso.funcionario.nombre,
            fecha=compromiso.fecha_comprometida,
            url=reverse(
                "agenda:compromiso_detail",
                args=[compromiso.pk],
            ),
            nivel="warning",
            prioridad=2,
        )

    # ---------------------------------------------------------
    # 2. EVIDENCIAS PENDIENTES
    # ---------------------------------------------------------

    evidencias_pendientes = (
        evidencias_visibles(user)
        .filter(
            estado_revision=Evidencia.ESTADO_PENDIENTE,
        )
        .select_related(
            "actividad",
            "actividad__funcionario",
            "actividad__funcionario__delegacion",
        )
        .order_by("fecha_carga")[:20]
    )

    for evidencia in evidencias_pendientes:
        actividad = evidencia.actividad

        agregar_alerta(
            tipo="evidencia",
            titulo="Evidencia pendiente de revisión",
            motivo=(
                f"La evidencia {evidencia.codigo_evidencia} "
                f"de la actividad {actividad.codigo} "
                "todavía no tiene una decisión de validación."
            ),
            responsable=actividad.funcionario.nombre,
            fecha=evidencia.fecha_carga,
            url=reverse(
                "activities:actividad_detail",
                args=[actividad.pk],
            ),
            nivel="warning",
            prioridad=3,
        )

    # ---------------------------------------------------------
    # 3. AUSENCIA DE REGISTROS VÁLIDOS
    # ---------------------------------------------------------

    if periodo and funcionarios_lista:
        ultimos_registros = (
            Actividad.objects
            .filter(
                funcionario_id__in=[
                    f.pk for f in funcionarios_lista
                ],
                periodo=periodo,
                estado=Actividad.ESTADO_VALIDADA,
                fecha__lte=hoy,
            )
            .values("funcionario_id")
            .annotate(
                ultima_fecha=Max("fecha"),
            )
        )

        fechas_por_funcionario = {
            fila["funcionario_id"]: fila["ultima_fecha"]
            for fila in ultimos_registros
        }

        for responsable in funcionarios_lista:
            ultima_fecha = fechas_por_funcionario.get(
                responsable.pk
            )

            if ultima_fecha:
                dias_ausencia = (
                    hoy - ultima_fecha
                ).days
            else:
                dias_ausencia = (
                    hoy - periodo.fecha_inicio
                ).days

            if dias_ausencia < dias_sin_registro:
                continue

            if ultima_fecha:
                detalle_fecha = (
                    f"Último registro válido: "
                    f"{ultima_fecha:%d/%m/%Y}."
                )
            else:
                detalle_fecha = (
                    "No existen registros válidos "
                    "en el período vigente."
                )

            agregar_alerta(
                tipo="ausencia",
                titulo="Ausencia de registros",
                motivo=(
                    f"{detalle_fecha} Han transcurrido "
                    f"{dias_ausencia} días sin actividad válida."
                ),
                responsable=responsable.nombre,
                fecha=hoy,
                url=url_desempeno(responsable),
                nivel="warning",
                prioridad=4,
            )

    # ---------------------------------------------------------
    # 4. AVANCE BAJO EL UMBRAL DE LA META
    # ---------------------------------------------------------

    if periodo:
        for responsable in funcionarios_lista:
            resumen = CalculoIndicadores.resumen_funcionario(
                responsable,
                periodo,
                hoy,
            )

            for fila in resumen.get("filas", []):
                if not fila.get("bajo_umbral"):
                    continue

                item = fila.get("item")
                meta = fila.get("meta")

                nombre_item = (
                    item.nombre_item
                    if item is not None
                    else "Ítem sin nombre"
                )

                cumplimiento = fila.get("cumplimiento")
                umbral = fila.get("umbral_historico")

                agregar_alerta(
                    tipo="bajo_umbral",
                    titulo="Avance bajo el umbral",
                    motivo=(
                        f"{nombre_item}: cumplimiento "
                        f"{cumplimiento}% frente al umbral "
                        f"mínimo de {umbral}%."
                    ),
                    responsable=responsable.nombre,
                    fecha=hoy,
                    url=url_desempeno(responsable),
                    nivel="danger",
                    prioridad=5,
                )
    
    # Primero se muestran las alertas de mayor prioridad.
    alertas.sort(
        key=lambda alerta: (
            alerta["prioridad"],
            alerta["fecha"],
            alerta["responsable"],
        )
    )

    # RF-037: persistencia individual por usuario.
    from audit.models import AlertaOperativa

    for datos_alerta in alertas[:50]:
        fecha_alerta = datos_alerta["fecha"]

        if hasattr(fecha_alerta, "date"):
            fecha_alerta = fecha_alerta.date()

        # La clave identifica el origen concreto de la alerta.
        identidad = "|".join([
            str(datos_alerta["tipo"]),
            str(datos_alerta["titulo"]),
            str(datos_alerta["responsable"]),
            str(datos_alerta["url"]),
            str(datos_alerta["motivo"]),
        ])

        clave = hashlib.sha256(
            identidad.encode("utf-8")
        ).hexdigest()

        AlertaOperativa.objects.update_or_create(
            usuario=user,
            clave=clave,
            defaults={
                "tipo": datos_alerta["tipo"],
                "titulo": datos_alerta["titulo"],
                "motivo": datos_alerta["motivo"],
                "responsable": datos_alerta["responsable"],
                "fecha": fecha_alerta,
                "url": datos_alerta["url"] or "",
                "nivel": datos_alerta["nivel"],
                "prioridad": datos_alerta["prioridad"],
            },
        )

    # Las alertas pendientes siguen visibles aunque se recargue
    # el dashboard o se cierre y vuelva a iniciar sesión.
    return list(
        AlertaOperativa.objects.filter(
            usuario=user,
            estado=AlertaOperativa.ESTADO_PENDIENTE,
        ).order_by(
            "prioridad",
            "fecha",
            "id_alerta",
        )[:50]
    )



@login_required
def dashboard(request):
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Count
    from django.db.models.functions import TruncMonth

    user = request.user
    hoy = timezone.localdate()
    limite = hoy + timedelta(
        days=getattr(settings, "SGR_DIAS_ALERTA_VENCIMIENTO", 7)
    )

    funcionario = get_funcionario(user)
    es_supervision = tiene_rol(user, *ROLES_SUPERVISION)

    Funcionario = _modelo("organizations", "Funcionario")
    Delegacion = _modelo("organizations", "Delegacion")
    Actividad = _modelo("activities", "Actividad")
    Evidencia = _modelo("activities", "Evidencia")
    Compromiso = _modelo("agenda", "Compromiso")
    Periodo = _modelo("measurement", "Periodo")
    Meta = _modelo("measurement", "Meta")
    Auditoria = _modelo("audit", "Auditoria")

    datos = {
        "periodo": None,
        "resumen_personal": None,
        "resumen_equipo": None,
        "total_funcionarios": 0,
        "total_delegaciones": 0,
        "mis_actividades": 0,
        "evidencias_pendientes": 0,
        "compromisos_vencidos": 0,
        "compromisos_por_vencer": 0,
        "compromisos_por_estado": {},
        "lista_vencidos": [],
        "ultimas_operaciones": [],
        "hay_metas_periodo": False,
        "hay_actividades": False,
        "hay_evidencias": False,
        "hay_compromisos": False,
        "grafico_personal": {"labels": [], "values": []},
        "grafico_semaforo": {
            "labels": ["Verde", "Ámbar", "Rojo"],
            "values": [0, 0, 0],
        },
        "grafico_delegaciones": {"labels": [], "values": []},
        "grafico_agenda": {"labels": [], "values": []},
        "grafico_evolucion": {"labels": [], "values": []},
        "grafico_evidencias": {"labels": [], "values": []},
    }

    # PERÍODO VIGENTE
    periodo = Periodo.objects.vigente(hoy) if Periodo else None
    datos["periodo"] = periodo

    CalculoIndicadores = None

    if periodo is not None:
        from measurement.services import CalculoIndicadores

    # FUNCIONARIOS AUTORIZADOS
    funcionarios_visibles = None

    if Funcionario is not None:
        funcionarios_visibles = filtrar_por_ambito(
            Funcionario.objects.filter(
                estado=Funcionario.ESTADO_ACTIVO
            ).select_related("cargo", "delegacion"),
            user,
            "delegacion_id",
        )

        datos["total_funcionarios"] = funcionarios_visibles.count()

    # RF-030: actividad reciente por funcionario.
    # funcionarios_visibles ya está limitado al ámbito autorizado.
    datos["actividad_reciente"] = (
        construir_resumen_actividad_reciente(
            funcionarios=(
                funcionarios_visibles
                if es_supervision
                else (
                    funcionarios_visibles.filter(pk=funcionario.pk)
                    if funcionario is not None
                    and funcionarios_visibles is not None
                    else Funcionario.objects.none()
                )
            ),
            periodo=periodo,
            hoy=hoy,
        )
        if funcionarios_visibles is not None
        else []
    )

    # METAS DEL PERÍODO
    if (
        Meta is not None
        and periodo is not None
        and funcionarios_visibles is not None
    ):
        datos["hay_metas_periodo"] = Meta.objects.filter(
            periodo=periodo,
            funcionario__in=funcionarios_visibles,
        ).exists()

    # ACTIVIDADES
    actividades = None

    if Actividad is not None:
        actividades = Actividad.objects.select_related(
            "funcionario",
            "funcionario__delegacion",
            "item",
            "periodo",
        ).all()

        actividades = filtrar_por_ambito(
            actividades,
            user,
            "funcionario__delegacion_id",
        )

        if not es_supervision:
            if funcionario is not None:
                actividades = actividades.filter(
                    funcionario=funcionario
                )
            else:
                actividades = actividades.none()

        if periodo is not None:
            actividades = actividades.filter(periodo=periodo)

        datos["hay_actividades"] = actividades.exists()

        if funcionario is not None:
            datos["mis_actividades"] = actividades.filter(
                funcionario=funcionario
            ).count()

        # Evolución de los últimos seis meses.
        primer_dia_mes = hoy.replace(day=1)
        meses = []

        for desplazamiento in range(5, -1, -1):
            indice = (
                primer_dia_mes.year * 12
                + primer_dia_mes.month - 1
                - desplazamiento
            )
            anio, mes_cero = divmod(indice, 12)

            meses.append(
                primer_dia_mes.replace(
                    year=anio,
                    month=mes_cero + 1,
                )
            )

        conteos_mensuales = {}

        for fila in actividades.filter(
            fecha__gte=meses[0],
        ).annotate(
            mes=TruncMonth("fecha")
        ).values(
            "mes"
        ).annotate(
            total=Count("pk")
        ):
            mes_resultado = fila["mes"]

            if hasattr(mes_resultado, "date"):
                mes_resultado = mes_resultado.date()

            conteos_mensuales[mes_resultado] = fila["total"]

        datos["grafico_evolucion"] = {
            "labels": [
                fecha.strftime("%b %Y")
                for fecha in meses
            ],
            "values": [
                conteos_mensuales.get(fecha, 0)
                for fecha in meses
            ],
        }

    # EVIDENCIAS
    if Evidencia is not None:
        evidencias = Evidencia.objects.select_related(
            "actividad",
            "actividad__funcionario",
            "actividad__funcionario__delegacion",
            "funcionario",
        ).all()

        evidencias = filtrar_por_ambito(
            evidencias,
            user,
            "actividad__funcionario__delegacion_id",
        )

        if not es_supervision:
            if funcionario is not None:
                evidencias = evidencias.filter(
                    actividad__funcionario=funcionario
                )
            else:
                evidencias = evidencias.none()

        datos["hay_evidencias"] = evidencias.exists()

        datos["evidencias_pendientes"] = evidencias.filter(
            estado_revision=Evidencia.ESTADO_PENDIENTE
        ).count()

        conteos_evidencias = {
            fila["estado_revision"]: fila["total"]
            for fila in evidencias.values(
                "estado_revision"
            ).annotate(total=Count("pk"))
        }

        estados_evidencia = [
            valor
            for valor, etiqueta in Evidencia._meta.get_field(
                "estado_revision"
            ).choices
        ]

        datos["grafico_evidencias"] = {
            "labels": estados_evidencia,
            "values": [
                conteos_evidencias.get(estado, 0)
                for estado in estados_evidencia
            ],
        }

    # COMPROMISOS Y AGENDA
    if Compromiso is not None:
        compromisos = Compromiso.objects.select_related(
            "funcionario",
            "delegacion",
        ).all()

        compromisos = filtrar_por_ambito(
            compromisos,
            user,
            "delegacion_id",
        )

        if not es_supervision:
            if funcionario is not None:
                compromisos = compromisos.filter(
                    funcionario=funcionario
                )
            else:
                compromisos = compromisos.none()

        datos["hay_compromisos"] = compromisos.exists()

        conteos_compromisos = {
            fila["estado"]: fila["total"]
            for fila in compromisos.values(
                "estado"
            ).annotate(total=Count("pk"))
        }

        datos["compromisos_por_estado"] = conteos_compromisos

        estados_compromiso = [
            valor
            for valor, etiqueta in Compromiso._meta.get_field(
                "estado"
            ).choices
        ]

        datos["grafico_agenda"] = {
            "labels": estados_compromiso,
            "values": [
                conteos_compromisos.get(estado, 0)
                for estado in estados_compromiso
            ],
        }

        abiertos = compromisos.exclude(
            estado=Compromiso.ESTADO_REALIZADO
        )

        vencidos = abiertos.filter(
            fecha_comprometida__lt=hoy
        )

        por_vencer = abiertos.filter(
            fecha_comprometida__gte=hoy,
            fecha_comprometida__lte=limite,
        )

        datos["compromisos_vencidos"] = vencidos.count()
        datos["compromisos_por_vencer"] = por_vencer.count()

        datos["lista_vencidos"] = (
            vencidos.order_by("fecha_comprometida")[:5]
        )

    # CUMPLIMIENTO POR INDICADOR
    if periodo is not None and CalculoIndicadores is not None:

        if funcionario is not None:
            resumen_personal = CalculoIndicadores.resumen_funcionario(
                funcionario,
                periodo,
                hoy,
            )

            datos["resumen_personal"] = resumen_personal

            filas = resumen_personal.get("filas", [])

            datos["grafico_personal"] = {
                "labels": [
                    fila["item"].nombre_item
                    for fila in filas
                ],
                "values": [
                    float(fila["cumplimiento"] or 0)
                    for fila in filas
                ],
            }

        elif user.is_superuser and funcionarios_visibles is not None:
            acumulados = {}

            for funcionario_global in funcionarios_visibles:
                resumen = CalculoIndicadores.resumen_funcionario(
                    funcionario_global,
                    periodo,
                    hoy,
                )

                for fila in resumen.get("filas", []):
                    item = fila.get("item")
                    cumplimiento = fila.get("cumplimiento")

                    if item is None or cumplimiento is None:
                        continue

                    item_id = item.pk

                    if item_id not in acumulados:
                        acumulados[item_id] = {
                            "nombre": item.nombre_item,
                            "suma": 0.0,
                            "cantidad": 0,
                        }

                    acumulados[item_id]["suma"] += float(cumplimiento)
                    acumulados[item_id]["cantidad"] += 1

            datos["grafico_personal"] = {
                "labels": [
                    valor["nombre"]
                    for valor in acumulados.values()
                ],
                "values": [
                    round(
                        valor["suma"] / valor["cantidad"],
                        2,
                    )
                    for valor in acumulados.values()
                    if valor["cantidad"] > 0
                ],
            }

    # SEMÁFORO Y DESEMPEÑO DEL EQUIPO
    if (
        periodo is not None
        and funcionarios_visibles is not None
        and es_supervision
        and CalculoIndicadores is not None
    ):
        resumen_equipo = CalculoIndicadores.resumen_delegacion(
            funcionarios_visibles,
            periodo,
            hoy,
        )

        datos["resumen_equipo"] = resumen_equipo

        conteo = resumen_equipo.get("conteo", {})

        datos["grafico_semaforo"] = {
            "labels": ["Verde", "Ámbar", "Rojo"],
            "values": [
                conteo.get("Verde", 0),
                conteo.get("Ámbar", 0),
                conteo.get("Rojo", 0),
            ],
        }

        if Delegacion is not None:
            ids_delegaciones = (
                funcionarios_visibles
                .values_list("delegacion_id", flat=True)
                .distinct()
            )

            delegaciones_visibles = Delegacion.objects.filter(
                pk__in=ids_delegaciones
            ).order_by("nombre")

            etiquetas = []
            valores = []

            for delegacion in delegaciones_visibles:
                equipo = funcionarios_visibles.filter(
                    delegacion=delegacion
                )

                resumen = CalculoIndicadores.resumen_delegacion(
                    equipo,
                    periodo,
                    hoy,
                )

                etiquetas.append(delegacion.nombre)
                valores.append(
                    float(resumen.get("promedio") or 0)
                )

            datos["total_delegaciones"] = len(etiquetas)

            datos["grafico_delegaciones"] = {
                "labels": etiquetas,
                "values": valores,
            }

    # ÚLTIMAS OPERACIONES DE AUDITORÍA
    if Auditoria is not None:
        operaciones = Auditoria.objects.select_related(
            "funcionario",
            "funcionario__delegacion",
        ).all()

        operaciones = filtrar_por_ambito(
            operaciones,
            user,
            "funcionario__delegacion_id",
        )

        operaciones = operaciones.order_by(
            "-fecha",
            "-id_auditoria",
        )[:15]

        nombres_modulos = {
            "actividad": "Actividades",
            "actividades": "Actividades",
            "compromiso": "Agenda",
            "compromisos": "Agenda",
            "funcionario": "Funcionarios",
            "delegacion": "Delegaciones",
            "usuario": "Usuarios",
            "caso": "Atención social",
            "atencion": "Atención social",
            "meta": "Metas",
            "periodo": "Períodos",
            "evidencia": "Evidencias",
            "rol": "Roles",
            "cargo": "Cargos",
        }

        for operacion in operaciones:
            entidad = (
                operacion.entidad_afectada or ""
            ).strip()

            clave = entidad.lower()

            operacion.modulo = nombres_modulos.get(
                clave,
                entidad.replace("_", " ").capitalize()
                if entidad
                else "Sistema",
            )

            operacion.responsable_nombre = (
                operacion.funcionario.nombre
                if operacion.funcionario_id
                else "Sistema / técnico"
            )


        datos["alertas_operativas"] = construir_alertas_operativas(
        user=user,
        periodo=periodo,
        hoy=hoy,
    )
    return render(
        request,
        "core/dashboard.html",
        {
            "datos": datos,
            "hoy": hoy,
            "sin_funcionario": funcionario is None,
        },
    )


# ============================================================
# RECUPERACIÓN DE CONTRASEÑA SGR
# Código de un solo uso, almacenado mediante hash en MySQL.
# ============================================================

CODIGO_VIGENCIA_SEGUNDOS = 120
CODIGO_REENVIO_SEGUNDOS = 45
CODIGO_MAX_INTENTOS = 5
CODIGO_MAX_REENVIOS = 3

RESET_SESSION_KEY = "recuperacion_sgr"


def _hash_codigo_recuperacion(codigo):
    """
    Genera un hash del código utilizando SECRET_KEY.
    El código original nunca se almacena en la base de datos.
    """
    contenido = f"{codigo}{settings.SECRET_KEY}"

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


def _enmascarar_correo_sgr(email):
    """Oculta parte del correo para mostrarlo en pantalla."""

    try:
        usuario, dominio = email.split("@", 1)

        if len(usuario) <= 2:
            usuario_oculto = usuario[0] + "*"
        else:
            usuario_oculto = (
                usuario[:2]
                + "*" * (len(usuario) - 2)
            )

        return f"{usuario_oculto}@{dominio}"

    except (ValueError, IndexError):
        return email


def _invalidar_codigo_sesion(request):
    """Invalida el código anterior asociado a la sesión."""

    estado = request.session.get(RESET_SESSION_KEY, {})
    codigo_id = estado.get("codigo_id")

    if codigo_id:
        PasswordResetCode.objects.filter(
            pk=codigo_id,
            is_used=False,
        ).update(is_used=True)


def recuperar_clave(request):
    """
    Paso 1:
    - Recibe el correo.
    - Genera un código aleatorio de seis dígitos.
    - Guarda solamente el hash en la base de datos.
    - Envía el código por correo.
    - Invalida códigos anteriores.
    - Controla los reenvíos.
    """

    if request.method != "POST":
        form = SolicitarCodigoForm()

        return render(
            request,
            "registration/recuperar_clave.html",
            {"form": form},
        )

    form = SolicitarCodigoForm(request.POST)

    if not form.is_valid():
        return render(
            request,
            "registration/recuperar_clave.html",
            {"form": form},
        )

    email = (
        form.cleaned_data["email"]
        .strip()
        .lower()
    )

    ahora = int(time.time())

    anterior = request.session.get(
        RESET_SESSION_KEY,
        {},
    )

    mismo_correo = (
        anterior.get("email") == email
    )

    if mismo_correo:

        transcurrido = (
            ahora - int(anterior.get("emitido", 0))
        )

        if transcurrido < CODIGO_REENVIO_SEGUNDOS:

            messages.info(
                request,
                "Debes esperar antes de solicitar otro código.",
            )

            return redirect("validar_codigo")

        reenvios = int(
            anterior.get("reenviados", 0)
        )

        if reenvios >= CODIGO_MAX_REENVIOS:

            _invalidar_codigo_sesion(request)

            request.session.pop(
                RESET_SESSION_KEY,
                None,
            )

            messages.error(
                request,
                "Se alcanzó el máximo de reenvíos. "
                "Inicia nuevamente el proceso más tarde.",
            )

            return redirect("recuperar_clave")

        reenvios += 1

    else:

        _invalidar_codigo_sesion(request)

        reenvios = 0

    # Eliminar la autorización anterior antes de generar otra.
    request.session.pop(
        RESET_SESSION_KEY,
        None,
    )

    User = get_user_model()

    usuario = User.objects.filter(
        email__iexact=email,
    ).first()

    codigo_id = None

    # No revelar si el correo está registrado.
    if usuario and usuario.is_active and usuario.email:

        # Invalidar todos los códigos pendientes del usuario.
        PasswordResetCode.objects.filter(
            user=usuario,
            is_used=False,
        ).update(is_used=True)

        codigo = (
            f"{secrets.randbelow(900000) + 100000:06d}"
        )

        registro_codigo = PasswordResetCode.objects.create(
            user=usuario,
            code_hash=_hash_codigo_recuperacion(codigo),
            expires_at=(
                timezone.now()
                + timedelta(
                    seconds=CODIGO_VIGENCIA_SEGUNDOS
                )
            ),
        )

        try:

            enviado = send_mail(
                subject="Código de recuperación - Sistema SGR",

                message=(
                    f"Hola {usuario.get_username()},\n\n"
                    f"Tu código de recuperación es: {codigo}\n\n"
                    "Este código vence en 2 minutos.\n\n"
                    "Si no solicitaste este cambio, "
                    "puedes ignorar este correo.\n\n"
                    "Sistema de Gestión de Resultados."
                ),

                from_email=settings.DEFAULT_FROM_EMAIL,

                recipient_list=[
                    usuario.email,
                ],

                fail_silently=False,
            )

            if not enviado:
                raise RuntimeError(
                    "El servidor de correo no confirmó el envío."
                )

            codigo_id = registro_codigo.pk

        except Exception:

            registro_codigo.delete()

            messages.error(
                request,
                "No fue posible enviar el código. "
                "Comprueba la configuración del correo e inténtalo nuevamente.",
            )

            return render(
                request,
                "registration/recuperar_clave.html",
                {"form": form},
            )

    # Guardar únicamente el identificador del código.
    request.session[RESET_SESSION_KEY] = {
        "email": email,
        "codigo_id": codigo_id,
        "emitido": ahora,
        "reenviados": reenvios,
        "verificado": False,
    }

    messages.info(
        request,
        "Si el correo está asociado a una cuenta activa, "
        "recibirás un código de recuperación.",
    )

    return redirect("validar_codigo")


def validar_codigo(request):
    """
    Paso 2:
    Comprueba el código persistente, su expiración,
    el límite de intentos y su utilización.
    """

    estado = request.session.get(
        RESET_SESSION_KEY,
    )

    if not estado:

        messages.error(
            request,
            "Solicita primero un código de recuperación.",
        )

        return redirect("recuperar_clave")

    codigo_id = estado.get("codigo_id")

    if not codigo_id:

        request.session.pop(
            RESET_SESSION_KEY,
            None,
        )

        messages.error(
            request,
            "No fue posible validar la solicitud. "
            "Comprueba el correo e inténtalo nuevamente.",
        )

        return redirect("recuperar_clave")

    registro = PasswordResetCode.objects.filter(
        pk=codigo_id,
    ).first()

    if not registro:

        request.session.pop(
            RESET_SESSION_KEY,
            None,
        )

        messages.error(
            request,
            "El código ya no está disponible. Solicita uno nuevo.",
        )

        return redirect("recuperar_clave")

    if registro.is_used:

        request.session.pop(
            RESET_SESSION_KEY,
            None,
        )

        messages.error(
            request,
            "Este código ya fue utilizado. Solicita uno nuevo.",
        )

        return redirect("recuperar_clave")

    if timezone.now() >= registro.expires_at:

        registro.is_used = True
        registro.save(update_fields=["is_used"])

        request.session.pop(
            RESET_SESSION_KEY,
            None,
        )

        messages.error(
            request,
            "El código expiró. Solicita uno nuevo.",
        )

        return redirect("recuperar_clave")

    if registro.attempts >= CODIGO_MAX_INTENTOS:

        registro.is_used = True
        registro.save(update_fields=["is_used"])

        request.session.pop(
            RESET_SESSION_KEY,
            None,
        )

        messages.error(
            request,
            "Superaste el máximo de intentos. Solicita un código nuevo.",
        )

        return redirect("recuperar_clave")

    if request.method == "POST":

        form = VerificarCodigoForm(request.POST)

        if form.is_valid():

            codigo_ingresado = (
                form.cleaned_data["codigo"]
            )

            resultado = None

            with transaction.atomic():

                registro_codigo = (
                    PasswordResetCode.objects
                    .select_for_update()
                    .select_related("user")
                    .filter(pk=codigo_id)
                    .first()
                )

                if not registro_codigo:

                    resultado = "invalido"

                elif registro_codigo.is_used:

                    resultado = "usado"

                elif timezone.now() >= registro_codigo.expires_at:

                    registro_codigo.is_used = True
                    registro_codigo.save(
                        update_fields=["is_used"]
                    )

                    resultado = "expirado"

                elif (
                    registro_codigo.attempts
                    >= CODIGO_MAX_INTENTOS
                ):

                    resultado = "intentos"

                elif not registro_codigo.user.is_active:

                    resultado = "invalido"

                else:

                    hash_ingresado = (
                        _hash_codigo_recuperacion(
                            codigo_ingresado
                        )
                    )

                    correcto = hmac.compare_digest(
                        hash_ingresado,
                        registro_codigo.code_hash,
                    )

                    if correcto:

                        resultado = "correcto"

                    else:

                        registro_codigo.attempts += 1

                        if (
                            registro_codigo.attempts
                            >= CODIGO_MAX_INTENTOS
                        ):

                            registro_codigo.is_used = True

                            resultado = "intentos"

                        else:

                            resultado = "incorrecto"

                        registro_codigo.save(
                            update_fields=[
                                "attempts",
                                "is_used",
                            ]
                        )

            if resultado == "correcto":

                estado["verificado"] = True

                request.session[RESET_SESSION_KEY] = estado

                messages.success(
                    request,
                    "Código validado correctamente.",
                )

                return redirect("nueva_clave")

            if resultado == "incorrecto":

                messages.error(
                    request,
                    "Código incorrecto. "
                    "Verifica el código e inténtalo nuevamente.",
                )

            elif resultado == "intentos":

                request.session.pop(
                    RESET_SESSION_KEY,
                    None,
                )

                messages.error(
                    request,
                    "Superaste el máximo de intentos. "
                    "Solicita un código nuevo.",
                )

                return redirect("recuperar_clave")

            else:

                request.session.pop(
                    RESET_SESSION_KEY,
                    None,
                )

                messages.error(
                    request,
                    "El código ya no es válido. Solicita uno nuevo.",
                )

                return redirect("recuperar_clave")

    else:

        form = VerificarCodigoForm()

    return render(
        request,
        "registration/validar_codigo.html",
        {
            "form": form,
            "email": estado.get("email", ""),
            "email_enmascarado": _enmascarar_correo_sgr(
                estado.get("email", "")
            ),
            "codigo_expira_timestamp": int(
                registro.expires_at.timestamp() * 1000
            ),
        },
    )


def nueva_clave(request):
    """
    Paso 3:
    Permite establecer una nueva contraseña únicamente
    después de verificar el código.
    """

    estado = request.session.get(
        RESET_SESSION_KEY,
    )

    if not estado or not estado.get("verificado"):

        messages.error(
            request,
            "Primero debes validar el código enviado a tu correo.",
        )

        return redirect("recuperar_clave")

    codigo_id = estado.get("codigo_id")

    registro = (
        PasswordResetCode.objects
        .select_related("user")
        .filter(pk=codigo_id)
        .first()
    )

    if (
        not registro
        or registro.is_used
        or timezone.now() >= registro.expires_at
        or not registro.user.is_active
    ):

        _invalidar_codigo_sesion(request)

        request.session.pop(
            RESET_SESSION_KEY,
            None,
        )

        messages.error(
            request,
            "La autorización expiró o dejó de ser válida. "
            "Solicita un nuevo código.",
        )

        return redirect("recuperar_clave")

    usuario = registro.user

    if request.method == "POST":

        form = NuevaClaveForm(
            request.POST,
            user=usuario,
        )

        if form.is_valid():

            resultado = None

            with transaction.atomic():

                registro_codigo = (
                    PasswordResetCode.objects
                    .select_for_update()
                    .select_related("user")
                    .filter(pk=codigo_id)
                    .first()
                )

                if (
                    not registro_codigo
                    or registro_codigo.is_used
                    or timezone.now() >= registro_codigo.expires_at
                    or not registro_codigo.user.is_active
                ):

                    resultado = "invalido"

                else:

                    usuario_actual = registro_codigo.user

                    usuario_actual.set_password(
                        form.cleaned_data["password1"]
                    )

                    usuario_actual.save(
                        update_fields=["password"]
                    )

                    # Marcar el código utilizado.
                    registro_codigo.is_used = True

                    registro_codigo.save(
                        update_fields=["is_used"]
                    )

                    # Invalidar cualquier otro código pendiente.
                    PasswordResetCode.objects.filter(
                        user=usuario_actual,
                        is_used=False,
                    ).update(is_used=True)

                    resultado = "correcto"

            if resultado == "correcto":

                request.session.pop(
                    RESET_SESSION_KEY,
                    None,
                )

                messages.success(
                    request,
                    "Contraseña actualizada correctamente. "
                    "Ya puedes iniciar sesión.",
                )

                return redirect("login")

            request.session.pop(
                RESET_SESSION_KEY,
                None,
            )

            messages.error(
                request,
                "La autorización dejó de ser válida. "
                "Solicita un nuevo código.",
            )

            return redirect("recuperar_clave")

    else:

        form = NuevaClaveForm(
            user=usuario,
        )

    return render(
        request,
        "registration/nueva_clave.html",
        {"form": form},
    )

def registro(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistroUsuarioForm(request.POST)

        if form.is_valid():
            
            User = get_user_model()

            User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                funcionario=None,
                activo_acceso=False,

            )

            messages.success(
                request,
                "Tu solicitud fue registrada. "
                "Un administrador debe asociar tu cuenta "
                "a un funcionario y asignarte los permisos "
                "correspondientes antes de habilitar el acceso.",
            )
            return redirect("login")
    else:
        form = RegistroUsuarioForm()

    return render(
        request,
        "registration/registro.html",
        {"form": form},
    )

@login_required
def perfil(request):
    """Muestra los datos de la cuenta del usuario autenticado."""

    usuario = request.user
    funcionario = get_funcionario(usuario)

    return render(
        request,
        "core/perfil.html",
        {
            "usuario_perfil": usuario,
            "funcionario_perfil": funcionario,
        },
    )


@login_required
def perfil_editar(request):
    """Permite modificar el correo y la fotografía del usuario autenticado."""

    if request.method == "POST":
        form = PerfilUsuarioForm(
            request.POST,
            request.FILES,
            instance=request.user,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Tu perfil se actualizó correctamente.",
            )

            return redirect("perfil")

    else:
        form = PerfilUsuarioForm(
            instance=request.user,
        )

    return render(
        request,
        "core/perfil_editar.html",
        {
            "form": form,
        },
    )


@login_required
@require_POST
def marcar_alerta_atendida(request, pk):
    """
    Marca como atendida una alerta del usuario autenticado.
    Un usuario no puede modificar alertas de otro usuario.
    """
    from audit.models import AlertaOperativa

    alerta = get_object_or_404(
        AlertaOperativa,
        pk=pk,
        usuario=request.user,
    )

    if alerta.estado == AlertaOperativa.ESTADO_PENDIENTE:
        alerta.estado = AlertaOperativa.ESTADO_ATENDIDA
        alerta.fecha_atencion = timezone.now()
        alerta.atendida_por = request.user

        alerta.save(update_fields=[
            "estado",
            "fecha_atencion",
            "atendida_por",
        ])

        messages.success(
            request,
            "La alerta fue marcada como atendida.",
        )

    return redirect("dashboard")
