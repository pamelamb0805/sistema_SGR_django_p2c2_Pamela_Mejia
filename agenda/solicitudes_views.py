
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from openpyxl import Workbook

from .models import (
    SolicitudVecinal,
    HistorialTransiciones,
)
from .solicitudes_forms import SolicitudVecinalForm
from .solicitudes_services import (
    agregar_evento,
    actualizar_datos_solicitud,
    cambiar_estado,
    crear_solicitud,
    normalizar_rut,
    rut_valido,
    solicitudes_visibles,
    tutor_registrado,
    puede_gestionar_solicitud,
)


def _limitar_publico(request, accion, limite=12):
    ip = request.META.get("REMOTE_ADDR", "desconocida")
    clave = f"sgr:solicitudes:{accion}:{ip}"

    if cache.add(clave, 1, timeout=3600):
        return True

    try:
        actual = cache.incr(clave)
    except ValueError:
        cache.add(clave, 1, timeout=3600)
        actual = 1

    return actual <= limite


@login_required
def solicitud_publica(request):
    if request.method == "POST":
        if not _limitar_publico(request, "crear", 8):
            return render(
                request,
                "solicitudes/solicitud_publica.html",
                {
                    "form": SolicitudVecinalForm(request.POST),
                    "error_seguridad": (
                        "Se alcanzó el límite temporal de envíos. "
                        "Intente más tarde."
                    ),
                },
                status=429,
            )

        form = SolicitudVecinalForm(request.POST)

        if form.is_valid():
            if (
                form.cleaned_data["tipo_solicitud"]
                == SolicitudVecinal.TIPO_REGALO
            ):
                tutor_verificado = request.session.get(
                    "sgr_tutor_verificado",
                    {},
                )

                if (
                    tutor_verificado.get("rut")
                    != form.cleaned_data["rut_solicitante"]
                ):
                    form.add_error(
                        "rut_solicitante",
                        "Primero debe verificar el RUT del adulto/tutor.",
                    )

                    return render(
                        request,
                        "solicitudes/solicitud_publica.html",
                        {"form": form},
                    )

                menor_verificado = request.session.get(
                    "sgr_menor_verificado",
                    {},
                )

                if (
                    menor_verificado.get("rut")
                    != normalizar_rut(
                        form.cleaned_data.get("rut_menor", "")
                    )
                ):
                    form.add_error(
                        "rut_menor",
                        "Primero debe consultar el RUT del menor.",
                    )

                    return render(
                        request,
                        "solicitudes/solicitud_publica.html",
                        {"form": form},
                    )

            try:
                solicitud = crear_solicitud(
                    form.cleaned_data
                )

            except (
                ValueError,
                IntegrityError,
                ValidationError,
            ):
                form.add_error(
                    None,
                    "No fue posible registrar la solicitud. "
                    "Verifique los datos y si el menor ya fue inscrito.",
                )

            else:
                request.session.pop(
                    "sgr_tutor_verificado",
                    None,
                )
                request.session.pop(
                    "sgr_menor_verificado",
                    None,
                )

                messages.success(
                    request,
                    "La solicitud vecinal fue registrada correctamente.",
                )

                return redirect(
                    "solicitudes:detalle",
                    pk=solicitud.pk,
                )

    else:
        form = SolicitudVecinalForm()

    return render(
        request,
        "solicitudes/solicitud_publica.html",
        {
            "form": form,
            "tutor_verificado": request.session.get(
                "sgr_tutor_verificado"
            ),
        },
    )


@require_POST
def verificar_tutor(request):
    if not _limitar_publico(
        request,
        "verificar_tutor",
        10,
    ):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Demasiados intentos. Intente más tarde.",
            },
            status=429,
        )

    rut = normalizar_rut(
        request.POST.get("rut", "")
    )

    if not rut_valido(rut):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Ingrese un RUT válido.",
            },
            status=400,
        )

    tutor = tutor_registrado(rut)

    if tutor is None:
        request.session.pop(
            "sgr_tutor_verificado",
            None,
        )

        return JsonResponse(
            {
                "ok": False,
                "mensaje": (
                    "El adulto/tutor no está registrado en el "
                    "padrón social. No se puede continuar."
                ),
            },
            status=404,
        )

    request.session["sgr_tutor_verificado"] = {
        "rut": rut,
        "usuario_id": tutor.pk,
    }

    return JsonResponse({
        "ok": True,
        "mensaje": (
            "Adulto/tutor validado. Puede continuar "
            "con los datos del menor."
        ),
    })


