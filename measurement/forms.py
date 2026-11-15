from django import forms

from core.forms import BootstrapFormMixin
from organizations.models import Funcionario, ItemMedible

from .models import Ajuste, Meta as MetaModel, Periodo, maximo_por_defecto, umbral_por_defecto
from decimal import Decimal

class PeriodoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Periodo
        fields = ["fecha_inicio", "fecha_termino"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_termino": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class ReabrirPeriodoForm(BootstrapFormMixin, forms.Form):
    motivo = forms.CharField(label="Motivo de la reapertura", widget=forms.Textarea(attrs={"rows": 3}))


class MetaForm(BootstrapFormMixin, forms.ModelForm):
    aplicar_a_cargo = forms.BooleanField(
        required=False, label="Aplicar a todos los funcionarios activos del mismo cargo",
        help_text="Crea la misma meta para cada funcionario del cargo (omite a quienes ya la tengan).")

    class Meta:
        model = MetaModel
        fields = ["periodo", "funcionario", "item", "valor_objetivo", "unidad",
                  "ponderador", "umbral_minimo", "maximo_computable"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["periodo"].queryset = Periodo.objects.abiertos()
        self.fields["funcionario"].queryset = Funcionario.objects.filter(
            estado=Funcionario.ESTADO_ACTIVO).select_related("cargo")
        self.fields["item"].queryset = ItemMedible.objects.filter(vigencia=True).select_related("cargo")
        if self.instance.pk:
            # Al editar solo cambian valores; funcionario, ítem y período quedan fijos
            for campo in ("periodo", "funcionario", "item"):
                self.fields[campo].disabled = True
                self.fields[campo].queryset = self.fields[campo].queryset.model.objects.all()
            del self.fields["aplicar_a_cargo"]
        else:
            self.fields["umbral_minimo"].initial = umbral_por_defecto()
            self.fields["maximo_computable"].initial = maximo_por_defecto()


class AjusteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Ajuste
        fields = ["periodo", "funcionario", "meta", "efecto", "valor", "motivo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["periodo"].queryset = Periodo.objects.abiertos()
        self.fields["funcionario"].queryset = Funcionario.objects.filter(estado=Funcionario.ESTADO_ACTIVO)
        self.fields["meta"].queryset = MetaModel.objects.select_related("item", "funcionario", "periodo")
        self.fields["meta"].required = False


class ReglasCalculoForm(BootstrapFormMixin, forms.Form):
    """
    Configuración versionada de reglas de cálculo.
    Los cambios se aplican desde el momento de su registro.
    """

    tope_cumplimiento = forms.DecimalField(
        label="Tope máximo de cumplimiento (%)",
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("0.01"),
        initial=150,
    )

    umbral_colectivo = forms.DecimalField(
        label="Umbral colectivo (%)",
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        initial=60,
    )

    umbral_ambar = forms.DecimalField(
        label="Umbral del semáforo ámbar (%)",
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        initial=60,
    )
