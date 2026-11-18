# Matriz de trazabilidad y validación SGR

**Base de código:** repositorio `pamelamb0805/sistema_SGR_django_p2c2_Pamela_Mejia`, rama `mejoras_finales` (árbol consultado: `b97c9ade32abe1b5669089eea2a629ba5c9e6178`).  
**Especificación disponible:** `Guia_Proyecto_Software_SGR_Alumnos.pdf`, `Historias_usuarios_requerimientos.pdf`, `diagramas proyecto integrado.drawio.xml`, `Descriptor de funciones.pdf` y `ANEXO A.pdf`.

> El paquete documental recibido contiene `Historias_usuarios_requerimientos.pdf`, no `Historias_usuarios_requerimientos.xlsx`. Esta matriz refleja el PDF disponible. No se declara conformidad literal con celdas o reglas que solo existan en el Excel ausente.

## Requerimientos funcionales

| ID | Implementación identificada | Pruebas existentes / añadidas | Validación pendiente |
|---|---|---|---|
| RF-001 | CRUD de delegaciones en `organizations` | `organizations/tests.py` | Ejecutar suite y casos de duplicidad/estado |
| RF-002 | Funcionarios, usuarios y roles en `organizations`; alta automática incluida en este paquete | `organizations/tests.py` + `organizations/test_account_and_admin_sistema.py` | Ejecutar; comprobar cuenta y contraseña inutilizable |
| RF-003 | Cargos e ítems medibles | `organizations/tests.py`, `activities/tests.py` | Ejecutar casos de ítems vigentes por cargo |
| RF-004 | Catálogo unificado por tipo y relación padre-hijo en `catalogs` | `catalogs/tests.py` | Ejecutar restricciones e historial |
| RF-005 | Períodos y días computables en `measurement` | `measurement/tests.py` | Ejecutar límites de fechas |
| RF-006 | Ponderaciones por cargo/período y suma aplicable | `measurement/tests.py` | Ejecutar reglas de suma y excepciones |
| RF-007 | Metas, umbrales y versionado en `measurement` | `measurement/tests.py` | Ejecutar cambios versionados |
| RF-008 | Ficha e indicadores individuales | `measurement/views.py` | Verificar períodos anteriores y datos semilla |
| RF-009 | Registro de actividades | `activities` | Ejecutar formularios y persistencia |
| RF-010 | Validación de campos de actividad | `activities/forms.py`, `activities/services.py` | Ejecutar formatos, obligatoriedad y fechas |
| RF-011 | Código único de evidencia | `activities/models.py`, `activities/services.py` | Ejecutar unicidad e inmutabilidad |
| RF-012 | Asociación/carga de evidencias | `activities` | Probar límites y tipos de archivo en entorno local |
| RF-013 | Aprobación, rechazo y corrección de evidencias | `activities` | Ejecutar matriz de roles y estados |
| RF-014 | Recalcular avance solo con validación válida | `activities/services.py`, `measurement` | Ejecutar regresiones de aprobación/rechazo/anulación |
| RF-015 | Atención social y gestiones asociadas | `social` | Confirmar máximo de gestiones y trazabilidad |
| RF-016 | Crear compromisos de agenda | `agenda/services.py` | Ejecutar flujo por delegación |
| RF-017 | Responsable, solicitante, territorio, área y fecha | `agenda/models.py`, `agenda/forms.py` | Ejecutar validaciones de campos obligatorios |
| RF-018 | Transiciones e historial inmutable | `agenda/models.py`, `agenda/services.py` | Ejecutar todas las transiciones y re-apertura |
| RF-019 | Plazos vencidos, por vencer y fuera de plazo | `agenda/models.py`, `agenda/services.py` | Ejecutar límites de fecha |
| RF-020 | Compromisos que aportan a medición según configuración del ítem | `agenda`, `measurement` | Ejecutar recálculo y evitar doble contabilización |
| RF-021 | Resumen colectivo por funcionario/estado | `agenda/services.py`, `agenda/views.py` | Conciliar totales contra listado filtrado |
| RF-022 | Cálculo de avance actual | `measurement/calculations.py` | Ejecutar conteos por período y estado |
| RF-023 | Porcentaje de cumplimiento | `measurement/calculations.py` | Probar meta cero, límites y redondeo |
| RF-024 | Cumplimiento ponderado | `measurement/calculations.py` | Probar tope configurable |
| RF-025 | Incentivos y penalizaciones parametrizables | `measurement/models.py`, `measurement/services.py` | Probar valores, motivos y efecto |
| RF-026 | Meta esperada según días computables | `measurement/calculations.py` | Probar inicio, término y período cerrado |
| RF-027 | Semáforo configurable | `measurement/calculations.py` | Probar límites verde/ámbar/rojo |
| RF-028 | Tablero personal | `measurement/views.py` | Validar filtros y enlaces al origen |
| RF-029 | Tablero de delegación | `measurement/services.py`, `measurement/views.py` | Conciliar agregados con funcionarios |
| RF-030 | Actividad reciente | `core/activity_metrics.py`, `core/views.py` | Probar ausencia de registros y períodos |
| RF-031 | Vista global por cargos | `measurement/views.py` | Validar navegación y agregados |
| RF-032 | Filtros por módulo | `agenda/views.py`, `activities/views.py`, `measurement` | Probar combinaciones y rangos de fecha |
| RF-033 | Exportaciones de informes | `audit`, `activities`, `agenda`, `organizations` | Comparar exportación con filtros aplicados |
| RF-034 | Transacciones, bloqueos y control optimista de concurrencia | `core/services.py`, `core/mixins.py` | Falta prueba concurrente real con dos sesiones/usuarios |
| RF-035 | Comentarios por registro | `audit/collaboration.py`, `audit/models.py` | `audit/tests.py` cubre creación, validación e inmutabilidad |
| RF-036 | Auditoría de cambios | `audit/services.py`, `audit/models.py` | Ejecutar cobertura de cada operación crítica |
| RF-037 | Alertas operativas persistentes | `core/views.py`, `audit/models.py` | `core/tests.py`; falta validación de tareas/infraestructura |
| RF-038 | Versionado de parámetros y vigencias | `measurement`, `catalogs`, `organizations` | Ejecutar comparación histórica antes/después |

