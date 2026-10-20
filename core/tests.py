"""
Pruebas de core: filtros de interfaz, login, dashboard y partials.
Renderizan las plantillas reales (templates/), por lo que detectan enlaces rotos (NoReverseMatch),
variables mal escritas y HTML desbalanceado.
"""
import re
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.core.paginator import Paginator
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from agenda.models import Compromiso
from measurement.models import Meta, Periodo
from measurement.services import CRUDMeta
from organizations.models import Cargo, Delegacion, Funcionario, FuncionarioRol, ItemMedible, Rol, Usuario

from .templatetags import ui_extras as ui

CLAVE = "Clave-Segura-2026"
HOY = timezone.localdate()
RAPIDO = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def balanceado(html, etiquetas=("div", "main", "nav", "header", "section", "ul", "li", "table", "thead",
                                "tbody", "tr", "form", "a", "span", "button")):
    return {t: (len(re.findall(rf"<{t}[\s>]", html)), html.count(f"</{t}>")) for t in etiquetas
            if len(re.findall(rf"<{t}[\s>]", html)) != html.count(f"</{t}>")}


# ---------------------------------------------------------------------------
# Filtros y tags
# ---------------------------------------------------------------------------
class EjemploForm(forms.Form):
    nombre = forms.CharField(label="Nombre", help_text="Como figura en el RUT")
    tipo = forms.ChoiceField(choices=[("a", "A")])
    activo = forms.BooleanField(required=False)
    nota = forms.CharField(widget=forms.Textarea, required=False)
    archivo = forms.FileField(required=False)


class FiltrosTests(TestCase):
    def test_tipo_widget(self):
        f = EjemploForm()
        self.assertEqual([ui.tipo_widget(f[n]) for n in ("nombre", "tipo", "activo", "nota", "archivo")],
                         ["input", "select", "checkbox", "textarea", "file"])

    def test_bs_campo_clases_y_accesibilidad(self):
        f = EjemploForm()
        self.assertIn('class="form-control"', ui.bs_campo(f["nombre"]))
        self.assertIn("form-select", ui.bs_campo(f["tipo"]))
        self.assertIn("form-check-input", ui.bs_campo(f["activo"]))
        self.assertIn('aria-describedby="id_nombre_ayuda"', ui.bs_campo(f["nombre"]))
        malo = EjemploForm(data={"nombre": ""})
        html = ui.bs_campo(malo["nombre"])
        self.assertIn("is-invalid", html)
        self.assertIn('aria-invalid="true"', html)
        self.assertIn("id_nombre_errores", html)

    def test_clases_sin_duplicar(self):
        f = EjemploForm()
        html = ui.add_class(f["nombre"], "form-control w-50")
        self.assertEqual(html.count("form-control"), 1)
        self.assertIn("w-50", html)

    def test_ancho_pct_es_seguro_para_css(self):
        self.assertEqual(ui.ancho_pct(Decimal("61.54")), "61.5")
        self.assertEqual(ui.ancho_pct(150), "100.0")
        self.assertEqual(ui.ancho_pct(-5), "0.0")
        self.assertEqual(ui.ancho_pct(None), "0.0")
        self.assertNotIn(",", ui.ancho_pct(33.3))

    def test_colores_y_porcentajes(self):
        self.assertEqual(ui.semaforo_color("Ámbar"), "warning")
        self.assertEqual(ui.estado_color("En revisión"), "info")
        self.assertEqual(ui.estado_color("Validada"), "success")
        self.assertEqual(ui.porcentaje(Decimal("61.54")), "61,5 %")
        self.assertEqual(ui.porcentaje(None), "—")


