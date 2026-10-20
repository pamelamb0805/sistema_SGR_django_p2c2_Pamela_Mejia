#Formulario de archivar dispositivos
#correccion eva2-n3
from django import forms
from .models import Device


class ArchiveDevicesForm(forms.Form):
    """Valida que los dispositivos elegidos pertenezcan al ámbito del usuario."""

    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.none(),
        label="Dispositivos a archivar",
    )

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo acepta IDs que estén en el queryset ya acotado por organización
        if queryset is not None:
            self.fields["devices"].queryset = queryset