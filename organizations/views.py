"""
Vistas de organizations.
- Lectura: Administrador, Coordinador y Delegado (este último solo su delegación).
- Escritura: solo Administrador (RF-001, RF-002, RF-003).
Cada entidad usa UNA plantilla (templates/organization/<entidad>_.html) con
la variable `modo`: 'lista', 'form' o 'detalle'.
"""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.exceptions import ReglaNegocioError
from core.mixins import (
    ROLES_CONFIGURACION, ROLES_SUPERVISION, AccionPostView, AmbitoDelegacionMixin, GuardarMixin,
    ModoMixin, RolRequeridoMixin, errores_form as _errores,
)
from core.mixins import ModalFormPageMixin

from .forms import AccesoForm, CargoForm, DelegacionForm, FuncionarioForm, ItemMedibleForm, RolForm, UsuarioAdminForm
from .models import Cargo, Delegacion, Funcionario, ItemMedible, Rol, Usuario
from .services import CRUDCargo, CRUDDelegacion, CRUDFuncionario, CRUDRol, Seguridad


# ---------------------------------------------------------------------------
# Bloques reutilizables
# ---------------------------------------------------------------------------
class LecturaMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_SUPERVISION


class EscrituraMixin(RolRequeridoMixin):
    roles_permitidos = ROLES_CONFIGURACION


# ---------------------------------------------------------------------------
# Delegaciones
# ---------------------------------------------------------------------------
class DelegacionListView(LecturaMixin, AmbitoDelegacionMixin, ModoMixin, ListView):
    model = Delegacion
    template_name = "organization/delegacion_.html"
    context_object_name = "delegaciones"
    ambito_campo = "id_delegacion"
    paginate_by = 10
    titulo = "Delegaciones"

    def get_queryset(self):
        qs = super().get_queryset()
        q, estado = self.request.GET.get("q", "").strip(), self.request.GET.get("estado", "")
        if q:
            qs = qs.filter(Q(codigo__icontains=q) | Q(nombre__icontains=q) | Q(direccion__icontains=q) | Q(comuna__icontains=q) | Q(ambito__icontains=q))
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(q=self.request.GET.get("q", ""), estado_sel=self.request.GET.get("estado", ""),
                        total_resultados=self.get_queryset().count(), estados=Delegacion.ESTADOS)
        return contexto


class DelegacionCreateView(
    EscrituraMixin,
    ModalFormPageMixin,
    ModoMixin,
    GuardarMixin,
    CreateView,
):
    model = Delegacion
    form_class = DelegacionForm
    template_name = "organization/delegacion_.html"
    modo, titulo = "form", "Nueva delegación"
    success_url_name = "organizations:delegacion_list"
    mensaje_exito = "Delegación creada y disponible en filtros y asignaciones."
    list_view_class = DelegacionListView

    def guardar(self, form):
        self.object = CRUDDelegacion.crear_delegacion(
            form.instance, self.request.user
        )


class DelegacionUpdateView(
    EscrituraMixin,
    ModalFormPageMixin,
    ModoMixin,
    GuardarMixin,
    UpdateView,
):
    model = Delegacion
    form_class = DelegacionForm
    template_name = "organization/delegacion_.html"
    modo, titulo = "form", "Editar delegación"
    success_url_name = "organizations:delegacion_list"
    mensaje_exito = "Delegación actualizada."
    list_view_class = DelegacionListView

    def guardar(self, form):
        self.object = CRUDDelegacion.modificar_delegacion(
            form.instance, self.request.user
        )

class DelegacionToggleView(AccionPostView):
    redirect_name = "organizations:delegacion_list"

    def get_objeto(self, pk):
        return get_object_or_404(Delegacion, pk=pk)

    def accion(self, request, objeto):
        CRUDDelegacion.activar_desactivar_delegacion(objeto, request.user)
        return f"Delegación «{objeto.nombre}» {'activada' if objeto.activa else 'desactivada'}."


# ---------------------------------------------------------------------------
# Cargos e ítems medibles
# ---------------------------------------------------------------------------
class CargoListView(LecturaMixin, ModoMixin, ListView):
    model = Cargo
    template_name = "organization/cargo_.html"
    context_object_name = "cargos"
    paginate_by = 10
    titulo = "Cargos y funciones"

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("items")
        q = self.request.GET.get("q", "").strip()
        return qs.filter(nombre_cargo__icontains=q) if q else qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "")
        return contexto


