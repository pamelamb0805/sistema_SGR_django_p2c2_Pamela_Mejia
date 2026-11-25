from django import forms

from core.forms import BootstrapFormMixin

from .models import Catalogo


class CatalogoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Catalogo
        fields = [
            "codigo",
            "tipo_catalogo",
            "nombre",
            "descripcion",
            "tipo_atencion_padre",
            "area",
            "estado",
        ]
        widgets = {
            "area": forms.TextInput(
                attrs={
                    "list": "areas-list",
                    "autocomplete": "off",
                }
            )
        }
        help_texts = {
            "area": "Use «General» para que aplique a todas las áreas."
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        padres = Catalogo.objects.filter(
            tipo_catalogo=Catalogo.TIPO_ATENCION,
            estado=Catalogo.ESTADO_ACTIVO,
        )

        # En edición, conserva la relación histórica actual aunque
        # el padre haya sido desactivado posteriormente.
        if self.instance.pk and self.instance.tipo_atencion_padre_id:
            padres = (
                padres
                | Catalogo.objects.filter(
                    pk=self.instance.tipo_atencion_padre_id
                )
            ).distinct()

        self.fields["tipo_atencion_padre"].queryset = padres.order_by(
            "nombre"
        )

        tipo_actual = (
            self.data.get("tipo_catalogo")
            if self.is_bound
            else self.instance.tipo_catalogo
        )

        self.fields["tipo_atencion_padre"].required = (
            tipo_actual == Catalogo.TIPO_SUBATENCION
        )

        if self.instance.pk and self.instance.en_uso():
            for campo in ("tipo_catalogo", "area"):
                self.fields[campo].disabled = True

            self.fields["tipo_catalogo"].help_text = (
                "Bloqueado: el elemento ya está en uso en registros."
            )