"""
Vistas de social. Plantillas (templates/social/):
  caso_.html    modo: lista | form | detalle | estadisticas
  gestion_.html modo: form (nueva gestión o corrección de una existente)

Privacidad (RNF-009): solo Funcionario y Delegado (de su delegación) y Administrador/Coordinador
acceden al módulo. Cada consulta de un caso queda registrada en la auditoría.
"""
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_OPERATIVOS, AccionPostView, GuardarMixin, ModoMixin, RolRequeridoMixin, denegar_acceso,
    es_transversal, registrar_auditoria, tiene_rol,
)
from organizations.models import Delegacion

from .forms import CasoForm, EstadoCasoForm, GestionForm, NuevoCasoForm
from .models import AtencionSocial, UsuarioSocial
from .services import (
    ROLES_SOCIAL, CRUDAtencionSocial, CRUDUsuarioSocial, casos_visibles, estadisticas_atenciones,
    gestiones_visibles, maximo_gestiones, puede_escribir, puede_reabrir,
)
from django.http import Http404, JsonResponse
from core.pagination import PageSizeMixin

from django.http import Http404, JsonResponse, HttpResponse
from openpyxl import Workbook

class SocialMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_SOCIAL


class EscrituraSocialMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_OPERATIVOS

def cargar_subatenciones(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Debe iniciar sesión."},
            status=401,
        )

    if not tiene_rol(request.user, *ROLES_SOCIAL):
        return JsonResponse(
            {"error": "No tiene permiso para consultar las subatenciones."},
            status=403,
        )

    tipo_id = request.GET.get("tipo_atencion", "").strip()
    area = request.GET.get("area") or None

    if not tipo_id.isdigit():
        return JsonResponse({"subatenciones": []})

    from catalogs.models import Catalogo

    tipo = Catalogo.objects.filter(
        pk=tipo_id,
        tipo_catalogo=Catalogo.TIPO_ATENCION,
        estado=Catalogo.ESTADO_ACTIVO,
    ).first()

    if tipo is None:
        return JsonResponse({"subatenciones": []})

    subatenciones = (
        Catalogo.objects.disponibles(
            area=area,
            tipo=Catalogo.TIPO_SUBATENCION,
        )
        .filter(tipo_atencion_padre=tipo)
        .order_by("nombre")
    )

    return JsonResponse({
        "subatenciones": [
            {
                "id": subatencion.pk,
                "nombre": subatencion.nombre,
            }
            for subatencion in subatenciones
        ]
    })
# ---------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------
class CasoListView(PageSizeMixin, SocialMixin, ModoMixin, ListView):
    template_name = "social/caso_.html"
    context_object_name = "casos"
    paginate_by = 15
    page_size_session_key = "caso_page_size"
    titulo = "Casos de atención social"
    roles_edicion = ROLES_OPERATIVOS

    def get_queryset(self):
        qs = (
            casos_visibles(self.request.user)
            .annotate(total_gestiones=Count("gestiones"))
            .order_by("-fecha_primer_registro", "nombre")
        )

        g = self.request.GET

        if g.get("q", "").strip():
            qs = qs.filter(nombre__icontains=g["q"].strip())

        if g.get("territorio", "").strip():
            qs = qs.filter(
                territorio__icontains=g["territorio"].strip()
            )

        for campo, filtro in (
            ("estado_caso", "estado_caso"),
            ("delegacion", "delegacion_id"),
            ("fecha_desde", "fecha_primer_registro__gte"),
            ("fecha_hasta", "fecha_primer_registro__lte"),
        ):
            if g.get(campo):
                qs = qs.filter(**{filtro: g[campo]})

        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        contexto.update(
            filtros=self.request.GET,
            estados=UsuarioSocial.ESTADOS,
            maximo=maximo_gestiones(),
            delegaciones=(
                Delegacion.objects.all()
                if es_transversal(self.request.user)
                else []
            ),
        )

        return contexto


