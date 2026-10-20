"""
Vistas de catalogs. Plantilla única: templates/catalogs/catalogo_.html (variable `modo`).
- Lectura del listado: Administrador, Coordinador y Delegado.
- Escritura: solo Administrador (HU-27).
- API por área: cualquier usuario autenticado (alimenta los formularios de registro).
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import (
    ROLES_CONFIGURACION, ROLES_SUPERVISION, AccionPostView, GuardarMixin, ModoMixin, RolRequeridoMixin,
)

from .forms import CatalogoForm
from .models import Catalogo
from .services import CRUDCatalogo


class LecturaMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_SUPERVISION


class EscrituraMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_CONFIGURACION


def _areas():
    return list(Catalogo.objects.order_by("area").values_list("area", flat=True).distinct())


class CatalogoListView(LecturaMixin, ModoMixin, ListView):
    model = Catalogo
    template_name = "catalogs/catalogo_.html"
    context_object_name = "elementos"
    paginate_by = 15
    titulo = "Catálogos de actividades y servicios"

    def get_queryset(self):
        qs = super().get_queryset()
        g = self.request.GET
        if g.get("q", "").strip():
            qs = qs.filter(nombre__icontains=g["q"].strip())
        for campo in ("tipo_catalogo", "area", "estado"):
            if g.get(campo):
                qs = qs.filter(**{campo: g[campo]})
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        g = self.request.GET
        contexto.update(
            q=g.get("q", ""), tipo_sel=g.get("tipo_catalogo", ""), area_sel=g.get("area", ""),
            estado_sel=g.get("estado", ""), tipos=Catalogo.TIPOS, estados=Catalogo.ESTADOS, areas=_areas(),
        )
        return contexto


class CatalogoFormMixin(EscrituraMixin, ModoMixin, GuardarMixin):
    model = Catalogo
    form_class = CatalogoForm
    template_name = "catalogs/catalogo_.html"
    modo = "form"
    success_url_name = "catalogs:catalogo_list"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["areas"] = _areas()
        return contexto


class CatalogoCreateView(CatalogoFormMixin, CreateView):
    titulo = "Nuevo elemento de catálogo"
    mensaje_exito = "Elemento creado."

    def guardar(self, form):
        self.object = CRUDCatalogo.crear_elemento_catalogo(form.instance, self.request.user)


class CatalogoUpdateView(CatalogoFormMixin, UpdateView):
    titulo = "Editar elemento de catálogo"
    mensaje_exito = "Elemento actualizado. Los registros históricos no se alteran."

    def guardar(self, form):
        self.object = CRUDCatalogo.modificar_elemento_catalogo(form.instance, self.request.user)


class CatalogoToggleView(AccionPostView):
    redirect_name = "catalogs:catalogo_list"

    def get_objeto(self, pk):
        return get_object_or_404(Catalogo, pk=pk)

    def accion(self, request, objeto):
        if objeto.activo:
            CRUDCatalogo.desactivar_elemento_catalogo(objeto, request.user)
            return f"«{objeto.nombre}» desactivado: no se ofrecerá en registros nuevos."
        CRUDCatalogo.activar_elemento_catalogo(objeto, request.user)
        return f"«{objeto.nombre}» activado."


@login_required
def catalogo_por_area(request):
    """JSON con los elementos activos aplicables a un área: /catalogs/api/por-area/?area=Social&tipo=Actividad"""
    elementos = CRUDCatalogo.mostrar_catalogo_por_area(
        request.GET.get("area") or None, request.GET.get("tipo") or None)
    return JsonResponse({"resultados": [
        {"id": e.pk, "nombre": e.nombre, "tipo": e.tipo_catalogo, "area": e.area} for e in elementos
    ]})
