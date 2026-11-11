from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from .auth_forms import (
    NuevaClaveForm,
    RegistroUsuarioForm,
    SGRAuthenticationForm,
    SolicitarCodigoForm,
    VerificarCodigoForm,
)

from .mixins import (
    ROL_VERIFICADOR,
    ROLES_SUPERVISION,
    es_transversal,
    filtrar_por_ambito,
    get_funcionario,
    registrar_auditoria,
    tiene_rol,
)

import hashlib
import secrets
import time

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from organizations.forms import PerfilUsuarioForm

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

@login_required
def dashboard(request):
    from datetime import timedelta

    from django.conf import settings
    from django.db.models import Count
    from django.shortcuts import render
    from django.utils import timezone

    user = request.user
    hoy = timezone.localdate()
    dias_alerta = getattr(settings, "SGR_DIAS_ALERTA_VENCIMIENTO", 7)
    limite = hoy + timedelta(days=dias_alerta)

    funcionario = get_funcionario(user)

    # Obtener modelos sin provocar errores si alguna aplicación
    # todavía no tiene disponible su modelo.
    Funcionario = _modelo("organizations", "Funcionario")
    Delegacion = _modelo("organizations", "Delegacion")
    Actividad = _modelo("activities", "Actividad")
    Evidencia = _modelo("activities", "Evidencia")
    Compromiso = _modelo("agenda", "Compromiso")
    Periodo = _modelo("measurement", "Periodo")
    Auditoria = _modelo("audit", "Auditoria")

    # Estructura inicial: evita variables inexistentes en el template.
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
        "grafico_actividades": {
            "labels": [],
            "values": [],
        },
        "grafico_agenda": {
            "labels": [],
            "values": [],
        },
        "grafico_semaforo": {
            "labels": ["Verde", "Ámbar", "Rojo"],
            "values": [0, 0, 0],
        },
        "grafico_personal": {
            "labels": [],
            "values": [],
        },
    }

    es_supervision = tiene_rol(user, *ROLES_SUPERVISION)

    # ---------------------------------------------------------
    # PERÍODO VIGENTE
    # ---------------------------------------------------------
    periodo = None

    if Periodo is not None:
        periodo = Periodo.objects.vigente(hoy)

    datos["periodo"] = periodo

    # Importación compartida por los dos resúmenes.
    CalculoIndicadores = None

    if periodo is not None:
        from measurement.services import CalculoIndicadores

    # ---------------------------------------------------------
    # FUNCIONARIOS Y DELEGACIONES VISIBLES
    # ---------------------------------------------------------
    if Funcionario is not None:
        funcionarios_visibles = filtrar_por_ambito(
            Funcionario.objects.all(),
            user,
            "delegacion_id",
        )

        datos["total_funcionarios"] = funcionarios_visibles.count()

    if Delegacion is not None and es_transversal(user):
        datos["total_delegaciones"] = Delegacion.objects.count()

    # ---------------------------------------------------------
    # ACTIVIDADES
    # ---------------------------------------------------------
    if Actividad is not None:
        actividades = Actividad.objects.all()

        actividades = filtrar_por_ambito(
            actividades,
            user,
            "funcionario__delegacion_id",
        )

        # Los funcionarios comunes solamente ven sus actividades.
        if not es_supervision:
            if funcionario is not None:
                actividades = actividades.filter(funcionario=funcionario)
            else:
                actividades = actividades.none()

        if periodo is not None:
            actividades = actividades.filter(periodo=periodo)

        if funcionario is not None:
            datos["mis_actividades"] = actividades.filter(
                funcionario=funcionario
            ).count()

        conteos_actividades = {
            fila["estado"]: fila["total"]
            for fila in actividades.values("estado").annotate(
                total=Count("pk")
            )
        }

        estados_actividad = [
            valor
            for valor, etiqueta in Actividad._meta.get_field(
                "estado"
            ).choices
        ]

        datos["grafico_actividades"] = {
            "labels": estados_actividad,
            "values": [
                conteos_actividades.get(estado, 0)
                for estado in estados_actividad
            ],
        }

    # ---------------------------------------------------------
    # EVIDENCIAS PENDIENTES DE REVISIÓN
    # ---------------------------------------------------------
    if Evidencia is not None:
        evidencias = Evidencia.objects.filter(
            estado_revision=Evidencia.ESTADO_PENDIENTE
        )

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

        datos["evidencias_pendientes"] = evidencias.count()

    # ---------------------------------------------------------
    # COMPROMISOS Y AGENDA MUNICIPAL
    # ---------------------------------------------------------
    if Compromiso is not None:
        compromisos = Compromiso.objects.all()

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

        conteos_compromisos = {
            fila["estado"]: fila["total"]
            for fila in compromisos.values("estado").annotate(
                total=Count("pk")
            )
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
            vencidos
            .select_related("funcionario", "delegacion")
            .order_by("fecha_comprometida")[:5]
        )

    # ---------------------------------------------------------
    # DESEMPEÑO DEL FUNCIONARIO
    # ---------------------------------------------------------
    if (
        periodo is not None
        and funcionario is not None
        and CalculoIndicadores is not None
    ):
        resumen_personal = CalculoIndicadores.resumen_funcionario(
            funcionario,
            periodo,
            hoy,
        )

        datos["resumen_personal"] = resumen_personal

        filas_personales = resumen_personal.get("filas", [])

        datos["grafico_personal"] = {
            "labels": [
                fila["item"].nombre_item
                for fila in filas_personales
            ],
            "values": [
                float(fila["cumplimiento"] or 0)
                for fila in filas_personales
            ],
        }

    # ---------------------------------------------------------
    # RESUMEN DEL EQUIPO / SEMÁFORO INSTITUCIONAL
    # ---------------------------------------------------------
    if (
        periodo is not None
        and Funcionario is not None
        and es_supervision
        and CalculoIndicadores is not None
    ):
        equipo = Funcionario.objects.filter(
            estado=Funcionario.ESTADO_ACTIVO
        ).select_related(
            "cargo",
            "delegacion",
        )

        equipo = filtrar_por_ambito(
            equipo,
            user,
            "delegacion_id",
        )

        resumen_equipo = CalculoIndicadores.resumen_delegacion(
            equipo,
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

    # ---------------------------------------------------------
    # ÚLTIMOS 15 REGISTROS REALES DE AUDITORÍA
    # ---------------------------------------------------------
    if Auditoria is not None:
        operaciones = Auditoria.objects.select_related(
            "funcionario"
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
            entidad = (operacion.entidad_afectada or "").strip()
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

        datos["ultimas_operaciones"] = operaciones

    # ---------------------------------------------------------
    # RENDERIZADO
    # ---------------------------------------------------------
    return render(
        request,
        "core/dashboard.html",
        {
            "datos": datos,
            "hoy": hoy,
            "sin_funcionario": funcionario is None,
        },
    )


# Recuperación con código de un solo uso.
CODIGO_VIGENCIA_SEGUNDOS = 120
CODIGO_REENVIO_SEGUNDOS = 45
CODIGO_MAX_INTENTOS = 5
CODIGO_MAX_REENVIOS = 3

def recuperar_clave(request):
    if request.method == "POST":
        form = SolicitarCodigoForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            ahora = int(time.time())
            anterior = request.session.get("recuperacion_sgr", {})

            mismo_correo = anterior.get("email") == email

            if mismo_correo:
                transcurrido = ahora - int(anterior.get("emitido", 0))

                if transcurrido < CODIGO_REENVIO_SEGUNDOS:
                    messages.info(
                        request,
                        "Si la cuenta existe, recibirás instrucciones. "
                        "Espera antes de solicitar otro código.",
                    )
                    return redirect("recuperar_clave")

                reenvios = int(anterior.get("reenviados", 0))

                if reenvios >= CODIGO_MAX_REENVIOS:
                    request.session.pop("recuperacion_sgr", None)
                    messages.error(
                        request,
                        "Se alcanzó el máximo de reenvíos. "
                        "Inicia nuevamente el proceso más tarde.",
                    )
                    return redirect("recuperar_clave")

                reenvios += 1
            else:
                reenvios = 0

            User = get_user_model()
            user = User.objects.filter(email__iexact=email).first()

            # No revelar si el correo está registrado.
            if user and user.is_active and user.email:
                codigo = f"{secrets.randbelow(1000000):06d}"

                request.session["recuperacion_sgr"] = {
                    "email": email,
                    "user_id": user.pk,
                    "hash": hashlib.sha256(
                        codigo.encode("utf-8")
                    ).hexdigest(),
                    "emitido": ahora,
                    "intentos": 0,
                    "reenviados": reenvios,
                    "verificado": False,
                }

                try:
                    asunto = "Código de recuperación SGR"
                    mensaje = (
                        f"Tu código de recuperación es {codigo}. "
                        "Vence en 2 minutos. "
                        "Si no lo solicitaste, ignora este correo."
                    )

                    send_mail(
                        asunto,
                        mensaje,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )

                except Exception:
                    request.session.pop("recuperacion_sgr", None)
                    messages.error(
                        request,
                        "No se pudo enviar el correo. "
                        "Verifica la configuración SMTP e inténtalo nuevamente.",
                    )
                    return render(
                        request,
                        "registration/recuperar_clave.html",
                        {"form": form},
                    )

            messages.info(
                request,
                "Si el correo está asociado a una cuenta activa, "
                "recibirás un código de recuperación.",
            )
            return redirect("validar_codigo")

    else:
        form = SolicitarCodigoForm()

    return render(
        request,
        "registration/recuperar_clave.html",
        {"form": form},
    )



def validar_codigo(request):
    estado = request.session.get("recuperacion_sgr")

    if not estado:
        messages.info(
            request,
            "Solicita primero un código de recuperación.",
        )
        return redirect("recuperar_clave")

    if int(time.time()) - int(estado.get("emitido", 0)) > CODIGO_VIGENCIA_SEGUNDOS:
        request.session.pop("recuperacion_sgr", None)
        messages.error(
            request,
            "El código venció. Solicita uno nuevo.",
        )
        return redirect("recuperar_clave")

    if request.method == "POST":
        form = VerificarCodigoForm(request.POST)

        if form.is_valid():
            estado["intentos"] = int(estado.get("intentos", 0)) + 1

            recibido = hashlib.sha256(
                form.cleaned_data["codigo"].encode("utf-8")
            ).hexdigest()

            correcto = secrets.compare_digest(
                recibido,
                estado.get("hash", ""),
            )

            if correcto:
                estado["verificado"] = True
                request.session["recuperacion_sgr"] = estado
                return redirect("nueva_clave")

            if estado["intentos"] >= CODIGO_MAX_INTENTOS:
                request.session.pop("recuperacion_sgr", None)
                messages.error(
                    request,
                    "Se superó el máximo de intentos. Solicita un código nuevo.",
                )
                return redirect("recuperar_clave")

            request.session["recuperacion_sgr"] = estado
            messages.error(request, "El código ingresado es incorrecto.")
    else:
        form = VerificarCodigoForm()

    return render(
        request,
        "registration/validar_codigo.html",
        {"form": form},
    )


def nueva_clave(request):
    estado = request.session.get("recuperacion_sgr")

    if not estado or not estado.get("verificado"):
        messages.error(
            request,
            "Primero debes validar el código enviado a tu correo.",
        )
        return redirect("recuperar_clave")

    if int(time.time()) - int(estado.get("emitido", 0)) > CODIGO_VIGENCIA_SEGUNDOS:
        request.session.pop("recuperacion_sgr", None)
        messages.error(
            request,
            "El código venció. Solicita uno nuevo.",
        )
        return redirect("recuperar_clave")

    User = get_user_model()
    user = User.objects.filter(
        pk=estado.get("user_id"),
        is_active=True,
    ).first()

    if not user:
        request.session.pop("recuperacion_sgr", None)
        messages.error(
            request,
            "No se pudo completar la recuperación. Solicita un código nuevo.",
        )
        return redirect("recuperar_clave")

    if request.method == "POST":
        form = NuevaClaveForm(request.POST, user=user)

        if form.is_valid():
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])

            request.session.pop("recuperacion_sgr", None)
            messages.success(
                request,
                "Contraseña actualizada. Ya puedes iniciar sesión.",
            )
            return redirect("login")
    else:
        form = NuevaClaveForm(user=user)

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