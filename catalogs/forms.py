from django import forms

from core.forms import BootstrapFormMixin

from .models import Catalogo


class CatalogoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Catalogo
        fields = ["codigo", "tipo_catalogo", "nombre", "descripcion", "tipo_atencion_padre", "area", "estado"]
        widgets = {"area": forms.TextInput(attrs={"list": "areas-list", "autocomplete": "off"})}
        help_texts = {"area": "Use «General» para que aplique a todas las áreas."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo_atencion_padre"].queryset = Catalogo.objects.filter(
            tipo_catalogo=Catalogo.TIPO_ATENCION, estado=Catalogo.ESTADO_ACTIVO
        ).order_by("nombre")
        if self.data.get("tipo_catalogo") == Catalogo.TIPO_SUBATENCION or (not self.data and self.instance.tipo_catalogo == Catalogo.TIPO_SUBATENCION if self.instance.pk else False):
            self.fields["tipo_atencion_padre"].required = True
        # Un elemento ya usado en registros no puede cambiar de tipo ni de área
        if self.instance.pk and self.instance.en_uso():
            for campo in ("tipo_catalogo", "area"):
                self.fields[campo].disabled = True
            self.fields["tipo_catalogo"].help_text = "Bloqueado: el elemento ya está en uso en registros."