class CargoDetailView(LecturaMixin, ModoMixin, DetailView):
    """Muestra los ítems del cargo y permite agregar nuevos (RF-003)."""
    model = Cargo
    template_name = "organization/cargo_.html"
    context_object_name = "cargo"
    modo = "detalle"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = f"Cargo: {self.object.nombre_cargo}"
        contexto["items"] = self.object.items.all()
        contexto["item_form"] = ItemMedibleForm()
        return contexto


class CargoCreateView(EscrituraMixin, ModalFormPageMixin, ModoMixin, GuardarMixin, CreateView):
    model = Cargo
    form_class = CargoForm
    template_name = "organization/cargo_.html"
    modo, titulo = "form", "Nuevo cargo"
    success_url_name = "organizations:cargo_list"
    mensaje_exito = "Cargo creado."
    list_view_class = CargoListView

    def guardar(self, form):
        self.object = CRUDCargo.crear_cargo(form.instance, self.request.user)

    def get_success_url(self):
        return reverse("organizations:cargo_detail", args=[self.object.pk])


class CargoUpdateView(EscrituraMixin, ModalFormPageMixin, ModoMixin, GuardarMixin, UpdateView):
    model = Cargo
    form_class = CargoForm
    template_name = "organization/cargo_.html"
    modo, titulo = "form", "Editar cargo"
    success_url_name = "organizations:cargo_list"
    mensaje_exito = "Cargo actualizado."
    list_view_class = CargoListView

    def guardar(self, form):
        self.object = CRUDCargo.modificar_cargo(form.instance, self.request.user)


class CargoDeleteView(AccionPostView):
    redirect_name = "organizations:cargo_list"

    def get_objeto(self, pk):
        return get_object_or_404(Cargo, pk=pk)

    def accion(self, request, objeto):
        CRUDCargo.eliminar_cargo(objeto, request.user)
        return "Cargo eliminado."

    def get_redirect(self, objeto):
        # Si falló, volver al detalle; si se eliminó, a la lista
        return reverse("organizations:cargo_list") if not Cargo.objects.filter(pk=objeto.pk).exists() \
            else reverse("organizations:cargo_detail", args=[objeto.pk])


class ItemCreateView(EscrituraMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        cargo = get_object_or_404(Cargo, pk=pk)
        form = ItemMedibleForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.cargo = cargo
            try:
                CRUDCargo.asociar_funcion_al_cargo(item, request.user)
                messages.success(request, "Ítem medible asociado al cargo.")
            except ReglaNegocioError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, _errores(form))
        return redirect("organizations:cargo_detail", pk=cargo.pk)


class ItemToggleView(AccionPostView):
    def get_objeto(self, pk):
        return get_object_or_404(ItemMedible, pk=pk)

    def accion(self, request, objeto):
        CRUDCargo.cambiar_vigencia_item(objeto, request.user)
        return f"Ítem «{objeto.nombre_item}» {'vigente' if objeto.vigencia else 'no vigente'}."

    def get_redirect(self, objeto):
        return reverse("organizations:cargo_detail", args=[objeto.cargo_id])


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
class RolListView(LecturaMixin, ModoMixin, ListView):
    model = Rol
    template_name = "organization/rol_.html"
    context_object_name = "roles"
    titulo = "Roles"


class RolCreateView(EscrituraMixin,ModalFormPageMixin, ModoMixin, GuardarMixin, CreateView):
    model = Rol
    form_class = RolForm
    template_name = "organization/rol_.html"
    modo, titulo = "form", "Nuevo rol"
    success_url_name = "organizations:rol_list"
    mensaje_exito = "Rol creado."
    list_view_class = RolListView

    def guardar(self, form):
        self.object = CRUDRol.crear_rol(form.instance, self.request.user)


class RolUpdateView(EscrituraMixin,ModalFormPageMixin, ModoMixin, GuardarMixin, UpdateView):
    model = Rol
    form_class = RolForm
    template_name = "organization/rol_.html"
    modo, titulo = "form", "Editar rol"
    success_url_name = "organizations:rol_list"
    mensaje_exito = "Rol actualizado."
    list_view_class = RolListView

    def guardar(self, form):
        self.object = CRUDRol.modificar_rol(form.instance, self.request.user)