def exportar_casos_excel(request):
    """Exporta los casos sociales y sus gestiones respetando filtros y permisos."""

    if not request.user.is_authenticated:
        return redirect("login")

    if not tiene_rol(request.user, *ROLES_SOCIAL):
        return denegar_acceso(request)

    # Se replica el queryset del listado para conservar sus filtros.
    casos = (
        casos_visibles(request.user)
        .annotate(total_gestiones=Count("gestiones"))
        .select_related("delegacion")
        .order_by("-fecha_primer_registro", "nombre")
    )

    filtros = request.GET

    q = filtros.get("q", "").strip()
    if q:
        casos = casos.filter(nombre__icontains=q)

    territorio = filtros.get("territorio", "").strip()
    if territorio:
        casos = casos.filter(territorio__icontains=territorio)

    for campo, filtro in (
        ("estado_caso", "estado_caso"),
        ("delegacion", "delegacion_id"),
        ("fecha_desde", "fecha_primer_registro__gte"),
        ("fecha_hasta", "fecha_primer_registro__lte"),
    ):
        valor = filtros.get(campo, "").strip()
        if valor:
            casos = casos.filter(**{filtro: valor})

    libro = Workbook()

    # Hoja 1: casos.
    hoja_casos = libro.active
    hoja_casos.title = "Casos"

    hoja_casos.append([
        "N.º de caso",
        "Persona atendida",
        "Territorio",
        "Delegación",
        "Fecha de primer registro",
        "Estado del caso",
        "Total de gestiones",
    ])

    for caso in casos:
        hoja_casos.append([
            caso.pk,
            caso.nombre,
            caso.territorio,
            caso.delegacion.nombre,
            caso.fecha_primer_registro,
            caso.estado_caso,
            caso.total_gestiones,
        ])

    # Hoja 2: gestiones de los casos incluidos en el listado filtrado.
    hoja_gestiones = libro.create_sheet("Gestiones")

    hoja_gestiones.append([
        "N.º de caso",
        "Persona atendida",
        "N.º de gestión",
        "Tipo de atención",
        "Subatención",
        "Descripción",
        "Fecha de atención",
        "Fecha de registro",
        "Funcionario responsable",
        "Delegación",
        "Estado",
        "Resultado",
    ])

    gestiones = (
        gestiones_visibles(request.user)
        .filter(usuario_id__in=casos.values("pk"))
        .order_by("usuario_id", "numero_gestion")
    )

    for gestion in gestiones:
        hoja_gestiones.append([
            gestion.usuario_id,
            gestion.usuario.nombre,
            gestion.numero_gestion,
            gestion.tipo_atencion.nombre,
            gestion.subatencion.nombre,
            gestion.descripcion,
            gestion.fecha,
            gestion.fecha_registro.replace(tzinfo=None)
            if gestion.fecha_registro else None,
            gestion.funcionario.nombre,
            gestion.delegacion.nombre,
            gestion.estado,
            gestion.resultado,
        ])

    # Formato general de las hojas.
    for hoja in libro.worksheets:
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = hoja.dimensions

        for columna in hoja.columns:
            ancho = max(
                len(str(celda.value or ""))
                for celda in columna
            )
            hoja.column_dimensions[
                columna[0].column_letter
            ].width = min(ancho + 3, 45)

        for celda in hoja[1]:
            celda.font = celda.font.copy(bold=True)

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    respuesta["Content-Disposition"] = (
        'attachment; filename="atencion_social.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"

    libro.save(respuesta)
    return respuesta

class CasoDetailView(SocialMixin, ModoMixin, DetailView):
    """Secuencia completa de gestiones desde un único caso (CA-04)."""
    template_name = "social/caso_.html"
    context_object_name = "caso"
    modo = "detalle"

    def get_queryset(self):
        return casos_visibles(self.request.user)

    def get(self, request, *args, **kwargs):
        respuesta = super().get(request, *args, **kwargs)
        registrar_auditoria(request, "CONSULTAR_CASO", "usuario_social", self.object.pk)   # acceso a datos personales
        return respuesta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        caso, user = self.object, self.request.user
        gestiones = CRUDUsuarioSocial.mostrar_historial_gestiones(caso.pk)
        escribe = puede_escribir(user, caso.delegacion_id)
        puede_cambiar_estado = (escribe or es_transversal(user)) and (not caso.cerrado or puede_reabrir(user, caso.delegacion_id))
        contexto.update(
            titulo=f"Caso N° {caso.pk}: {caso.nombre}", gestiones=gestiones, maximo=maximo_gestiones(),
            restantes=max(0, maximo_gestiones() - len(gestiones)),
            puede_editar=escribe and not caso.cerrado,
            puede_agregar=escribe and not caso.cerrado and CRUDAtencionSocial.validar_maximo_tres_gestiones(caso.pk),
            estado_form=EstadoCasoForm(initial={"estado_caso": caso.estado_caso}) if puede_cambiar_estado else None,
        )
        return contexto

class CasoCreateView(
    EscrituraSocialMixin,
    ModoMixin,
    GuardarMixin,
    FormView,
):
    form_class = NuevoCasoForm
    template_name = "social/caso_.html"
    modo, titulo = "form", "Nuevo caso de atención social"
    roles_edicion = ROLES_OPERATIVOS

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["area"] = self.request.GET.get("area") or None
        return kwargs

    def guardar(self, form):
        datos = form.cleaned_data

        caso = UsuarioSocial(
            nombre=datos["nombre"],
            territorio=datos["territorio"],
        )

        gestion = AtencionSocial(
            tipo_atencion=datos["tipo_atencion"],
            subatencion=datos["subatencion"],
            descripcion=datos["descripcion"],
            fecha=datos["fecha"],
            estado=datos["estado"],
            resultado=datos["resultado"],
        )

        self.caso = CRUDUsuarioSocial.crear_caso(
            caso,
            gestion,
            self.request.user,
        )

        self.mensaje_exito = (
            f"Caso N° {self.caso.pk} registrado con su primera gestión."
        )

    def get_success_url(self):
        return reverse(
            "social:caso_detail",
            args=[self.caso.pk],
        )


class CasoUpdateView(EscrituraSocialMixin, ModoMixin, GuardarMixin, UpdateView):
    form_class = CasoForm
    template_name = "social/caso_.html"
    modo, titulo = "form", "Editar datos del caso"
    roles_edicion = ROLES_OPERATIVOS
    mensaje_exito = "Datos del caso actualizados."

    def get_queryset(self):
        return casos_visibles(self.request.user)

    def guardar(self, form):
        self.object = CRUDUsuarioSocial.modificar_caso(form.instance, self.request.user)

    def get_success_url(self):
        return reverse("social:caso_detail", args=[self.object.pk])


class CasoEstadoView(AccionPostView):
    roles_permitidos = ROLES_SOCIAL

    def get_objeto(self, pk):
        return get_object_or_404(casos_visibles(self.request.user), pk=pk)

    def accion(self, request, objeto):
        form = EstadoCasoForm(request.POST)
        if not form.is_valid():
            raise ReglaNegocioError("Seleccione un estado válido.")
        CRUDUsuarioSocial.cambiar_estado_caso(objeto, form.cleaned_data["estado_caso"], request.user)
        return f"Caso actualizado a «{form.cleaned_data['estado_caso']}»."

    def get_redirect(self, objeto):
        return reverse("social:caso_detail", args=[objeto.pk])


# ---------------------------------------------------------------------------
# Gestiones
# ---------------------------------------------------------------------------
class GestionCreateView(
    EscrituraSocialMixin,
    ModoMixin,
    GuardarMixin,
    CreateView,
):
    model = AtencionSocial
    form_class = GestionForm
    template_name = "social/gestion_.html"
    modo, titulo = "form", "Nueva gestión"
    roles_edicion = ROLES_OPERATIVOS
    mensaje_exito = "Gestión registrada en el caso."

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not tiene_rol(request.user, *ROLES_OPERATIVOS):
                return denegar_acceso(request)

            self.caso = get_object_or_404(
                casos_visibles(request.user),
                pk=kwargs["pk"],
            )

            if not puede_escribir(
                request.user,
                self.caso.delegacion_id,
            ):
                return denegar_acceso(request)

            if (
                self.caso.cerrado
                or not CRUDAtencionSocial.validar_maximo_tres_gestiones(
                    self.caso.pk
                )
            ):
                messages.error(
                    request,
                    "El caso está cerrado o ya tiene todas las gestiones permitidas.",
                )
                return redirect(
                    "social:caso_detail",
                    pk=self.caso.pk,
                )

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            caso=self.caso,
            area=self.request.GET.get("area") or None,
            instance=AtencionSocial(usuario=self.caso),
        )
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            caso=self.caso,
            gestiones=CRUDAtencionSocial.mostrar_gestiones_por_caso(
                self.caso.pk
            ),
            maximo=maximo_gestiones(),
        )
        return contexto

    def guardar(self, form):
        self.object = CRUDAtencionSocial.registrar_gestion(
            form.instance,
            self.request.user,
        )

    def get_success_url(self):
        return reverse(
            "social:caso_detail",
            args=[self.caso.pk],
        )