## Reglas de negocio del PDF

| ID | Regla que debe respetarse | Módulo principal | Evidencia pendiente |
|---|---|---|---|
| RN-001 | Ponderadores aplicables suman 100 %, salvo excepción configurada | `measurement` | Casos borde y excepciones autorizadas |
| RN-002 | Meta cuantitativa mayor que cero; fórmula para ítem porcentual | `measurement` | Pruebas de fórmulas y límites |
| RN-003 | Avance cuenta actividades válidas del ítem/período | `measurement`, `activities` | Probar estados y duplicados |
| RN-004 | Cumplimiento = avance / meta × 100 | `measurement` | Confirmar redondeo con responsable funcional |
| RN-005 | Ponderado = porcentaje × ponderador, con tope | `measurement` | Confirmar tope institucional |
| RN-006 | Umbral colectivo inicial 80 %, configurable | `measurement` | Confirmar parámetro aprobado |
| RN-007 | Meta esperada por días computables transcurridos | `measurement` | Probar fechas inclusivas/exclusivas |
| RN-008 | Semáforo verde/ámbar/rojo con umbrales configurables | `measurement` | Confirmar 60 % y límites oficiales |
| RN-009 | Solo validación aprobada suma al avance | `activities`, `measurement` | Prueba de regresión de estados |
| RN-010 | Código de evidencia único e inmutable | `activities` | Prueba de unicidad y cambios directos |
| RN-011 | Ajustes positivos/negativos configurables | `measurement` | Confirmar valores oficiales de penalización |
| RN-012 | Hasta tres gestiones sociales por persona | `social` | Probar máximo y secuencia |
| RN-013 | Período cerrado inmutable salvo reapertura autorizada y auditada | `measurement` | Probar rechazo y reapertura con auditoría |

