from django import forms

from core.forms import BootstrapFormMixin
from organizations.models import Funcionario

from .models import Auditoria


class AuditoriaFiltroForm(BootstrapFormMixin, forms.Form):
    """Filtros de consulta y exportación (se envían por GET)."""
    evento = forms.ChoiceField(label="Evento", required=False)
    entidad = forms.ChoiceField(label="Entidad", required=False)
    id_entidad = forms.IntegerField(label="ID de la entidad", required=False, min_value=0)
    funcionario = forms.ModelChoiceField(label="Usuario", required=False, queryset=Funcionario.objects.none(),
                                         empty_label="Todos")
    fecha_desde = forms.DateField(label="Desde", required=False,
                                  widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    fecha_hasta = forms.DateField(label="Hasta", required=False,
                                  widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    q = forms.CharField(label="Texto en los valores", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        eventos = Auditoria.objects.order_by("evento").values_list("evento", flat=True).distinct()
        entidades = Auditoria.objects.exclude(entidad_afectada="").order_by("entidad_afectada") \
            .values_list("entidad_afectada", flat=True).distinct()
        self.fields["evento"].choices = [("", "Todos")] + [(e, e) for e in eventos]
        self.fields["entidad"].choices = [("", "Todas")] + [(e, e) for e in entidades]
        self.fields["funcionario"].queryset = Funcionario.objects.filter(
            pk__in=Auditoria.objects.exclude(funcionario=None).values("funcionario_id"))

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("fecha_desde"), datos.get("fecha_hasta")
        if desde and hasta and hasta < desde:
            self.add_error("fecha_hasta", "La fecha final no puede ser anterior a la inicial.")
        return datos


class ComentarioRegistroForm(forms.Form):
    mensaje = forms.CharField(
        label="Comentario",
        required=True,
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": (
                    "Escriba una observación, consulta "
                    "o respuesta relacionada con este registro..."
                ),
            }
        ),
    )

    respuesta_a = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_mensaje(self):
        mensaje = (self.cleaned_data.get("mensaje") or "").strip()

        if not mensaje:
            raise forms.ValidationError(
                "Debe escribir un comentario."
            )

        if len(mensaje) > 5000:
            raise forms.ValidationError(
                "El comentario no puede superar los 5000 caracteres."
            )

        return mensaje
