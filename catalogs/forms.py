from django import forms

from core.forms import BootstrapFormMixin

from .models import Catalogo


class CatalogoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Catalogo
        fields = ["tipo_catalogo", "nombre", "area", "estado"]
        widgets = {"area": forms.TextInput(attrs={"list": "areas-list", "autocomplete": "off"})}
        help_texts = {"area": "Use «General» para que aplique a todas las áreas."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un elemento ya usado en registros no puede cambiar de tipo ni de área
        if self.instance.pk and self.instance.en_uso():
            for campo in ("tipo_catalogo", "area"):
                self.fields[campo].disabled = True
            self.fields["tipo_catalogo"].help_text = "Bloqueado: el elemento ya está en uso en registros."