# ---------------------------------------------------------------------------
# Partials
# ---------------------------------------------------------------------------
class PartialsTests(TestCase):
    def test_form_field_etiqueta_obligatorio_ayuda_y_errores(self):
        form = EjemploForm(data={"nombre": ""})
        form.is_valid()
        html = render_to_string("partials/_form_field.html", {"field": form["nombre"]})
        self.assertIn("Nombre", html)
        self.assertIn("(obligatorio)", html)
        self.assertIn("Como figura en el RUT", html)
        self.assertIn("is-invalid", html)
        self.assertIn("Este campo es obligatorio", html)
        self.assertEqual(balanceado(html), {})

    def test_form_field_checkbox_y_label_personalizado_y_col(self):
        form = EjemploForm()
        html = render_to_string("partials/_form_field.html", {"field": form["activo"], "label": "¿Activo?", "col": "col-md-6"})
        self.assertIn("form-check", html)
        self.assertIn("¿Activo?", html)
        self.assertIn("col-md-6", html)

    def test_form_errors_muestra_solo_los_generales(self):
        form = EjemploForm(data={"nombre": "x", "tipo": "a"})
        form.is_valid()
        form.add_error(None, "La suma de ponderaciones superaría 100 %.")
        html = render_to_string("partials/_form_errors.html", {"form": form})
        self.assertIn("superaría 100", html)
        self.assertEqual(render_to_string("partials/_form_errors.html", {"form": EjemploForm()}).strip(), "")

    def _pagina(self, numero, consulta):
        pagina = Paginator(list(range(45)), 10).page(numero)
        request = RequestFactory().get("/lista/", consulta)
        return render_to_string("partials/_pagination.html", {"page_obj": pagina, "request": request})

    def test_paginacion_conserva_filtros(self):
        html = self._pagina(2, {"q": "ana", "estado": "Abierto", "page": 2})
        self.assertIn("Mostrando 11–20 de 45 registros", html)
        self.assertIn("q=ana", html)
        self.assertIn("estado=Abierto", html)
        self.assertRegex(html, r'href="\?[^"]*page=3"')
        self.assertIn('aria-current="page"', html)
        self.assertEqual(balanceado(html), {})

    def test_paginacion_con_puntos_suspensivos_y_una_sola_pagina(self):
        grande = Paginator(list(range(500)), 10).page(25)
        html = render_to_string("partials/_pagination.html",
                                {"page_obj": grande, "request": RequestFactory().get("/")})
        self.assertIn(str(Paginator.ELLIPSIS), html)          # puntos suspensivos entre bloques de páginas
        una = Paginator(list(range(3)), 10).page(1)
        html = render_to_string("partials/_pagination.html", {"page_obj": una, "request": RequestFactory().get("/")})
        self.assertIn("Mostrando 1–3 de 3 registros", html)
        self.assertNotIn("<nav", html)

    def test_url_pagina_tag(self):
        t = Template("{% load ui_extras %}{% url_pagina 4 %}")
        r = RequestFactory().get("/x/", {"q": "a b", "page": 1})
        self.assertEqual(t.render(Context({"request": r})), "?q=a+b&amp;page=4")


# ---------------------------------------------------------------------------
# Login y dashboard
# ---------------------------------------------------------------------------
@RAPIDO
class BaseVistas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.deleg = Delegacion.objects.create(nombre="Rural", ambito="x")
        cls.deleg2 = Delegacion.objects.create(nombre="Centro", ambito="y")
        cls.cargo = Cargo.objects.create(nombre_cargo="Terreno", vigencia_desde=HOY - timedelta(days=400))
        cls.item = ItemMedible.objects.create(nombre_item="Visitas", cargo=cls.cargo)
        cls.roles = {n: Rol.objects.create(nombre_rol=n) for n in
                     ("Administrador", "Coordinador", "Delegado", "Funcionario", "Verificador", "Consulta")}

    def crear(self, rol, deleg=None, activo=True):
        f = Funcionario.objects.create(
            identificador_institucional=rol, nombre=f"Nombre {rol}", cargo=self.cargo,
            delegacion=deleg or self.deleg, estado="Activo" if activo else "Inactivo")
        FuncionarioRol.objects.create(funcionario=f, rol=self.roles[rol])
        return f, Usuario.objects.create_user(rol.lower(), CLAVE, funcionario=f)

    def entrar(self, usuario):
        self.assertTrue(self.client.login(username=usuario, password=CLAVE))


