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

| Componente | Alcance requerido | Estado en código recibido |
| --- | --- | --- |
| Login | Usuario o correo y contraseña; validación y acceso según perfil. | Implementado; requiere ejecución integrada de pruebas |
| Recuperar contraseña | Código por correo, validación, expiración, intentos y nueva clave. | Implementado; SMTP real depende de configuración |
| Validar código | Código válido/incorrecto/vencido, intentos y reenvío. | Implementado; requiere validación integrada |
| Crear nueva contraseña | Nueva clave, confirmación, validadores y retorno al login. | Implementado; requiere validación integrada |
| CRUD Delegaciones | Código, nombre, dirección, comuna y estado. | Implementado con auditoría, filtros, paginación y Excel |
| CRUD Roles | Nombre, descripción, permisos y alcance autorizado. | Implementado con permisos y restricciones de delegación de privilegios |
| CRUD Usuarios | Nombre, correo, rol, delegación(es) autorizada(s) y estado. | Implementado mediante Usuario/Funcionario y asignación de roles/delegaciones |
| CRUD Ítems y metas | Código, nombre, descripción y estado (mantenedor de Ítems). | Ítems implementados vinculados a Cargo; metas administradas en `measurement` |
| CRUD Tipo de Atención | Código, nombre, descripción y estado. | Implementado como tipo de `Catalogo` |
| CRUD Sub Atención | Código, nombre, Tipo de Atención asociado y estado. | Implementado como `Catalogo` con FK autorreferente al Tipo de Atención |
| Ingreso de atención | Solicitante, tipo, subatención, descripción, delegación, responsable y fecha. | Implementado como caso + primera gestión en `social` |

La rama de trabajo conserva la arquitectura de modelos existente. La selección de delegación activa se valida en servidor y limita las consultas del contexto actual.

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

El plan de pruebas de esta entrega, el estado de los RNF y las limitaciones de validación están documentados en [`ENTREGA_ANEXO_A.md`](docs/ENTREGA_ANEXO_A.md).

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
- El correo de acceso está modelado en `organizations.Usuario.email`; el usuario de acceso mantiene relación 1:1 con `Funcionario`.
- Las aplicaciones propias incluyen migraciones Django. Antes de desplegar, revisar `python manage.py showmigrations` y ejecutar las migraciones pendientes en una copia de la base de datos.
- Para producción, definir `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` y `DEFAULT_FROM_EMAIL` en `.env`, nunca publicar esos valores en Git.