class RolDeleteView(AccionPostView):
    redirect_name = "organizations:rol_list"

    def get_objeto(self, pk):
        return get_object_or_404(Rol, pk=pk)

    def accion(self, request, objeto):
        CRUDRol.eliminar_rol(objeto, request.user)
        return "Rol eliminado."


# ---------------------------------------------------------------------------
# Funcionarios
# ---------------------------------------------------------------------------
class FuncionarioListView(LecturaMixin, AmbitoDelegacionMixin, ModoMixin, ListView):
    model = Funcionario
    template_name = "organization/funcionario_.html"
    context_object_name = "funcionarios"
    ambito_campo = "delegacion_id"
    paginate_by = 10
    titulo = "Funcionarios"

    def get_queryset(self):
        qs = super().get_queryset().select_related("cargo", "delegacion") \
            .prefetch_related("funcionario_roles__rol")
        g = self.request.GET
        if g.get("q", "").strip():
            q = g["q"].strip()
            qs = qs.filter(Q(nombre__icontains=q) | Q(identificador_institucional__icontains=q))
        if g.get("delegacion"):
            qs = qs.filter(delegacion_id=g["delegacion"])
        if g.get("cargo"):
            qs = qs.filter(cargo_id=g["cargo"])
        if g.get("estado"):
            qs = qs.filter(estado=g["estado"])
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        g = self.request.GET
        contexto.update(
            q=g.get("q", ""), delegacion_sel=g.get("delegacion", ""),
            cargo_sel=g.get("cargo", ""), estado_sel=g.get("estado", ""),
            delegaciones=Delegacion.objects.all(), cargos=Cargo.objects.all(),
            estados=Funcionario.ESTADOS,
        )
        return contexto


class FuncionarioDetailView(LecturaMixin, AmbitoDelegacionMixin, ModoMixin, DetailView):
    model = Funcionario
    template_name = "organization/funcionario_.html"
    context_object_name = "funcionario"
    ambito_campo = "delegacion_id"
    modo = "detalle"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = getattr(self.object, "usuario", None)
        contexto.update(
            titulo=f"Funcionario: {self.object.nombre}",
            roles_asignados=self.object.funcionario_roles.select_related("rol"),
            usuario_acceso=usuario,
            acceso_form=AccesoForm(usuario=usuario),
        )
        return contexto


class FuncionarioCreateView(EscrituraMixin,  ModalFormPageMixin, ModoMixin, GuardarMixin, CreateView):
    model = Funcionario
    form_class = FuncionarioForm
    template_name = "organization/funcionario_.html"
    modo, titulo = "form", "Nuevo funcionario"
    success_url_name = "organizations:funcionario_list"
    mensaje_exito = "Funcionario registrado."
    list_view_class = FuncionarioListView

    def guardar(self, form):
        self.object = CRUDFuncionario.crear_funcionario(
            form.instance, form.cleaned_data["roles"], self.request.user)

    def get_success_url(self):
        return reverse("organizations:funcionario_detail", args=[self.object.pk])


class FuncionarioUpdateView(EscrituraMixin, ModalFormPageMixin, ModoMixin, GuardarMixin, UpdateView):
    model = Funcionario
    form_class = FuncionarioForm
    template_name = "organization/funcionario_.html"
    modo, titulo = "form", "Editar funcionario"
    success_url_name = "organizations:funcionario_list"
    mensaje_exito = "Funcionario actualizado."
    list_view_class = FuncionarioListView

    def guardar(self, form):
        self.object = CRUDFuncionario.modificar_funcionario(
            form.instance, form.cleaned_data["roles"], self.request.user)

    def get_success_url(self):
        return reverse("organizations:funcionario_detail", args=[self.object.pk])


class FuncionarioToggleView(AccionPostView):
    redirect_name = "organizations:funcionario_list"

    def get_objeto(self, pk):
        return get_object_or_404(Funcionario, pk=pk)

    def accion(self, request, objeto):
        CRUDFuncionario.cambiar_estado(objeto, request.user)
        return f"Funcionario «{objeto.nombre}» {'activado' if objeto.activo else 'desactivado'}."



