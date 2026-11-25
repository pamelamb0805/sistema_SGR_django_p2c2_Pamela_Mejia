# Matriz de trazabilidad de requisitos SGR

Esta matriz relaciona los requisitos del Excel con las áreas del proyecto y la estrategia de regresión. La existencia de código o pruebas automatizadas no equivale por sí sola a una aprobación: se debe registrar el resultado real de cada ejecución.

| Requisito | Área/código principal | Verificación de regresión |
|---|---|---|
| RF-001 | `organizations` Delegaciones | CRUD, unicidad, estado, filtros y alcance. |
| RF-002 | `organizations` Usuarios/Roles | Alta, asociación, acceso, cuenta inactiva y privilegio mínimo. |
| RF-003 | `organizations` Cargos/funciones | Vigencia, asociación y validación de relaciones. |
| RF-004 | `catalogs` | CRUD, duplicados, estado y filtros. |
| RF-005 | `measurement` Períodos | Vigencia, fechas, solapamientos y bloqueo según estado. |
| RF-006 | `measurement` Ponderaciones | Suma configurada, límites y valores inválidos. |
| RF-007 | `measurement` Metas/umbrales | Reglas, topes, faltantes y cambios de vigencia. |
| RF-008 | `organizations` Perfil | Datos del funcionario y delegación vigente. |
| RF-009/RF-010 | `activities` | Registro y validación de actividad, fechas y relaciones. |
| RF-011/RF-012 | `activities` Evidencias | Generación, asociación, formatos, tamaños y metadatos. |
| RF-013/RF-014 | `activities` Validaciones | Aprobar/rechazar, permisos y cálculo único de puntaje. |
| RF-015 | `social` | Caso, atenciones, máximo de gestiones, catálogos y ámbito. |
| RF-016/RF-017/RF-018/RF-019 | `agenda` | Compromisos, asignación, estados, plazos y transiciones. |
| RF-020 a RF-026 | `measurement` + `agenda` | Cálculos, ponderación, topes, metas esperadas y ajustes. |
| RF-027 a RF-031 | `core` + `measurement` | Semáforos, tableros personal/delegación, actividad reciente y vista global. |
| RF-032/RF-033 | `core`, `agenda`, `social`, `organizations` | Búsqueda, filtros, paginación y Excel autorizado. |
| RF-034/RNF-003 | Servicios y transacciones | Dos usuarios modificando/creando simultáneamente; medir conflictos y consistencia. |
| RF-035 | `audit`/`websocket` | Coordinación, notificaciones, comentarios y actualización visible. |
| RF-036/RNF-008 | `audit` + historiales | Usuario, fecha, acción, entidad, valor anterior/nuevo y no alteración. |
| RF-037/RNF-018 | `audit`/`core` | Alertas, umbrales, atención y monitoreo. |
| RF-038/RNF-015 | Versiones de `catalogs`, `measurement`, `organizations` | Cambios efectivos, histórico y consulta de períodos anteriores. |
| RNF-001 | Infraestructura | Disponibilidad objetivo 99,5 %, medir indisponibilidades. |
| RNF-002 | Consultas y tableros | Medir respuesta objetivo 2 s en condiciones normales; dashboard consolidado según CA. |
| RNF-003 | Base de datos/servicios | Concurrencia, bloqueos, doble envío y restricciones únicas. |
| RNF-004 | `organizations.Usuario`/login | Identidad individual, recuperación; MFA/directorio requiere integración institucional. |
| RNF-005 | `core.mixins`, servicios y vistas | Matriz de rol, delegación, función y operación; pruebas de acceso horizontal/vertical. |
| RNF-006 | HTTPS, `.env`, DB | TLS, secretos, repositorios, copias y cifrado de evidencias. |
| RNF-007 | Formularios/modelos/DB | Formatos, relaciones, duplicados y concurrencia. |
| RNF-008 | `audit`/`HistorialTransiciones` | Eventos críticos inmutables y cronológicos. |
| RNF-009 | Vistas/consultas/exportaciones | Minimización y restricción de datos personales. |
| RNF-010 | AWS/DB | Backup automatizado y restauración comprobada. |
| RNF-011/RNF-012 | Templates/JS | Usabilidad, etiquetas, navegación teclado, contraste y textos alternativos. |
| RNF-013 | Navegadores | Chrome y Edge soportados. |
| RNF-014 | Modelo/índices | Agregar delegaciones, cargos, actividades, períodos y usuarios sin rediseño. |
| RNF-015 | Servicios/migraciones/docs | Configuración sin cambios de código y mantenibilidad. |
| RNF-016 | Exportaciones | Excel/formatos estructurados con alcance autorizado. |
| RNF-017 | Evidencias | Tipo, tamaño, antivirus, metadatos y permisos de archivos. |
| RNF-018 | Logging/alertas | Métricas, errores, fallas de integración y capacidad. |

La implementación de solicitudes vecinales cubre directamente los escenarios SOL-001 a SOL-034 de `PLAN_PRUEBAS_SOLICITUDES_VECINALES.md`. Los demás requisitos requieren la regresión de las suites existentes y evidencia de infraestructura; no se declaran aprobados por este módulo.
