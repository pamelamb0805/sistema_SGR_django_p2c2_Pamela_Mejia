from django import forms
from django.db.models import Q
from django.utils import timezone

from core.forms import BootstrapFormMixin
from organizations.models import ItemMedible

from .models import Compromiso
from .services import funcionarios_asignables


class CompromisoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Compromiso
        fields = ["origen", "solicitante", "territorio", "fecha_comprometida", "funcionario",
                  "area_apoyo", "item_medible", "observacion"]
        widgets = {
            "fecha_comprometida": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacion": forms.Textarea(attrs={"rows": 3}),
            "origen": forms.TextInput(attrs={"list": "origenes-list", "autocomplete": "off"}),
        }
        help_texts = {"item_medible": "Opcional. Si lo indica, al realizarse el compromiso aporta a ese ítem."}

    ORIGENES = ["Solicitud interna", "Solicitud externa", "Solicitud vecinal"]

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].label = "Responsable"
        self.fields["funcionario"].queryset = funcionarios_asignables(usuario)
        items = ItemMedible.objects.filter(vigencia=True).select_related("cargo")
        if self.instance.pk and self.instance.item_medible_id:
            items = ItemMedible.objects.filter(Q(pk=self.instance.item_medible_id) | Q(pk__in=items.values("pk")))
        self.fields["item_medible"].queryset = items
        self.fields["fecha_comprometida"].widget.attrs["min"] = timezone.localdate().isoformat()
        if self.instance.pk:
            # El responsable solo cambia mediante «Reasignar» (queda registrado el motivo)
            self.fields["funcionario"].disabled = True
            self.fields["funcionario"].queryset = type(self.instance.funcionario).objects.all()
        elif usuario is not None and self.fields["funcionario"].queryset.count() == 1:
            self.fields["funcionario"].initial = self.fields["funcionario"].queryset.first().pk


class EstadoForm(BootstrapFormMixin, forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado")
    observacion = forms.CharField(label="Observación de avance", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, compromiso=None, **kwargs):
        super().__init__(*args, **kwargs)
        permitidos = Compromiso.TRANSICIONES.get(compromiso.estado, ()) if compromiso else ()
        self.fields["estado"].choices = [(e, e) for e in permitidos]


class ReasignarForm(BootstrapFormMixin, forms.Form):
    funcionario = forms.ModelChoiceField(label="Nuevo responsable", queryset=None)
    motivo = forms.CharField(label="Motivo de la reasignación", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, usuario=None, compromiso=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = funcionarios_asignables(usuario)
        if compromiso is not None:
            qs = qs.exclude(pk=compromiso.funcionario_id)
        self.fields["funcionario"].queryset = qs
