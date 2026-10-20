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


class SocialMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_SOCIAL


class EscrituraSocialMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_OPERATIVOS


# ---------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------
class CasoListView(SocialMixin, ModoMixin, ListView):
    template_name = "social/caso_.html"
    context_object_name = "casos"
    paginate_by = 15
    titulo = "Casos de atención social"
    roles_edicion = ROLES_OPERATIVOS

    def get_queryset(self):
        qs = casos_visibles(self.request.user).annotate(total_gestiones=Count("gestiones")) \
            .order_by("-fecha_primer_registro", "nombre")
        g = self.request.GET
        if g.get("q", "").strip():
            qs = qs.filter(nombre__icontains=g["q"].strip())
        if g.get("territorio", "").strip():
            qs = qs.filter(territorio__icontains=g["territorio"].strip())
        for campo, filtro in (("estado_caso", "estado_caso"), ("delegacion", "delegacion_id"),
                              ("fecha_desde", "fecha_primer_registro__gte"),
                              ("fecha_hasta", "fecha_primer_registro__lte")):
            if g.get(campo):
                qs = qs.filter(**{filtro: g[campo]})
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            filtros=self.request.GET, estados=UsuarioSocial.ESTADOS, maximo=maximo_gestiones(),
            delegaciones=Delegacion.objects.all() if es_transversal(self.request.user) else [])
        return contexto


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


class CasoCreateView(EscrituraSocialMixin, ModoMixin, GuardarMixin, FormView):
    form_class = NuevoCasoForm
    template_name = "social/caso_.html"
    modo, titulo = "form", "Nuevo caso de atención social"
    roles_edicion = ROLES_OPERATIVOS

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["area"] = self.request.GET.get("area") or None
        return kwargs

    def guardar(self, form):
        d = form.cleaned_data
        caso = UsuarioSocial(nombre=d["nombre"], territorio=d["territorio"])
        gestion = AtencionSocial(tipo_atencion=d["tipo_atencion"], catalogo=d["catalogo"], fecha=d["fecha"],
                                 estado=d["estado"], resultado=d["resultado"])
        self.caso = CRUDUsuarioSocial.crear_caso(caso, gestion, self.request.user)
        self.mensaje_exito = f"Caso N° {self.caso.pk} registrado con su primera gestión."

    def get_success_url(self):
        return reverse("social:caso_detail", args=[self.caso.pk])


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
class GestionCreateView(EscrituraSocialMixin, ModoMixin, GuardarMixin, CreateView):
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
            self.caso = get_object_or_404(casos_visibles(request.user), pk=kwargs["pk"])
            if not puede_escribir(request.user, self.caso.delegacion_id):
                return denegar_acceso(request)
            if self.caso.cerrado or not CRUDAtencionSocial.validar_maximo_tres_gestiones(self.caso.pk):
                messages.error(request, "El caso está cerrado o ya tiene todas las gestiones permitidas.")
                return redirect("social:caso_detail", pk=self.caso.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(caso=self.caso, area=self.request.GET.get("area") or None,
                      instance=AtencionSocial(usuario=self.caso))
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(caso=self.caso, gestiones=CRUDAtencionSocial.mostrar_gestiones_por_caso(self.caso.pk),
                        maximo=maximo_gestiones())
        return contexto

    def guardar(self, form):
        self.object = CRUDAtencionSocial.registrar_gestion(form.instance, self.request.user)

    def get_success_url(self):
        return reverse("social:caso_detail", args=[self.caso.pk])


class GestionUpdateView(EscrituraSocialMixin, ModoMixin, GuardarMixin, UpdateView):
    form_class = GestionForm
    template_name = "social/gestion_.html"
    modo, titulo = "form", "Corregir gestión"
    roles_edicion = ROLES_OPERATIVOS
    mensaje_exito = "Gestión actualizada."

    def get_queryset(self):
        return gestiones_visibles(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(caso=self.object.usuario, area=self.request.GET.get("area") or None)
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(caso=self.object.usuario, maximo=maximo_gestiones(),
                        gestiones=CRUDAtencionSocial.mostrar_gestiones_por_caso(self.object.usuario_id))
        return contexto

    def guardar(self, form):
        self.object = CRUDAtencionSocial.modificar_gestion(form.instance, self.request.user)

    def get_success_url(self):
        return reverse("social:caso_detail", args=[self.object.usuario_id])


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