class GestionUpdateView(
    EscrituraSocialMixin,
    ModoMixin,
    GuardarMixin,
    UpdateView,
):
    form_class = GestionForm
    template_name = "social/gestion_.html"
    modo, titulo = "form", "Corregir gestión"
    roles_edicion = ROLES_OPERATIVOS
    mensaje_exito = "Gestión actualizada."

    def get_queryset(self):
        return gestiones_visibles(self.request.user)

    def get_object(self, queryset=None):
        objeto = super().get_object(queryset)

        if not puede_escribir(
            self.request.user,
            objeto.usuario.delegacion_id,
        ):
            raise Http404

        if objeto.usuario.cerrado:
            raise Http404

        return objeto



    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            caso=self.object.usuario,
            area=self.request.GET.get("area") or None,
        )
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            caso=self.object.usuario,
            maximo=maximo_gestiones(),
            gestiones=CRUDAtencionSocial.mostrar_gestiones_por_caso(
                self.object.usuario_id
            ),
        )
        return contexto

    def guardar(self, form):
        self.object = CRUDAtencionSocial.modificar_gestion(
            form.instance,
            self.request.user,
        )

    def get_success_url(self):
        return reverse(
            "social:caso_detail",
            args=[self.object.usuario_id],
        )


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------
def estadisticas(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not tiene_rol(request.user, *ROLES_SOCIAL):
        return denegar_acceso(request)
    g = request.GET
    qs = gestiones_visibles(request.user)
    for campo, filtro in (("fecha_desde", "fecha__gte"), ("fecha_hasta", "fecha__lte"),
                          ("delegacion", "usuario__delegacion_id")):
        if g.get(campo) and (campo != "delegacion" or es_transversal(request.user)):
            qs = qs.filter(**{filtro: g[campo]})
    return render(request, "social/caso_.html", {
        "modo": "estadisticas", "titulo": "Estadísticas de atención social", "filtros": g,
        "estadisticas": estadisticas_atenciones(qs), "hoy": timezone.localdate(),
        "delegaciones": Delegacion.objects.all() if es_transversal(request.user) else [],
    })


def exportar_estadisticas_excel(request):
    """Exporta estadísticas sociales respetando filtros y permisos."""

    if not request.user.is_authenticated:
        return redirect("login")

    if not tiene_rol(request.user, *ROLES_SOCIAL):
        return denegar_acceso(request)

    filtros = request.GET
    gestiones = gestiones_visibles(request.user)

    # Aplicar exactamente los filtros del informe.
    for campo, filtro in (
        ("fecha_desde", "fecha__gte"),
        ("fecha_hasta", "fecha__lte"),
        ("delegacion", "usuario__delegacion_id"),
    ):
        valor = filtros.get(campo, "").strip()

        if valor and (
            campo != "delegacion" or es_transversal(request.user)
        ):
            gestiones = gestiones.filter(**{filtro: valor})

    # Las estadísticas consideran únicamente gestiones realizadas.
    realizadas = (
        gestiones.filter(
            estado=AtencionSocial.ESTADO_REALIZADA
        )
        .select_related(
            "usuario",
            "tipo_atencion",
            "subatencion",
            "funcionario",
            "delegacion",
        )
        .order_by("fecha", "usuario_id", "numero_gestion")
    )

    resumen = estadisticas_atenciones(gestiones)

    libro = Workbook()

    # --------------------------------------------------
    # HOJA 1: RESUMEN GENERAL
    # --------------------------------------------------
    hoja = libro.active
    hoja.title = "Resumen"

    hoja.append(["ESTADÍSTICAS DE ATENCIÓN SOCIAL"])
    hoja.append(["Indicador", "Total"])
    hoja.append([
        "Gestiones realizadas",
        resumen["total_gestiones"],
    ])
    hoja.append([
        "Personas atendidas",
        resumen["total_personas"],
    ])

    hoja.append([])
    hoja.append(["Filtros aplicados", "Valor"])
    hoja.append([
        "Fecha desde",
        filtros.get("fecha_desde") or "Todas",
    ])
    hoja.append([
        "Fecha hasta",
        filtros.get("fecha_hasta") or "Todas",
    ])

    delegacion_id = filtros.get("delegacion", "").strip()

    if delegacion_id and es_transversal(request.user):
        nombre_delegacion = (
            Delegacion.objects.filter(pk=delegacion_id)
            .values_list("nombre", flat=True)
            .first()
        )
        hoja.append([
            "Delegación",
            nombre_delegacion or "No encontrada",
        ])
    else:
        hoja.append([
            "Delegación",
            "Todas las delegaciones autorizadas",
        ])

    # --------------------------------------------------
    # HOJA 2: POR TIPO DE ATENCIÓN
    # --------------------------------------------------
    hoja = libro.create_sheet("Por tipo")
    hoja.append(["Tipo de atención", "Total"])

    for fila in resumen["por_tipo"]:
        hoja.append([
            fila["tipo_atencion__nombre"] or "Sin especificar",
            fila["total"],
        ])

    # --------------------------------------------------
    # HOJA 3: POR SUBATENCIÓN
    # --------------------------------------------------
    hoja = libro.create_sheet("Por subatención")
    hoja.append(["Subatención", "Total"])

    for fila in resumen["por_subatencion"]:
        hoja.append([
            fila["subatencion__nombre"] or "Sin especificar",
            fila["total"],
        ])

    # --------------------------------------------------
    # HOJA 4: POR DELEGACIÓN
    # --------------------------------------------------
    hoja = libro.create_sheet("Por delegación")
    hoja.append(["Delegación", "Total"])

    for fila in resumen["por_delegacion"]:
        hoja.append([
            fila["delegacion__nombre"] or "Sin especificar",
            fila["total"],
        ])

    # --------------------------------------------------
    # HOJA 5: POR MES
    # --------------------------------------------------
    hoja = libro.create_sheet("Por mes")
    hoja.append(["Mes", "Total"])

    for fila in resumen["por_mes"]:
        mes = fila["mes"]

        hoja.append([
            mes.strftime("%m/%Y") if mes else "",
            fila["total"],
        ])

    # --------------------------------------------------
    # HOJA 6: DETALLE DE GESTIONES
    # --------------------------------------------------
    hoja = libro.create_sheet("Detalle")

    hoja.append([
        "N.º de caso",
        "Persona atendida",
        "Territorio",
        "N.º de gestión",
        "Tipo de atención",
        "Subatención",
        "Descripción",
        "Fecha de atención",
        "Fecha de registro",
        "Funcionario responsable",
        "Delegación",
        "Resultado",
    ])

    for gestion in realizadas:
        fecha_registro = gestion.fecha_registro

        if fecha_registro and timezone.is_aware(fecha_registro):
            fecha_registro = timezone.localtime(
                fecha_registro
            ).replace(tzinfo=None)

        hoja.append([
            gestion.usuario_id,
            gestion.usuario.nombre,
            gestion.usuario.territorio,
            gestion.numero_gestion,
            gestion.tipo_atencion.nombre,
            gestion.subatencion.nombre,
            gestion.descripcion,
            gestion.fecha,
            fecha_registro,
            str(gestion.funcionario),
            gestion.delegacion.nombre,
            gestion.resultado,
        ])

    # --------------------------------------------------
    # FORMATO DE LAS HOJAS
    # --------------------------------------------------
    for hoja in libro.worksheets:
        hoja.freeze_panes = "A2"

        if hoja.title != "Resumen":
            hoja.auto_filter.ref = hoja.dimensions

        for columna in hoja.columns:
            ancho = max(
                (
                    len(str(celda.value or ""))
                    for celda in columna
                ),
                default=10,
            )

            hoja.column_dimensions[
                columna[0].column_letter
            ].width = min(max(ancho + 3, 12), 50)

    respuesta = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    respuesta["Content-Disposition"] = (
        'attachment; filename="estadisticas_sociales.xlsx"'
    )
    respuesta["Cache-Control"] = "private, no-store"

    libro.save(respuesta)

    return respuesta