class LoginTests(BaseVistas):
    def test_pagina_de_login(self):
        r = self.client.get(reverse("login"))
        html = r.content.decode()
        self.assertEqual(r.status_code, 200)
        self.assertIn("Sistema de Gestión de Resultados", html)
        self.assertIn('name="username"', html)
        self.assertIn('type="password"', html)
        self.assertIn("csrfmiddlewaretoken", html)
        self.assertIn("btn-ver-clave", html)
        self.assertNotIn("Regístrate", html)                  # el SGR no tiene autorregistro
        self.assertNotIn("sgr-sidebar", html)                 # sin menú para visitantes
        self.assertEqual(balanceado(html), {})

    def test_credenciales_incorrectas_muestran_mensaje_y_conservan_usuario(self):
        self.crear("Funcionario")
        r = self.client.post(reverse("login"), {"username": "funcionario", "password": "mala"})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('data-sgr-message data-tag="error"', html)
        self.assertIn('value="funcionario"', html)
        self.assertNotIn("mala", html)                        # la contraseña nunca se devuelve

    def test_ingreso_correcto_redirige_al_dashboard(self):
        self.crear("Funcionario")
        r = self.client.post(reverse("login"), {"username": "funcionario", "password": CLAVE})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        r = self.client.get(reverse("dashboard"))
        self.assertIn("Bienvenido/a, Nombre Funcionario", r.content.decode())

    def test_respeta_next_y_rechaza_destinos_externos(self):
        self.crear("Funcionario")
        r = self.client.post(reverse("login"), {"username": "funcionario", "password": CLAVE,
                                                "next": reverse("agenda:compromiso_list")})
        self.assertRedirects(r, reverse("agenda:compromiso_list"), fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post(reverse("login"), {"username": "funcionario", "password": CLAVE,
                                                "next": "https://sitio-malo.example/"})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)

    def test_pagina_de_login_conserva_next_en_campo_oculto(self):
        r = self.client.get(reverse("login"), {"next": "/agenda/"})
        self.assertIn('name="next" value="/agenda/"', r.content.decode())

    def test_ya_autenticado_no_ve_el_login(self):
        self.crear("Funcionario")
        self.entrar("funcionario")
        self.assertRedirects(self.client.get(reverse("login")), reverse("dashboard"), fetch_redirect_response=False)

    def test_funcionario_inactivo_no_ingresa(self):
        self.crear("Funcionario", activo=False)
        r = self.client.post(reverse("login"), {"username": "funcionario", "password": CLAVE})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_solo_por_post(self):
        self.crear("Funcionario")
        self.entrar("funcionario")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"), fetch_redirect_response=False)


