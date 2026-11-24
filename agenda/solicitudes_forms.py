
from django import forms
from django.utils import timezone

from core.forms import BootstrapFormMixin
from organizations.models import Delegacion

from .models import Compromiso
from .solicitudes_services import (
    normalizar_rut,
    rut_valido,
    tutor_registrado,
)


class SolicitudVecinalForm(
    BootstrapFormMixin,
    forms.Form,
):

    nombre_solicitante = forms.CharField(
        max_length=150,
        required=False,
        label="Nombre del vecino",
    )

    rut_solicitante = forms.CharField(
        max_length=12,
        label="RUT del vecino",
        help_text="Ejemplo: 12.345.678-5",
        widget=forms.TextInput(attrs={
            "placeholder": "12.345.678-5",
            "inputmode": "text",
            "pattern": r"[0-9Kk.\-]+",
            "title": "Ingrese un RUT chileno válido.",
            "maxlength": "12",
            "autocomplete": "off",
        }),
    )

    relacion_vecinal = forms.ChoiceField(
        choices=Compromiso.RELACIONES_VECINALES,
        label="Relación con la junta de vecinos",
    )

    delegacion = forms.ModelChoiceField(
        queryset=Delegacion.objects.none(),
        required=False,
        label="Delegación municipal",
    )

    territorio = forms.CharField(
        max_length=150,
        required=False,
        label="Sector o territorio",
    )

    categoria_solicitud = forms.ChoiceField(
        choices=[
            ("Social", "Social"),
            (
                "Organizaciones Comunitarias",
                "Organizaciones comunitarias",
            ),
            ("Aseo", "Aseo"),
            ("Ornato", "Ornato"),
            ("Espacios públicos", "Espacios públicos"),
            (
                "Servicios comunitarios",
                "Servicios comunitarios",
            ),
            ("Otra", "Otra"),
        ],
        label="Área de la solicitud",
    )

    tipo_solicitud = forms.ChoiceField(
        choices=Compromiso.TIPOS_SOLICITUD,
        label="Tipo de solicitud",
    )

    descripcion_solicitud = forms.CharField(
        max_length=5000,
        widget=forms.Textarea(attrs={
            "rows": 4,
            "maxlength": "5000",
        }),
        label="Descripción del requerimiento",
    )

    fecha_propuesta_solucion = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            "type": "date",
        }),
        label="Fecha propuesta de solución",
    )

    rut_menor = forms.CharField(
        required=False,
        max_length=12,
        label="RUT del menor",
        widget=forms.TextInput(attrs={
            "placeholder": "12.345.678-5",
            "inputmode": "text",
            "pattern": r"[0-9Kk.\-]+",
            "title": "Ingrese un RUT chileno válido.",
            "maxlength": "12",
            "autocomplete": "off",
        }),
    )

    nombre_menor = forms.CharField(
        required=False,
        max_length=150,
        label="Nombre del menor",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["delegacion"].queryset = (
            Delegacion.objects.filter(
                estado=Delegacion.ESTADO_ACTIVA
            ).order_by("nombre")
        )

        self.fields[
            "fecha_propuesta_solucion"
        ].widget.attrs["min"] = (
            timezone.localdate().isoformat()
        )

    def clean_rut_solicitante(self):
        rut_original = self.cleaned_data.get(
            "rut_solicitante",
            "",
        )

        rut = normalizar_rut(rut_original)

        if not rut or not rut_valido(rut_original):
            raise forms.ValidationError(
                "El RUT ingresado no es válido. "
                "Ingrese solo números y un dígito verificador "
                "numérico o K."
            )

        return rut

    def clean_rut_menor(self):
        rut_original = self.cleaned_data.get(
            "rut_menor",
            "",
        )

        if not rut_original:
            return ""

        rut = normalizar_rut(rut_original)

        if not rut or not rut_valido(rut_original):
            raise forms.ValidationError(
                "El RUT del menor no es válido."
            )

        return rut

    def clean(self):
        data = super().clean()

        fecha = data.get("fecha_propuesta_solucion")

        if fecha and fecha < timezone.localdate():
            self.add_error(
                "fecha_propuesta_solucion",
                "La fecha propuesta no puede ser anterior a hoy.",
            )

        tipo = data.get("tipo_solicitud")

        if tipo == Compromiso.TIPO_GENERAL:

            if not (
                data.get("nombre_solicitante") or ""
            ).strip():
                self.add_error(
                    "nombre_solicitante",
                    "Ingrese el nombre del vecino.",
                )

            if not (
                data.get("territorio") or ""
            ).strip():
                self.add_error(
                    "territorio",
                    "Ingrese el sector o territorio.",
                )

            if not data.get("delegacion"):
                self.add_error(
                    "delegacion",
                    "Seleccione la delegación municipal.",
                )

        if tipo == Compromiso.TIPO_REGALO:

            rut = data.get("rut_solicitante")

            if rut and not tutor_registrado(rut):
                self.add_error(
                    "rut_solicitante",
                    "El adulto/tutor no está registrado en el "
                    "padrón social del sistema.",
                )

            rut_menor = data.get("rut_menor")

            if not rut_menor:
                self.add_error(
                    "rut_menor",
                    "Ingrese un RUT válido del menor.",
                )

            elif Compromiso.objects.filter(
                rut_menor=rut_menor
            ).exists():
                self.add_error(
                    "rut_menor",
                    "Este menor ya tiene un regalo registrado "
                    "en el sistema.",
                )

            if not (
                data.get("nombre_menor") or ""
            ).strip():
                self.add_error(
                    "nombre_menor",
                    "Ingrese el nombre del menor.",
                )

        return data
