"""Integra las rutas, navegación y KPIs de solicitudes sobre la rama actual.

Ejecutar desde la raíz del proyecto: python aplicar_integracion_solicitudes.py
Es idempotente: si una integración ya existe, no la duplica.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(relative_path, anchor, replacement, *, before=True, marker=None):
    path = ROOT / relative_path
    content = path.read_text(encoding="utf-8")
    if marker and marker in content:
        print(f"[OK] Ya integrado: {relative_path}")
        return
    if anchor not in content:
        raise SystemExit(f"No se encontró el punto de integración en {relative_path}: {anchor[:80]!r}")
    content = content.replace(anchor, replacement + anchor if before else anchor + replacement, 1)
    path.write_text(content, encoding="utf-8")
    print(f"[OK] Integrado: {relative_path}")


# 1. URL pública y bandeja privada.
replace_once(
    "config/urls.py",
    '    path("agenda/", include("agenda.urls")),\n',
    '    path("solicitudes/", include("agenda.solicitudes_urls")),\n',
    before=False,
    marker='include("agenda.solicitudes_urls")',
)

# 2. Cargar tag de visibilidad y mostrar el menú solo a perfiles habilitados.
base_path = ROOT / "templates/base.html"
base_content = base_path.read_text(encoding="utf-8")
if "solicitudes_tags" not in base_content:
    anchor_load = "{% load static ui_extras %}"
    if anchor_load not in base_content:
        raise SystemExit("No se encontró el bloque load en templates/base.html")
    base_path.write_text(base_content.replace(anchor_load, "{% load static ui_extras solicitudes_tags %}", 1), encoding="utf-8")
    print("[OK] Integrado: templates/base.html (tag)")
else:
    print("[OK] Ya integrado: templates/base.html (tag)")
nav_anchor = '''                    <li class="nav-item">\n                        <a class="nav-link {% if ns == 'agenda' and name != 'resumen' %}active{% endif %}"\n                           href="{% url 'agenda:compromiso_list' %}">\n                            <i class="bi bi-calendar-event"></i>Agenda colectiva\n                        </a>\n                    </li>\n'''
nav_insert = '''                    {% puede_ver_solicitudes user as sgr_puede_ver_solicitudes %}\n                    {% if sgr_puede_ver_solicitudes %}\n                    <li class="nav-item">\n                        <a class="nav-link {% if ns == 'solicitudes' %}active{% endif %}" href="{% url 'solicitudes:lista' %}">\n                            <i class="bi bi-inbox"></i>Solicitudes vecinales\n                        </a>\n                    </li>\n                    {% endif %}\n'''
replace_once("templates/base.html", nav_anchor, nav_insert, before=False, marker="{% url 'solicitudes:lista' %}")

# 3. Link público en el login (no requiere autenticación).
login_anchor = '''          <a href="{% url 'recuperar_clave' %}"\n             class="text-decoration-none">\n'''
login_insert = '''          <a href="{% url 'solicitudes:publica' %}" class="btn btn-outline-primary w-100 mb-3">\n            <i class="bi bi-megaphone me-1" aria-hidden="true"></i>Ingresar solicitud vecinal sin iniciar sesión\n          </a>\n\n'''
replace_once("templates/registration/login.html", login_anchor, login_insert, marker="{% url 'solicitudes:publica' %}")

# 4. Contadores exclusivos del Delegado.
dashboard_anchor = '''    datos["alertas_operativas"] = construir_alertas_operativas(\n'''
dashboard_insert = '''    datos["solicitudes_creadas"] = None\n    datos["solicitudes_pendientes"] = None\n    datos["solicitudes_cerradas"] = None\n    if funcionario is not None and tiene_rol(user, "Delegado"):\n        from agenda.solicitudes_services import solicitudes_visibles\n        solicitudes = solicitudes_visibles(user)\n        datos["solicitudes_creadas"] = solicitudes.filter(estado_solicitud="Creado").count()\n        datos["solicitudes_pendientes"] = solicitudes.filter(estado_solicitud="Pendiente").count()\n        datos["solicitudes_cerradas"] = solicitudes.filter(estado_solicitud="Concluido").count()\n\n'''
replace_once("core/views.py", dashboard_anchor, dashboard_insert, marker='datos["solicitudes_creadas"]')

# 5. Bloque KPI del Delegado.
kpi_anchor = '''    <!-- KPI -->\n\n    <div class="sgr-kpi-strip">\n'''
kpi_insert = '''    {% if d.solicitudes_creadas is not None %}\n    <section class="card border-0 shadow-sm mb-3" aria-labelledby="solicitudes-kpi-title">\n      <div class="card-body py-3">\n        <div class="d-flex justify-content-between align-items-center mb-2">\n          <h2 id="solicitudes-kpi-title" class="h6 mb-0">Solicitudes vecinales de mi delegación</h2>\n          <a href="{% url 'solicitudes:lista' %}" class="small">Ver todas</a>\n        </div>\n        <div class="row g-2 text-center">\n          <div class="col-4"><div class="border rounded p-2"><div class="small text-muted">Creadas</div><strong class="fs-4">{{ d.solicitudes_creadas }}</strong></div></div>\n          <div class="col-4"><div class="border rounded p-2"><div class="small text-muted">Pendientes</div><strong class="fs-4">{{ d.solicitudes_pendientes }}</strong></div></div>\n          <div class="col-4"><div class="border rounded p-2"><div class="small text-muted">Cerradas</div><strong class="fs-4">{{ d.solicitudes_cerradas }}</strong></div></div>\n        </div>\n      </div>\n    </section>\n    {% endif %}\n\n'''
replace_once("templates/core/dashboard.html", kpi_anchor, kpi_insert, marker='id="solicitudes-kpi-title"')

print("Integración finalizada. Revise git diff antes de ejecutar migraciones.")
