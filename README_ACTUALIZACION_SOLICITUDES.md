# Actualización SGR — Solicitudes vecinales y regalos

**Repositorio:** `pamelamb0805/sistema_SGR_django_p2c2_Pamela_Mejia`  
**Rama de destino:** `mejoras_finales`  
**Versión remota revisada:** `88f9d9abeeeca7aa4dd0d88a86a4bd89e867a74d` (`Revision 2.0`)

Este ZIP es un paquete de actualización incremental para aplicar sobre el proyecto de esa rama. No es una copia completa del repositorio. Incluye los archivos completos que deben reemplazarse, los archivos nuevos, migraciones, pruebas y un script idempotente para integrar las modificaciones pequeñas en archivos existentes sin reemplazar su contenido completo.

## Aplicación

1. Haz una copia de seguridad del proyecto y de la base de datos.
2. Descomprime este ZIP en la raíz de tu proyecto local, conservando las carpetas. Acepta reemplazar los archivos indicados.
3. Ejecuta desde la raíz:

   ```bash
   python aplicar_integracion_solicitudes.py
   python manage.py check
   python manage.py migrate
   python manage.py test agenda.test_solicitudes
   python manage.py test
   ```

4. Revisa `git diff` antes de confirmar cambios.

No ejecutar scripts de semilla, `loaddata`, ni insertar registros. No se incluye `.env`, contraseñas, datos personales, ni fixtures.

## Archivos completos para reemplazar

- `agenda/models.py`
- `agenda/services.py`
- `social/models.py`

## Archivos nuevos

- `agenda/migrations/0003_solicitudes_vecinales.py`
- `social/migrations/0003_usuario_rut.py`
- `agenda/solicitudes_forms.py`
- `agenda/solicitudes_services.py`
- `agenda/solicitudes_views.py`
- `agenda/solicitudes_urls.py`
- `agenda/test_solicitudes.py`
- `agenda/templatetags/__init__.py`
- `agenda/templatetags/solicitudes_tags.py`
- `templates/solicitudes/solicitud_publica.html`
- `templates/solicitudes/lista.html`
- `templates/solicitudes/detalle.html`
- `aplicar_integracion_solicitudes.py`
- Documentación bajo `docs/`.

El script integra `config/urls.py`, `core/views.py`, `templates/base.html`, `templates/registration/login.html` y `templates/core/dashboard.html` sin sustituir esos archivos completos.

## Arquitectura y datos

No se crean nuevas entidades ni tablas de negocio. La solicitud se representa en `COMPROMISO`; sus eventos en `HISTORIAL_TRANSICIONES`; el RUT del tutor se agrega a `USUARIO` (`social.UsuarioSocial`). La unicidad del RUT del menor se garantiza con índice único en `COMPROMISO.rut_menor` (valores `NULL` para solicitudes no relacionadas con regalos).

La migración agrega `social.UsuarioSocial.rut`, nullable y único. Para habilitar regalos, tu semilla debe completar el RUT normalizado de los adultos/tutores. Este ZIP no altera ni crea la semilla.

## Estado de pruebas

En el entorno de construcción se ejecutó `compileall` y pasó `git diff --check`; cinco comprobaciones puras de RUT pasaron. No fue posible ejecutar Django: el entorno no tiene Django instalado y no tiene acceso de red para instalar `requirements.txt`. Por tanto, `manage.py check`, las migraciones reales, pruebas de integración con MySQL, navegador y estrés quedan pendientes de ejecutar en tu entorno. No se declara 100 % de cobertura ni aprobación final.

Consulta:
- `docs/IMPLEMENTACION_SOLICITUDES_VECINALES.md`
- `docs/PLAN_PRUEBAS_SOLICITUDES_VECINALES.md`
- `docs/MATRIZ_RF_RNF_SGR.md`
