from django import forms
from django.utils import timezone

from catalogs.models import Catalogo
from core.forms import BootstrapFormMixin

from .models import AtencionSocial, UsuarioSocial
from .services import TIPOS_CATALOGO_ATENCION


def _catalogo_atencion(area=None, actual=None):
    qs = Catalogo.objects.disponibles(area=area).filter(tipo_catalogo__in=TIPOS_CATALOGO_ATENCION)
    if actual:
        qs = Catalogo.objects.filter(pk=actual) | qs
    return qs


class NuevoCasoForm(BootstrapFormMixin, forms.Form):
    """Alta de un caso: identifica a la persona una sola vez y registra su primera gestión."""
    nombre = forms.CharField(label="Nombre de la persona atendida", max_length=150)
    territorio = forms.CharField(label="Territorio", max_length=150)
    tipo_atencion = forms.ChoiceField(label="Tipo de atención", choices=AtencionSocial.TIPOS)
    catalogo = forms.ModelChoiceField(label="Atención / subatención", queryset=Catalogo.objects.none())
    fecha = forms.DateField(label="Fecha", initial=timezone.localdate,
                            widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    estado = forms.ChoiceField(label="Estado de la gestión", choices=AtencionSocial.ESTADOS,
                               initial=AtencionSocial.ESTADO_REALIZADA)
    resultado = forms.CharField(label="Resultado", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["catalogo"].queryset = _catalogo_atencion(area)

    def clean(self):
        datos = super().clean()
        if datos.get("estado") == AtencionSocial.ESTADO_REALIZADA and not (datos.get("resultado") or "").strip():
            self.add_error("resultado", "Indique el resultado de la gestión realizada.")
        return datos


class CasoForm(BootstrapFormMixin, forms.ModelForm):
    """Edición de los datos de identificación del caso."""
    class Meta:
        model = UsuarioSocial
        fields = ["nombre", "territorio"]


class GestionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AtencionSocial
        fields = ["tipo_atencion", "catalogo", "fecha", "estado", "resultado"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "resultado": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, caso=None, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        usadas = set()
        if caso is not None:
            usadas = set(caso.gestiones.exclude(pk=self.instance.pk).values_list("tipo_atencion", flat=True))
        # Solo se ofrecen tipos aún no usados en el caso (tipos diferenciados, RN-012)
        self.fields["tipo_atencion"].choices = [(v, l) for v, l in AtencionSocial.TIPOS if v not in usadas]
        self.fields["catalogo"].queryset = _catalogo_atencion(area, self.instance.catalogo_id)


class EstadoCasoForm(BootstrapFormMixin, forms.Form):
    estado_caso = forms.ChoiceField(label="Estado del caso", choices=UsuarioSocial.ESTADOS)
