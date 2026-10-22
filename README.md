# Sistema SGR – Sistema de Gestión de Resultados

Aplicación web desarrollada con **Python y Django** para el proyecto integrador de INACAP, basado en el caso de las delegaciones municipales de la Ilustre Municipalidad de La Serena.

> Todos los datos del proyecto son **ficticios o anonimizados**. No se cargan datos reales de ciudadanos ni de funcionarios.

---

## Descripción y objetivo

El SGR centraliza el registro, seguimiento, validación y medición de la gestión de funcionarios y delegaciones. Su objetivo es construir la base backend del sistema (modelos, reglas de negocio, autenticación y mantenedores) con un desarrollo estructurado y escalable, a partir de la especificación de la *Guía de Proyecto Integrado SGR*, el diagrama E-R y el diagrama de clases.

## Alcance de la segunda evaluación (ANEXO A)

La segunda entrega presenta:

- Acceso al sistema (login) y recuperación de contraseña.
- Seis mantenedores (CRUD).
- Ingreso de atención ciudadana.

Condiciones generales:

- Todas las pantallas usan **un mismo template** y se identifican con la **delegación activa** según el perfil del usuario.
- El sistema está disponible en **AWS**, con el código actualizado en un **repositorio remoto Git**.
- Todas las pantallas y su navegación están creadas. La persistencia y funcionalidad se exigen según el avance de Backend; lo **simulado** no acredita persistencia real.
- Las alertas, confirmaciones y resultados de operación usan **SweetAlert2**.
- Las validaciones se ejecutan en la interfaz **y** en el servidor.

### Módulos y pantallas

Estado posible: **Operativo** (persistencia y lógica reales), **Simulado** (solo interfaz) o **Pendiente**.

| Componente | Alcance requerido | Estado |
| --- | --- | --- |
| Login | Usuario o correo y contraseña; validación y acceso según perfil. | Implementación presente; falta prueba integrada |
| Recuperar contraseña | Código por correo, validación, expiración, intentos y nueva clave. | Código implementado; requiere SMTP y prueba integrada |
| Validar código | Ingreso y comprobación del código, vigencia, reenvío y tratamiento de intentos fallidos. | Por definir |
| Crear nueva contraseña | Nueva clave, confirmación, validación de requisitos y retorno al login. | Por definir |
| CRUD Delegaciones | Código, nombre, dirección, comuna y estado. | Parcial: modelo actual usa nombre, ámbito y estado |
| CRUD Roles | Nombre, descripción, permisos y alcance autorizado. | Parcial: nombre y descripción; permisos/alcance no modelados |
| CRUD Usuarios | Nombre, correo, rol, delegación(es) autorizada(s) y estado. | Parcial: se agregó correo; modelo permite una delegación por funcionario |
| CRUD Ítems y metas | Código, nombre, descripción y estado (mantenedor de Ítems). | Por definir |
| CRUD Tipo de Atención | Código, nombre, descripción y estado. | Por definir |
| CRUD Sub Atención | Código, nombre, Tipo de Atención asociado y estado. | Por definir |
| Ingreso de atención | Solicitante, tipo, subatención, descripción, delegación, usuario responsable y fecha de registro. | Por definir |

Los diseños se basan en `mockups.pdf` (páginas 1 a 6). Los catálogos de Vecinos y Tipo de Gestión que aparecen en los mockups son solo contexto y no se incorporan como requisito adicional en esta entrega.

## Requisitos comunes de interfaz

### Identidad visual

La identidad visual de todas las pantallas (login, recuperación de contraseña, mantenedores, ingreso de atención y mensajes SweetAlert2) se basa en las normas gráficas oficiales de la Municipalidad de La Serena: <https://laserena.cl/conocenos/normas-graficas>.

### Estructura de cada mantenedor

- Crear, consultar, listar, editar y eliminar o desactivar registros, respetando relaciones y reglas de negocio.
- Tabla con columnas relevantes, estado textual y acciones claras.
- Paginador, total de resultados y búsqueda por coincidencia parcial en varios campos, sin distinguir mayúsculas y minúsculas.
- Los filtros se conservan al cambiar de página.
- Estados de carga, listado vacío, ausencia de coincidencias y errores.
- Botón **Exportar a Excel**: exporta los resultados autorizados del filtro aplicado en todas sus páginas, sin contraseñas, tokens ni campos internos.
- Campos obligatorios identificados, con opciones de guardar y cancelar.

### Delegación activa