@require_POST
def verificar_menor(request):
    if not _limitar_publico(
        request,
        "verificar_menor",
        10,
    ):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Demasiados intentos. Intente más tarde.",
            },
            status=429,
        )

    tutor_data = request.session.get(
        "sgr_tutor_verificado",
        {},
    )

    tutor = (
        tutor_registrado(tutor_data.get("rut", ""))
        if tutor_data
        else None
    )

    if (
        tutor is None
        or tutor.pk != tutor_data.get("usuario_id")
    ):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": (
                    "Verifique primero el RUT del adulto/tutor."
                ),
            },
            status=403,
        )

    rut = normalizar_rut(
        request.POST.get("rut", "")
    )

    if not rut_valido(rut):
        return JsonResponse(
            {
                "ok": False,
                "mensaje": "Ingrese un RUT válido del menor.",
            },
            status=400,
        )

    existente = (
        SolicitudVecinal.objects
        .filter(rut_menor=rut)
        .prefetch_related("compromisos__delegacion")
        .first()
    )

    if existente:
        compromiso = existente.compromiso_principal
        misma_delegacion = (
            compromiso is not None
            and compromiso.delegacion_id == tutor.delegacion_id
        )

        mensaje = (
            "El menor ya está registrado en esta misma delegación."
            if misma_delegacion
            else (
                "El menor ya está registrado en otra delegación. "
                "No se puede duplicar el beneficio."
            )
        )

        request.session.pop(
            "sgr_menor_verificado",
            None,
        )

        return JsonResponse(
            {
                "ok": False,
                "estado": (
                    "misma_delegacion"
                    if misma_delegacion
                    else "otra_delegacion"
                ),
                "mensaje": mensaje,
            },
            status=409,
        )

    request.session["sgr_menor_verificado"] = {
        "rut": rut,
    }

    return JsonResponse({
        "ok": True,
        "estado": "disponible",
        "mensaje": (
            "El menor no registra inscripción previa. "
            "Puede continuar."
        ),
    })


def _obtener_solicitud(user, pk):
    solicitud = (
        solicitudes_visibles(user)
        .filter(pk=pk)
        .first()
    )

    if solicitud is None:
        raise Http404("Solicitud no encontrada.")

    return solicitud


@login_required
def lista_solicitudes(request):
    qs = solicitudes_visibles(
        request.user
    ).order_by(
        "-fecha_creacion",
        "-pk",
    )

    estado = request.GET.get(
        "estado",
        "",
    ).strip()

    categoria = request.GET.get(
        "categoria",
        "",
    ).strip()

    busqueda = request.GET.get(
        "q",
        "",
    ).strip()

    if estado:
        qs = qs.filter(
            estado_solicitud=estado
        )

    if categoria:
        qs = qs.filter(
            categoria__icontains=categoria
        )

    if busqueda:
        qs = qs.filter(
            Q(rut_solicitante__icontains=busqueda)
            | Q(descripcion__icontains=busqueda)
            | Q(nombre_menor__icontains=busqueda)
            | Q(compromisos__solicitante__icontains=busqueda)
            | Q(compromisos__territorio__icontains=busqueda)
        )

    qs = qs.distinct()

    page_obj = Paginator(
        qs,
        25,
    ).get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "solicitudes/lista.html",
        {
            "solicitudes": page_obj.object_list,
            "page_obj": page_obj,
            "estados": SolicitudVecinal.ESTADOS,
            "filtros": request.GET,
        },
    )


@login_required
def detalle_solicitud(request, pk):
    solicitud = _obtener_solicitud(
        request.user,
        pk,
    )

    historial = solicitud.historial

    puede_gestionar = puede_gestionar_solicitud(
        request.user,
        solicitud,
    )

    return render(
        request,
        "solicitudes/detalle.html",
        {
            "solicitud": solicitud,
            "historial": historial,
            "puede_gestionar": puede_gestionar,
            "estados": SolicitudVecinal.ESTADOS,
            "compromisos": solicitud.compromisos.select_related(
                "funcionario",
                "delegacion",
                "item_medible",
                "periodo",
            ).order_by("fecha_comprometida"),
        },
    )