class DashboardTests(BaseVistas):
    def test_requiere_sesion(self):
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, f"{reverse('login')}?next={reverse('dashboard')}", fetch_redirect_response=False)

    def test_contenido_por_rol(self):
        esperado = {
            "Funcionario": (["Mi trabajo", "Registrar actividad", "Mi desempeño", "Atención social"],
                            ["Verificación", "Supervisión y medición", "Organización"]),
            "Verificador": (["Verificación", "Validación de evidencias"],
                            ["Supervisión y medición", "Registrar actividad", "Atención social"]),
            "Delegado": (["Supervisión y medición", "Semáforo de delegación", "Funcionarios"], ["Verificación"]),
            "Consulta": (["Actividades", "Agenda colectiva"],
                         ["Registrar actividad", "Supervisión y medición", "Atención social", "Verificación"]),
            "Administrador": (["Verificación", "Supervisión y medición", "Organización", "Catálogos"], []),
        }
        for rol, (si, no) in esperado.items():
            self.crear(rol)
            self.entrar(rol.lower())
            r = self.client.get(reverse("dashboard"))
            html = r.content.decode()
            self.assertEqual(r.status_code, 200, rol)
            for texto in si:
                self.assertIn(texto, html, f"{rol} debería ver «{texto}»")
            for texto in no:
                self.assertNotIn(texto, html, f"{rol} NO debería ver «{texto}»")
            self.assertEqual(balanceado(html), {}, rol)
            self.client.logout()

    def test_superusuario_sin_funcionario_ve_aviso_y_no_error_403(self):
        Usuario.objects.create_superuser("root", CLAVE)
        self.entrar("root")
        r = self.client.get(reverse("dashboard"))
        html = r.content.decode()
        self.assertEqual(r.status_code, 200)
        self.assertIn("no tiene un funcionario asociado", html)
        self.assertIn("Panel técnico", html)

    def test_sin_periodo_vigente_avisa(self):
        self.crear("Funcionario")
        self.entrar("funcionario")
        self.assertIn("No hay un período de medición abierto", self.client.get(reverse("dashboard")).content.decode())

    def test_semaforo_personal_con_meta(self):
        f, _ = self.crear("Funcionario")
        periodo = Periodo.objects.create(fecha_inicio=HOY - timedelta(days=30), fecha_termino=HOY + timedelta(days=30))
        CRUDMeta.crear_meta(Meta(funcionario=f, item=self.item, periodo=periodo, valor_objetivo=Decimal("10"),
                                 unidad="visitas", ponderador=Decimal("100")))
        self.entrar("funcionario")
        r = self.client.get(reverse("dashboard"))
        html = r.content.decode()
        self.assertEqual(r.context["datos"]["resumen_personal"]["semaforo"], "Rojo")     # 0 % vs ~50 % esperado
        self.assertIn("Mi avance en el período", html)
        self.assertIn("badge text-bg-danger", html)
        self.assertIn("Meta esperada al día", html)
        self.assertRegex(html, r'style="width: \d+\.\d%"')                                # punto decimal, no coma
        self.assertEqual(balanceado(html), {})

    def test_equipo_y_vencidos_para_el_delegado(self):
        f, _ = self.crear("Funcionario")
        self.crear("Delegado")
        otro, _ = self.crear("Verificador", deleg=self.deleg2)
        periodo = Periodo.objects.create(fecha_inicio=HOY - timedelta(days=30), fecha_termino=HOY + timedelta(days=30))
        CRUDMeta.crear_meta(Meta(funcionario=f, item=self.item, periodo=periodo, valor_objetivo=Decimal("10"),
                                 unidad="v", ponderador=Decimal("100")))
        Compromiso.objects.create(origen="x", solicitante="Junta Norte", territorio="Norte", funcionario=f,
                                  delegacion=self.deleg, fecha_comprometida=HOY - timedelta(days=4))
        Compromiso.objects.create(origen="x", solicitante="Junta Ajena", territorio="Centro", funcionario=otro,
                                  delegacion=self.deleg2, fecha_comprometida=HOY - timedelta(days=4))
        self.entrar("delegado")
        r = self.client.get(reverse("dashboard"))
        html = r.content.decode()
        self.assertIn("Semáforo del equipo", html)
        self.assertIn("Compromisos vencidos sin cierre", html)
        self.assertIn("Junta Norte", html)
        self.assertNotIn("Junta Ajena", html)                        # otra delegación: no se filtra
        self.assertEqual(r.context["datos"]["resumen_equipo"]["total_funcionarios"], 2)   # funcionario + delegado
        self.assertEqual(balanceado(html), {})

    def test_logout_en_la_barra_es_post_con_csrf(self):
        self.crear("Funcionario")
        self.entrar("funcionario")
        html = self.client.get(reverse("dashboard")).content.decode()
        formulario = re.search(r'<form method="post" action="/logout/">(.*?)</form>', html, re.S)
        self.assertIsNotNone(formulario)
        self.assertIn("csrfmiddlewaretoken", formulario.group(1))