## Requerimientos no funcionales

| ID | Estado de implementación observado | Evidencia que falta para declararlo satisfecho |
|---|---|---|
| RNF-001 Disponibilidad | Configuración de aplicación presente | SLA mensual 99,5 %, monitoreo y evidencia de uptime AWS |
| RNF-002 Rendimiento | Paginación e índices/querysets optimizados en varios módulos | Mediciones p50/p95; objetivos 2 s y 5 s bajo carga |
| RNF-003 Concurrencia | `transaction.atomic`, `select_for_update` y huella SHA-256 | Prueba real de dos sesiones guardando simultáneamente |
| RNF-004 Autenticación | Usuario individual, hash de contraseña y recuperación | MFA/directorio institucional, si se exige |
| RNF-005 Autorización | Roles, permisos funcionales y ámbito por delegación; `ADMIN_SISTEMA` funcional | Matriz completa de endpoints y operaciones |
| RNF-006 Confidencialidad | Configuración HTTPS/cookies/CSRF para producción | TLS, cifrado de respaldos y secretos AWS verificados |
| RNF-007 Integridad | Validaciones, FK, constraints y transacciones | Pruebas de carrera y consistencia de base de datos |
| RNF-008 Auditoría | Eventos con actor, fecha, entidad y valores; historial protegido | Confirmar cobertura completa y política de retención |
| RNF-009 Privacidad | Ámbito y roles limitan acceso | Revisión de campos personales, exportaciones y retención legal |
| RNF-010 Respaldo/recuperación | No se acredita automatización dentro del código | Backup AWS, RPO 24 h, RTO 4 h y restauración ensayada |
| RNF-011 Usabilidad | Plantillas comunes, mensajes, filtros y paginación | Pruebas de usuario y validación de tareas frecuentes |
| RNF-012 Accesibilidad | Etiquetas y foco presentes en parte de la UI | Auditoría WCAG, contraste, teclado y lector de pantalla |
| RNF-013 Compatibilidad | Diseño web adaptable y Bootstrap | Pruebas reales en Chrome/Edge y dispositivos móviles |
| RNF-014 Escalabilidad | Apps separadas y modelo relacional extensible | Prueba de volumen y dimensionamiento de infraestructura |
| RNF-015 Mantenibilidad | Separación por apps, modelos, servicios y formularios | Lint, revisión estática y documentación final |
| RNF-016 Interoperabilidad | Exportación estructurada Excel | Contratos/API externa si la institución los requiere |
| RNF-017 Gestión de evidencias | Validación de formatos/tamaño en aplicación | Antivirus real, retención y borrado seguro |
| RNF-018 Monitoreo | Auditoría, notificaciones y alertas operativas | Métricas de infraestructura, errores y capacidad AWS |

## Pruebas y resultado

- En el proyecto base se identifican suites en `organizations`, `catalogs`, `measurement`, `activities`, `agenda`, `social`, `audit`, `core` y `websocket`.
- Este paquete agrega 11 pruebas para cuenta automática desde servicio y Django Admin, idempotencia, preservación de ROOT, dry-run, rol `ADMIN_SISTEMA`, desactivación segura, rutas correctas del dashboard, huella de concurrencia y carga de recursos responsive.
- Se validó sintaxis con `py_compile`/`compileall` y la integridad del ZIP.
- `manage.py check`, la suite Django y la cobertura no se pudieron ejecutar en este entorno porque Django no está instalado y no hay acceso a Internet para instalar dependencias.
- No se afirma 100 % de cobertura ni 100 % de conformidad RNF hasta ejecutar las pruebas en el entorno local y completar las validaciones externas indicadas.