- La cabecera muestra de forma permanente el **código y nombre de la delegación activa**, el nombre del usuario y su rol, con un distintivo de texto e icono (el color por sí solo no identifica el contexto).
- Usuario con una sola delegación: contexto fijo.
- Usuario con varias delegaciones: selector que muestra solo las autorizadas. Cambiar de contexto actualiza listados, filtros, exportaciones y formularios, y advierte sobre cambios sin guardar.
- La delegación y los permisos se validan en el **servidor**; ocultar botones no es control de acceso.

### Ingreso de atención

- Identifica al solicitante y permite elegir Tipo de Atención y Sub Atención.
- La Sub Atención muestra solo opciones **activas** del tipo elegido y se limpia si deja de ser válida al cambiar el tipo.
- La delegación se completa desde el contexto autorizado del usuario; responsable y fecha/hora se registran automáticamente.
- Al guardar se muestra confirmación y un identificador de atención; cancelar no crea registros.

## Pruebas

El plan de pruebas de esta entrega (casos de acceso, recuperación de contraseña, mantenedores, listados, ingreso de atención, perfil y delegación, SweetAlert2, pruebas de estrés y registro de defectos) está en [`PLAN_DE_PRUEBAS.md`](docs/PLAN_DE_PRUEBAS.md).

Las pruebas pendientes por falta de Backend se declaran como **Pendiente** con su justificación; no se informan como aprobadas.

## Prerrequisitos

- Python 3.12 o superior (según lo que exija la versión de Django de `requirements.txt`)
- Git
- Dependencias de `requirements.txt`

## Instalación y ejecución local

```bash
# 1. Clonar el repositorio
git clone https://github.com/pamelamb0805/sistema_SGR_django_p2c2_Pamela_Mejia.git
cd sistema_SGR_django_p2c2_Pamela_Mejia

# 2. Crear y activar el entorno virtual
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Variables de entorno
# Copiar .env.example a .env y completar los valores
cp .env.example .env        # En Windows: copy .env.example .env

# 5. Migraciones y usuario administrador
python manage.py migrate
python manage.py createsuperuser

# 6. Ejecutar el servidor
python manage.py runserver
```

La aplicación queda disponible en <http://127.0.0.1:8000/>.

## Estructura del proyecto

```text
sistema_SGR_django_p2c2_Pamela_Mejia/
├── config/          # Configuración del proyecto Django
├── core/            # Funcionalidad base
├── organizations/
├── catalogs/
├── social/
├── activities/
├── agenda/
├── audit/
├── templates/       # Templates HTML (template base compartido)
├── static/          # Archivos estáticos
├── docs/            # Documentación (plan de pruebas)
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

## Despliegue en AWS

| Dato | Valor |
| --- | --- |
| URL pública | _completar_ |
| Servicio / instancia | _completar_ |
| Región | _completar_ |
| Fecha del último despliegue | _completar_ |

## Seguridad

- Las credenciales y llaves van en variables de entorno (`.env`), excluidas del repositorio mediante `.gitignore`.
- No se almacenan contraseñas en texto plano.
- Los permisos y la delegación se validan en el servidor.
- Solo se usan datos de prueba ficticios.

## Autora

Pamela Mejía – Ingeniería en Informática, INACAP.


## Notas de implementación para la entrega

- Se agregó flujo de recuperación con código de seis dígitos, vencimiento de 10 minutos, máximo de 5 intentos y formulario de nueva contraseña. El código se envía por correo si se configura SMTP; sin `EMAIL_HOST`, Django lo imprime en la consola local y **no se envía un correo real**.
- Para iniciar sesión con correo, cada funcionario debe tener un correo registrado en `organizations.Funcionario.email`.
- **Cambio de base de datos:** se agregó el campo `email` al modelo `Funcionario`. En una base nueva, ejecutar `python manage.py migrate --run-syncdb`. Si la base MySQL ya existía y la tabla `funcionario` ya está creada, aplicar una vez: `ALTER TABLE funcionario ADD COLUMN email VARCHAR(254) NOT NULL DEFAULT '';` y después retirar el valor por defecto si se desea. Respaldar la base antes de modificarla.
- El repositorio original no contiene migraciones Django de las aplicaciones propias. Por eso hay que probar los cambios contra una copia de la base real antes de desplegar; no se debe asumir que la modificación del esquema ya está aplicada.
- Para producción, definir `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` y `DEFAULT_FROM_EMAIL` en `.env`, nunca publicar esos valores en Git.
