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
    """
    Panel inicial. Los datos se limitan al ámbito del usuario (delegación).
    Cada bloque es None si su app aún no existe; la plantilla lo omite.
    """
    user = request.user
    funcionario = get_funcionario(user)
    hoy = timezone.localdate()
    limite = hoy + timedelta(days=settings.SGR_DIAS_ALERTA_VENCIMIENTO)

    Funcionario = _modelo("organizations", "Funcionario")
    Delegacion = _modelo("organizations", "Delegacion")
    Actividad = _modelo("activities", "Actividad")
    Evidencia = _modelo("activities", "Evidencia")
    Compromiso = _modelo("agenda", "Compromiso")

    datos = {
        "total_delegaciones": None,
        "total_funcionarios": None,
        "mis_actividades": None,
        "evidencias_pendientes": None,
        "compromisos_por_estado": None,
        "compromisos_vencidos": None,
        "compromisos_por_vencer": None,
        "lista_vencidos": None,
        "es_verificador": tiene_rol(user, ROL_VERIFICADOR),
    }

    if Delegacion is not None and es_transversal(user):
        datos["total_delegaciones"] = Delegacion.objects.count()

    if Funcionario is not None:
        datos["total_funcionarios"] = filtrar_por_ambito(
            Funcionario.objects.all(), user, "delegacion_id").count()

    if Actividad is not None and funcionario is not None:
        datos["mis_actividades"] = Actividad.objects.filter(funcionario=funcionario).count()

    if Evidencia is not None:
        datos["evidencias_pendientes"] = filtrar_por_ambito(
            Evidencia.objects.filter(estado_revision="Pendiente"),
            user, "actividad__funcionario__delegacion_id").count()

    if Compromiso is not None:
        base = filtrar_por_ambito(Compromiso.objects.all(), user, "delegacion_id")
        abiertos = base.exclude(estado="Realizado")
        datos["compromisos_por_estado"] = {
            fila["estado"]: fila["total"]
            for fila in base.values("estado").annotate(total=Count("pk"))
        }
        vencidos = abiertos.filter(fecha_comprometida__lt=hoy)
        datos["compromisos_vencidos"] = vencidos.count()
        datos["compromisos_por_vencer"] = abiertos.filter(
            fecha_comprometida__gte=hoy,
            fecha_comprometida__lte=limite).count()
        datos["lista_vencidos"] = vencidos.select_related(
            "funcionario", "delegacion").order_by("fecha_comprometida")[:5]

    # --- Medición: semáforo personal y consolidado del equipo ---
    datos.update({"periodo": None, "resumen_personal": None, "resumen_equipo": None})
    Periodo = _modelo("measurement", "Periodo")
    if Periodo is not None:
        from measurement.services import CalculoIndicadores

        periodo = Periodo.objects.vigente(hoy)
        datos["periodo"] = periodo
        if periodo is not None:
            if funcionario is not None:
                datos["resumen_personal"] = CalculoIndicadores.resumen_funcionario(funcionario, periodo, hoy)
            if tiene_rol(user, *ROLES_SUPERVISION) and Funcionario is not None:
                equipo = filtrar_por_ambito(
                    Funcionario.objects.filter(estado="Activo").select_related("cargo", "delegacion"),
                    user, "delegacion_id")
                datos["resumen_equipo"] = CalculoIndicadores.resumen_delegacion(equipo, periodo, hoy)

    return render(request, "core/dashboard.html", {
        "datos": datos, "hoy": hoy, "sin_funcionario": funcionario is None,
    })


# Recuperación con código de un solo uso.
CODIGO_VIGENCIA_SEGUNDOS = 600
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

            # Mensaje neutro: no revelar si el correo está registrado.
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
                    send_mail(
                        subject="Código de recuperación SGR",
                        message=(
                            f"Tu código de recuperación es {codigo}. "
                            "Vence en 10 minutos. "
                            "Si no lo solicitaste, ignora este correo."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
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