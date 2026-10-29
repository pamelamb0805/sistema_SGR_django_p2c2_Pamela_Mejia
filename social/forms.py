
from django import forms
from django.utils import timezone

from catalogs.models import Catalogo
from core.forms import BootstrapFormMixin

from .models import AtencionSocial, UsuarioSocial


def _tipos_atencion(area=None):
    return Catalogo.objects.disponibles(
        area=area,
        tipo=Catalogo.TIPO_ATENCION,
    ).order_by("nombre")


def _subatenciones(tipo_id=None, area=None, actual=None):
    qs = Catalogo.objects.disponibles(
        area=area,
        tipo=Catalogo.TIPO_SUBATENCION,
    )

    if tipo_id:
        qs = qs.filter(tipo_atencion_padre_id=tipo_id)
    else:
        qs = qs.none()

    # En edición se puede conservar un valor antiguo para mostrarlo,
    # pero la validación del formulario impedirá guardar uno inactivo.
    if actual:
        qs = (Catalogo.objects.filter(pk=actual) | qs).distinct()

    return qs.order_by("nombre")


class SeleccionAtencionMixin:
    """Configura y valida el par Tipo de Atención/Subatención."""

    def configurar_atencion(self, area=None, datos=None, instancia=None):
        datos = datos or {}
        tipo_id = (
            datos.get("tipo_atencion")
            or getattr(instancia, "tipo_atencion_id", None)
        )

        self.fields["tipo_atencion"].queryset = _tipos_atencion(area)
        self.fields["subatencion"].queryset = _subatenciones(
            tipo_id=tipo_id,
            area=area,
            actual=getattr(instancia, "subatencion_id", None),
        )

    def clean(self):
        datos = super().clean()
        tipo = datos.get("tipo_atencion")
        subatencion = datos.get("subatencion")

        if tipo and tipo.tipo_catalogo != Catalogo.TIPO_ATENCION:
            self.add_error(
                "tipo_atencion",
                "Seleccione un Tipo de Atención válido.",
            )

        if subatencion:
            if subatencion.tipo_catalogo != Catalogo.TIPO_SUBATENCION:
                self.add_error(
                    "subatencion",
                    "Seleccione una Subatención válida.",
                )
            elif not subatencion.activo:
                self.add_error(
                    "subatencion",
                    "La Subatención seleccionada está inactiva.",
                )
            elif tipo and subatencion.tipo_atencion_padre_id != tipo.pk:
                self.add_error(
                    "subatencion",
                    "La Subatención debe pertenecer al Tipo de Atención seleccionado.",
                )

        if tipo and not tipo.activo:
            self.add_error(
                "tipo_atencion",
                "El Tipo de Atención seleccionado está inactivo.",
            )

        return datos


class NuevoCasoForm(
    SeleccionAtencionMixin,
    BootstrapFormMixin,
    forms.Form,
):
    """Registra una persona y su primera gestión."""

    nombre = forms.CharField(
        label="Nombre de la persona atendida",
        max_length=150,
    )
    territorio = forms.CharField(
        label="Territorio",
        max_length=150,
    )
    tipo_atencion = forms.ModelChoiceField(
        label="Tipo de Atención",
        queryset=Catalogo.objects.none(),
    )
    subatencion = forms.ModelChoiceField(
        label="Subatención",
        queryset=Catalogo.objects.none(),
    )
    descripcion = forms.CharField(
        label="Descripción de la atención",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    fecha = forms.DateField(
        label="Fecha de la gestión",
        initial=timezone.localdate,
        widget=forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        ),
    )
    estado = forms.ChoiceField(
        label="Estado de la gestión",
        choices=AtencionSocial.ESTADOS,
        initial=AtencionSocial.ESTADO_REALIZADA,
    )
    resultado = forms.CharField(
        label="Resultado",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.configurar_atencion(
            area=area,
            datos=self.data if self.is_bound else None,
        )

    def clean(self):
        datos = super().clean()

        if (
            datos.get("estado") == AtencionSocial.ESTADO_REALIZADA
            and not (datos.get("resultado") or "").strip()
        ):
            self.add_error(
                "resultado",
                "Indique el resultado de la gestión realizada.",
            )

        return datos


class CasoForm(BootstrapFormMixin, forms.ModelForm):
    """Edición de los datos de identificación del caso."""

    class Meta:
        model = UsuarioSocial
        fields = ["nombre", "territorio"]


class GestionForm(
    SeleccionAtencionMixin,
    BootstrapFormMixin,
    forms.ModelForm,
):
    class Meta:
        model = AtencionSocial
        fields = [
            "tipo_atencion",
            "subatencion",
            "descripcion",
            "fecha",
            "estado",
            "resultado",
        ]
        widgets = {
            "fecha": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "resultado": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, caso=None, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.caso = caso

        self.configurar_atencion(
            area=area,
            datos=self.data if self.is_bound else None,
            instancia=self.instance,
        )

        if caso is not None:
            usadas = caso.gestiones.exclude(
                pk=self.instance.pk
            ).values_list("tipo_atencion_id", flat=True)

            self.fields["tipo_atencion"].queryset = (
                self.fields["tipo_atencion"].queryset.exclude(
                    pk__in=usadas
                )
                | Catalogo.objects.filter(
                    pk=self.instance.tipo_atencion_id
                )
            ).distinct()


class EstadoCasoForm(BootstrapFormMixin, forms.Form):
    estado_caso = forms.ChoiceField(
        label="Estado del caso",
        choices=UsuarioSocial.ESTADOS,
    )
