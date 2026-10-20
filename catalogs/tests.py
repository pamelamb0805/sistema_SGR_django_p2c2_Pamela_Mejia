from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.exceptions import ReglaNegocioError
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, Rol, Usuario

from .models import Catalogo
from .services import CRUDCatalogo

CLAVE = "Clave-Segura-2026"


class CatalogoModeloTests(TestCase):
    def setUp(self):
        self.reunion = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Reunión vecinal", area="Social")
        self.general = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Visita a terreno", area="General")
        self.inactivo = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Antigua", area="Social",
                                                estado="Inactivo")
        self.rural = Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Poda", area="Rural")

    def test_nombre_unico_por_tipo_y_area_sin_distinguir_mayusculas(self):
        with self.assertRaises(ValidationError):
            Catalogo(tipo_catalogo="Actividad", nombre="reunión VECINAL", area="social").full_clean()

    def test_mismo_nombre_en_otra_area_es_valido(self):
        Catalogo(tipo_catalogo="Actividad", nombre="Reunión vecinal", area="Rural").full_clean()

    def test_disponibles_solo_activos_del_area_mas_general(self):
        nombres = set(Catalogo.objects.disponibles(area="Social").values_list("nombre", flat=True))
        self.assertEqual(nombres, {"Reunión vecinal", "Visita a terreno"})   # sin inactivos ni de otra área


class CatalogoServicioTests(TestCase):
    def setUp(self):
        self.elemento = Catalogo.objects.create(tipo_catalogo="Servicio", nombre="Entrega de agua", area="Rural")

    def test_desactivar_y_activar(self):
        CRUDCatalogo.desactivar_elemento_catalogo(self.elemento)
        self.assertFalse(Catalogo.objects.get(pk=self.elemento.pk).activo)
        CRUDCatalogo.activar_elemento_catalogo(self.elemento)
        self.assertTrue(Catalogo.objects.get(pk=self.elemento.pk).activo)

    def test_en_uso_no_permite_cambiar_tipo_ni_area(self):
        self.elemento.area = "Social"
        with mock.patch.object(Catalogo, "en_uso", return_value=True):
            with self.assertRaises(ReglaNegocioError):
                CRUDCatalogo.modificar_elemento_catalogo(self.elemento)
        self.assertEqual(Catalogo.objects.get(pk=self.elemento.pk).area, "Rural")

    def test_en_uso_permite_cambiar_estado_y_nombre(self):
        self.elemento.nombre = "Entrega de agua potable"
        with mock.patch.object(Catalogo, "en_uso", return_value=True):
            CRUDCatalogo.modificar_elemento_catalogo(self.elemento)
        self.assertEqual(Catalogo.objects.get(pk=self.elemento.pk).nombre, "Entrega de agua potable")


class CatalogoVistaTests(TestCase):
    def setUp(self):
        delegacion = Delegacion.objects.create(nombre="Rural", ambito="x")
        cargo = Cargo.objects.create(nombre_cargo="C", vigencia_desde="2026-01-01")
        for nombre in ("Administrador", "Funcionario"):
            rol = Rol.objects.create(nombre_rol=nombre)
            f = Funcionario.objects.create(identificador_institucional=nombre, nombre=nombre,
                                           cargo=cargo, delegacion=delegacion)
            FuncionarioRol.objects.create(funcionario=f, rol=rol)
            Usuario.objects.create_user(nombre.lower(), CLAVE, funcionario=f)
        Catalogo.objects.create(tipo_catalogo="Actividad", nombre="Poda", area="Rural")

    def test_admin_crea_elemento(self):
        self.client.login(username="administrador", password=CLAVE)
        r = self.client.post(reverse("catalogs:catalogo_create"),
                             {"tipo_catalogo": "Servicio", "nombre": "Retiro de escombros",
                              "area": "Rural", "estado": "Activo"})
        self.assertRedirects(r, reverse("catalogs:catalogo_list"), fetch_redirect_response=False)
        self.assertTrue(Catalogo.objects.filter(nombre="Retiro de escombros").exists())

    def test_funcionario_comun_no_puede_crear(self):
        self.client.login(username="funcionario", password=CLAVE)
        r = self.client.post(reverse("catalogs:catalogo_create"),
                             {"tipo_catalogo": "Servicio", "nombre": "X", "area": "Rural", "estado": "Activo"})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        self.assertFalse(Catalogo.objects.filter(nombre="X").exists())

    def test_api_por_area_requiere_login_y_devuelve_json(self):
        url = reverse("catalogs:catalogo_por_area")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.login(username="funcionario", password=CLAVE)
        datos = self.client.get(url, {"area": "Rural", "tipo": "Actividad"}).json()
        self.assertEqual([e["nombre"] for e in datos["resultados"]], ["Poda"])