class FuncionarioAccesoView(EscrituraMixin, View):
    """Crea el acceso de un funcionario o actualiza sus credenciales."""
    http_method_names = ["post"]

    def post(self, request, pk):
        funcionario = get_object_or_404(Funcionario, pk=pk)
        usuario = getattr(funcionario, "usuario", None)

        form = AccesoForm(request.POST, usuario=usuario)

        if form.is_valid():
            try:
                if usuario:
                    # Actualizar el correo y las delegaciones autorizadas.
                    email = form.cleaned_data["email"].strip().lower()
                    delegaciones = form.cleaned_data[
                        "delegaciones_autorizadas"
                    ]

                    if Usuario.objects.filter(
                        email__iexact=email
                    ).exclude(pk=usuario.pk).exists():
                        raise ReglaNegocioError(
                            "Ese correo electrónico ya está registrado."
                        )

                    usuario.email = email
                    usuario.delegaciones_autorizadas.set(delegaciones)
                    usuario.save(update_fields=["email"])

                    # Cambiar la contraseña solo si se ingresó una.
                    password = form.cleaned_data.get("password1")
                    if password:
                        Seguridad.cambiar_contrasenia(
                            usuario,
                            password,
                            request.user,
                        )

                    messages.success(
                        request,
                        "Acceso actualizado correctamente.",
                    )

                else:
                    # Crear el acceso del funcionario.
                    usuario = Seguridad.crear_usuario(
                        funcionario,
                        form.cleaned_data["username"],
                        form.cleaned_data["password1"],
                        request.user,
                        email=form.cleaned_data["email"],
                        delegaciones=form.cleaned_data[
                            "delegaciones_autorizadas"
                        ],
                    )

                    messages.success(
                        request,
                        "Acceso creado correctamente.",
                    )

            except ReglaNegocioError as exc:
                messages.error(request, str(exc))

        else:
            messages.error(request, _errores(form))

        return redirect(
            "organizations:funcionario_detail",
            pk=funcionario.pk,
        )


class UsuarioListView(EscrituraMixin, ListView):
    model = Usuario
    template_name = "organization/usuario_.html"
    context_object_name = "usuarios"
    paginate_by = 15

    def get_queryset(self):
        queryset = (
            Usuario.objects
            .select_related("funcionario")
            .prefetch_related("delegaciones_autorizadas")
            .order_by("username")
        )

        q = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "").strip()

        if q:
            queryset = queryset.filter(
                Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(funcionario__nombre__icontains=q)
            )

        if estado == "ACTIVO":
            queryset = queryset.filter(
                activo_acceso=True,
                funcionario__activo=True,
            )
        elif estado == "INACTIVO":
            queryset = queryset.filter(
                Q(activo_acceso=False)
                | Q(funcionario__activo=False)
                | Q(funcionario__isnull=True)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "q": self.request.GET.get("q", ""),
            "estado_sel": self.request.GET.get("estado", ""),
            "estados": [
                ("ACTIVO", "Activo"),
                ("INACTIVO", "Inactivo o pendiente"),
            ],
            "titulo": "Usuarios",
        })
        return context


class UsuarioCreateView(
    EscrituraMixin,
    ModalFormPageMixin,
    ModoMixin,
    GuardarMixin,
    CreateView,
):
    model = Usuario
    form_class = UsuarioAdminForm
    template_name = "organization/usuario_.html"
    modo, titulo = "form", "Crear usuario"
    success_url_name = "organizations:usuario_list"
    mensaje_exito = "Usuario creado correctamente."
    list_view_class = UsuarioListView

    def guardar(self, form):
        self.object = Seguridad.guardar_usuario(
            form,
            self.request.user,
        )


class UsuarioUpdateView(
    EscrituraMixin,
    ModalFormPageMixin,
    ModoMixin,
    GuardarMixin,
    UpdateView,
):
    model = Usuario
    form_class = UsuarioAdminForm
    template_name = "organization/usuario_.html"
    modo, titulo = "Editar usuario"
    success_url_name = "organizations:usuario_list"
    mensaje_exito = "Usuario actualizado correctamente."
    list_view_class = UsuarioListView

    def guardar(self, form):
        self.object = Seguridad.guardar_usuario(
            form,
            self.request.user,
        )


class UsuarioToggleView(EscrituraMixin, AccionPostView):
    redirect_name = "organizations:usuario_list"

    def get_objeto(self, pk):
        return get_object_or_404(Usuario, pk=pk)

    def accion(self, request, objeto):
        Seguridad.cambiar_estado_acceso(objeto, request.user)

        return (
            f"Acceso de {objeto.username} "
            f"{'habilitado' if objeto.activo_acceso else 'deshabilitado'}."
        )