@login_required
@require_POST
def actualizar_solicitud(request, pk):
    solicitud = _obtener_solicitud(
        request.user,
        pk,
    )

    if not puede_gestionar_solicitud(
        request.user,
        solicitud,
    ):
        raise Http404("Solicitud no encontrada.")

    if (
        solicitud.estado_solicitud
        == SolicitudVecinal.ESTADO_CONCLUIDO
    ):
        messages.error(
            request,
            "La solicitud concluida no admite modificaciones.",
        )
        return redirect(
            "solicitudes:detalle",
            pk=pk,
        )

    estado = request.POST.get(
        "estado_solicitud",
        solicitud.estado_solicitud,
    )

    solucion = request.POST.get(
        "solucion",
        "",
    ).strip()

    fecha_txt = request.POST.get(
        "fecha_propuesta_solucion",
        "",
    ).strip()

    fecha = None

    if fecha_txt:
        try:
            fecha = date.fromisoformat(fecha_txt)
        except ValueError:
            messages.error(
                request,
                "La fecha propuesta no tiene un formato válido.",
            )
            return redirect(
                "solicitudes:detalle",
                pk=pk,
            )

        if fecha < timezone.localdate():
            messages.error(
                request,
                "La fecha propuesta no puede estar en el pasado.",
            )
            return redirect(
                "solicitudes:detalle",
                pk=pk,
            )

    try:
        if estado != solicitud.estado_solicitud:
            solicitud = cambiar_estado(
                solicitud,
                estado,
                request.user,
                request.POST.get("observacion", ""),
            )

        solicitud = actualizar_datos_solicitud(
            solicitud,
            solucion,
            fecha,
            request.user,
        )

        messages.success(
            request,
            "Solicitud actualizada correctamente.",
        )

    except ValueError as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "solicitudes:detalle",
        pk=pk,
    )


@login_required
@require_POST
def agregar_evento_solicitud(request, pk):
    solicitud = _obtener_solicitud(
        request.user,
        pk,
    )

    if not puede_gestionar_solicitud(
        request.user,
        solicitud,
    ):
        raise Http404("Solicitud no encontrada.")

    try:
        agregar_evento(
            solicitud,
            request.user,
            request.POST.get("observacion", ""),
        )

        messages.success(
            request,
            "Evento agregado a la trazabilidad.",
        )

    except ValueError as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "solicitudes:detalle",
        pk=pk,
    )


@login_required
def exportar_solicitudes(request):
    qs = solicitudes_visibles(
        request.user
    ).order_by(
        "-fecha_creacion",
        "-pk",
    )

    if request.GET.get("estado"):
        qs = qs.filter(
            estado_solicitud=request.GET["estado"]
        )

    if request.GET.get("categoria"):
        qs = qs.filter(
            categoria__icontains=request.GET["categoria"]
        )

    if request.GET.get("q"):
        q = request.GET["q"].strip()

        qs = qs.filter(
            Q(rut_solicitante__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(nombre_menor__icontains=q)
            | Q(compromisos__solicitante__icontains=q)
            | Q(compromisos__territorio__icontains=q)
        )

    qs = qs.distinct()

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Solicitudes"

    hoja.append([
        "Folio",
        "Fecha de creación",
        "Delegación",
        "Solicitante",
        "RUT solicitante",
        "Estado",
        "Categoría",
        "Descripción",
        "Solución",
        "Fecha propuesta",
    ])

    for solicitud in qs.iterator():
        compromiso = solicitud.compromiso_principal

        hoja.append([
            solicitud.pk,
            timezone.localtime(
                solicitud.fecha_creacion
            ).strftime("%d/%m/%Y %H:%M"),
            (
                compromiso.delegacion.nombre
                if compromiso else ""
            ),
            (
                compromiso.solicitante
                if compromiso else ""
            ),
            solicitud.rut_solicitante,
            solicitud.estado_solicitud,
            solicitud.categoria,
            solicitud.descripcion,
            solicitud.solucion,
            (
                solicitud.fecha_propuesta_solucion.isoformat()
                if solicitud.fecha_propuesta_solucion
                else ""
            ),
        ])

    trazabilidad = libro.create_sheet(
        "Trazabilidad"
    )

    trazabilidad.append([
        "Folio solicitud",
        "Folio compromiso",
        "Fecha y hora",
        "Funcionario",
        "Estado anterior",
        "Estado nuevo",
        "Evento / observación",
    ])

    eventos = (
        HistorialTransiciones.objects
        .filter(
            compromiso__solicitud_vecinal__in=qs
        )
        .select_related(
            "funcionario",
            "compromiso",
            "compromiso__solicitud_vecinal",
        )
        .order_by(
            "fecha",
            "id_cambio",
        )
    )

    for evento in eventos.iterator():
        trazabilidad.append([
            evento.compromiso.solicitud_vecinal_id,
            evento.compromiso_id,
            timezone.localtime(
                evento.fecha
            ).strftime("%d/%m/%Y %H:%M:%S"),
            evento.funcionario.nombre,
            evento.estado_anterior,
            evento.estado_nuevo,
            evento.observacion,
        ])

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    respuesta["Content-Disposition"] = (
        'attachment; filename="solicitudes_vecinales.xlsx"'
    )

    libro.save(respuesta)

    return respuesta
