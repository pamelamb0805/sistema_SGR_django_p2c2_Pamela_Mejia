from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from catalogs.models import Catalogo
from core.exceptions import ReglaNegocioError
from core.forms import BootstrapFormMixin
from organizations.models import ItemMedible

from .models import Actividad, Validacion
from .services import TIPOS_CATALOGO_ACTIVIDAD, CRUDEvidencia


class ActividadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Actividad
        fields = ["fecha", "tipo_registro", "catalogo", "item", "accion", "contacto", "telefono",
                  "ingreso_agenda_colectiva"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "accion": forms.Textarea(attrs={"rows": 3}),
            "telefono": forms.TextInput(attrs={"type": "tel", "placeholder": "+56 9 1234 5678"}),
        }

    def __init__(self, *args, funcionario=None, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        actual_item = self.instance.item_id if self.instance.pk else None
        actual_catalogo = self.instance.catalogo_id if self.instance.pk else None

        # Solo los ítems vigentes del cargo del funcionario (RF-003)
        items = ItemMedible.objects.filter(vigencia=True, cargo_id=funcionario.cargo_id) if funcionario \
            else ItemMedible.objects.none()
        if actual_item:
            items = ItemMedible.objects.filter(Q(pk=actual_item) | Q(pk__in=items.values("pk")))
        self.fields["item"].queryset = items

        # Solo catálogo activo y aplicable al área (HU-27)
        catalogo = Catalogo.objects.disponibles(area=area).filter(tipo_catalogo__in=TIPOS_CATALOGO_ACTIVIDAD)
        if actual_catalogo:
            catalogo = Catalogo.objects.filter(Q(pk=actual_catalogo) | Q(pk__in=catalogo.values("pk")))
        self.fields["catalogo"].queryset = catalogo


class EvidenciaForm(BootstrapFormMixin, forms.Form):
    archivo = forms.FileField(
        label="Fotografía o archivo de respaldo",
        widget=forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}))

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        try:
            CRUDEvidencia.validar_formato_archivo(archivo)
        except ReglaNegocioError as exc:
            raise ValidationError(str(exc))
        return archivo


class ValidacionForm(BootstrapFormMixin, forms.Form):
    decision = forms.ChoiceField(label="Decisión", choices=Validacion.DECISIONES)
    observacion = forms.CharField(label="Observación", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        datos = super().clean()
        if datos.get("decision") and datos["decision"] != Validacion.DECISION_APROBADA \
                and not (datos.get("observacion") or "").strip():
            self.add_error("observacion", "La observación es obligatoria al rechazar o solicitar corrección.")
        return datos


class AnularForm(BootstrapFormMixin, forms.Form):
    motivo = forms.CharField(label="Motivo de la anulación", widget=forms.Textarea(attrs={"rows": 3}))
