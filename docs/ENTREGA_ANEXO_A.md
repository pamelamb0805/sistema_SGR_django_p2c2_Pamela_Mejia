# Entrega técnica – ANEXO A SGR

## Base de trabajo y alcance

- Repositorio: `pamelamb0805/sistema_SGR_django_p2c2_Pamela_Mejia`.
- Rama identificada en el ZIP recibido: `mejoras_finales`.
- Commit local incluido en el ZIP: `6712b0b84e9d4b78b97b00d08a01e25363020144`.
- Especificación aplicada: `ANEXO A.pdf`, `Guia_Proyecto_Software_SGR_Alumnos.pdf`, `Historias_usuarios_requerimientos.pdf` y `diagramas proyecto integrado.drawio.xml`.

**Importante sobre los insumos:** en `sistema_sgr_archivos.zip` se recibió `Historias_usuarios_requerimientos.pdf`, no el archivo Excel `Historias_usuarios_requerimientos.xlsx` mencionado en la solicitud. También se menciona `mockups.pdf` en el ANEXO A, pero ese archivo no venía en el ZIP. Por ello, la matriz de requisitos se contrastó con la versión PDF entregada y la UI existente. Si el Excel contiene celdas, RN o criterios adicionales, deben incorporarse en una revisión posterior antes de afirmar conformidad literal con ese Excel.

## Arquitectura de datos conservada

No se reemplazaron ni renombraron modelos ni se generaron migraciones de esquema en esta actualización. Se conserva el modelo de dominio implementado en el proyecto y representado por el diagrama:

- `organizations`: `Delegacion`, `Cargo`, `ItemMedible`, `Funcionario`, `Rol`, `FuncionarioRol`, `Usuario` y `PasswordResetCode`.
- `catalogs`: `Catalogo`, con discriminador `tipo_catalogo` y autorrelación `tipo_atencion_padre` para Subatención.
- `social`: `UsuarioSocial` (persona solicitante/caso) y `AtencionSocial` (gestión/atención), con referencias a tipo, subatención, funcionario responsable y delegación.

Las subatenciones siguen siendo elementos del catálogo relacionados mediante FK con un tipo de atención. No se duplicó esta entidad creando tablas paralelas, porque eso alteraría la arquitectura existente.

## Cambios de código de esta actualización

1. **Contexto activo de delegación:** se añadió `DelegacionActivaMiddleware`, que valida cada ID de sesión contra la lista de delegaciones activas autorizadas en servidor.
2. **Cambio de contexto:** se añadió el endpoint POST `contexto/delegacion/`, protegido por autenticación y CSRF. Una selección no autorizada se rechaza y se registra como acceso denegado.
3. **Cabecera compartida:** `base.html` muestra código y nombre de la delegación activa. Si hay más de una autorizada, muestra un selector; al cambiar, advierte si detecta campos modificados en formularios.
4. **Recuperación de contraseña:** la vigencia por defecto se ajustó a 600 segundos (10 minutos), con reenvío cada 45 segundos, máximo de 5 intentos y 3 reenvíos; los valores se parametrizan mediante `SGR_RESET_CODE_*`.
5. **Aislamiento por contexto:** `filtrar_por_ambito` limita los querysets al contexto activo para usuarios con alcance múltiple o global. El módulo de atención social también aplica ese contexto a la lectura y escritura.
6. **Corrección de autorización:** se eliminó la definición duplicada de `get_delegaciones_autorizadas_ids` que sobreescribía la versión restrictiva. Ahora las delegaciones adicionales solo se consideran para roles con alcance `multiples`; los IDs se limitan a delegaciones activas.
7. **Endurecimiento de producción:** `DEBUG` queda desactivado por defecto y se incorporan HSTS, política de referencia y cabecera de proxy HTTPS al operar con `DEBUG=False`. Para desarrollo local se debe establecer `DEBUG=True` en `.env` y para producción configurar Redis (`REDIS_URL`).
8. **Pruebas nuevas:** `core/test_delegacion_contexto.py` cubre IDs autorizados, rechazo de una delegación ajena, aceptación de una delegación adicional autorizada, filtrado por contexto activo y cambio de contexto. `core/test_recuperacion_clave.py` cubre envío, no divulgación de existencia, hash, expiración, intento incorrecto y flujo completo de cambio de contraseña.

## Estado de los componentes del ANEXO A según el código revisado

| Componente | Implementación encontrada | Validación que falta ejecutar en entorno Django |
|---|---|---|
| Login | `SGRLoginView` y `SGRAuthenticationForm`; admite usuario/correo y valida cuenta activa | Prueba integrada con base de datos y usuarios semilla |
| Recuperar contraseña | Flujo en `core/views.py`, modelo `PasswordResetCode`, hash del código, expiración e intentos | SMTP real, reenvío y límites de frecuencia en despliegue |
| Validar código | Vista y formulario de código de seis dígitos | Casos válido, inválido, vencido, reutilizado, intentos agotados y reenvío |
| Nueva contraseña | Formulario con confirmación y validadores Django; código se invalida al completar | Verificar login con nueva clave y rechazo de anterior |
| CRUD Delegaciones | Listado, creación, edición, activación/desactivación, filtros y Excel | Casos de relaciones, duplicados, exportación con filtros y autorización |
| CRUD Roles | CRUD, permisos funcionales y alcance autorizado | Matriz de privilegio mínimo y segregación de funciones |
| CRUD Usuarios | CRUD de cuenta, correo, roles, delegaciones autorizadas y estado | Restricciones de cuenta inactiva y permisos por actor |
| CRUD Ítems y metas | Ítems vinculados a Cargo; metas en `measurement`; estado de ítem mediante vigencia | Confirmar casos completos de metas y su relación con cargo/período |
| CRUD Tipo/Subatención | CRUD unificado de `Catalogo`, separado por `tipo_catalogo`; FK padre para Subatención | Probar restricciones, desactivación y relación en uso |
| Ingreso de atención | Alta de caso y primera gestión en `social`; tipo/subatención, delegación, funcionario y fechas | Probar solicitante duplicado, subatención dependiente, doble envío y filtros de contexto |

La persistencia se realiza mediante modelos/servicios Django; no se consideraron como operativas funciones meramente visuales. El sistema contiene más módulos de la guía general (actividades, agenda, medición, evidencias, auditoría y colaboración), pero el foco de esta entrega es el alcance explícito del ANEXO A.

## Requerimientos no funcionales: controles presentes y límites

| RNF | Control/código identificado | Evidencia pendiente / dependencia externa |
|---|---|---|
| RNF-001 Disponibilidad | Configuración de despliegue y manejo de errores | SLA mensual 99,5 % y monitoreo real AWS |
| RNF-002 Rendimiento | Querysets con `select_related`/`prefetch_related`, paginación e índices de modelos | Medir p50/p95 y verificar objetivo de 2 s bajo carga |
| RNF-003 Concurrencia | Uso de `transaction.atomic`, `select_for_update`, constraints únicos y Channels | Prueba de concurrencia con usuarios simultáneos |
| RNF-004 Autenticación | Usuario individual, hash de contraseña, sesión, recuperación | MFA e integración con directorio institucional no están demostrados |
| RNF-005 Autorización | Roles, permisos funcionales y ámbito validado en servidor | Ejecutar matriz completa por endpoint/operación |
| RNF-006 Confidencialidad | HTTPS en producción, cookies seguras, CSRF, `X_FRAME_OPTIONS`, `nosniff` | Confirmar TLS, cifrado de respaldos y secretos en AWS |
| RNF-007 Integridad | Validaciones de formularios/modelos, FK, constraints y transacciones | Pruebas de carrera concurrente y duplicados |
| RNF-008 Auditoría | Servicios de auditoría con actor, fecha, evento, entidad y valores | Verificar inmutabilidad/retención y cobertura de cada operación |
| RNF-009 Privacidad | Restricción por roles/ámbito y minimización de datos exportados | Revisar permisos de cada campo sensible y política de retención institucional |
| RNF-010 Respaldo | No se acredita automatización en el código recibido | Configurar backups administrados AWS, RPO 24 h/RTO 4 h y restauración ensayada |
| RNF-011 Usabilidad | Template común, mensajes, filtros, paginación y SweetAlert2 | Pruebas con usuarios y validación visual institucional |
| RNF-012 Accesibilidad | Etiquetas, foco y navegación básica presentes | Auditoría WCAG, contraste y pruebas con teclado/lector de pantalla |
| RNF-013 Compatibilidad | Aplicación web adaptable | Pruebas en Chrome/Edge y móviles soportados |
| RNF-014 Escalabilidad | Modelo relacional normalizado por dominios y configuración de catálogos | Prueba de volumen y dimensionamiento AWS |
| RNF-015 Mantenibilidad | Apps separadas, servicios, formularios, modelos y configuración por entorno | Revisión estática/lint y documentación de mantenimiento |
| RNF-016 Interoperabilidad | Exportaciones Excel y endpoints JSON internos | Contratos/API externa no especificados en el ANEXO A |
| RNF-017 Gestión de evidencias | Límites de carga, extensiones permitidas y relaciones de evidencia | Antivirus/escaneo real, retención y borrado seguro |
| RNF-018 Monitoreo | Auditoría, notificaciones y alertas operativas | Métricas de infraestructura, alertas de capacidad y dashboards AWS |

No se declara implementado MFA, antivirus, backups AWS, SLA ni pruebas de estrés porque dependen de infraestructura/servicios que no vienen en los ZIP. Tampoco se debe afirmar que esos RNF están aprobados sin evidencias.

## Ejecución local

1. Descomprimir el ZIP de actualización en una carpeta nueva y conservar el proyecto original como respaldo.
2. Copiar el `.env.example` a `.env` y completar los valores locales. Para desarrollo: `DEBUG=True`. No copiar secretos al repositorio.
3. Crear y activar un entorno virtual e instalar `pip install -r requirements.txt`.
4. Configurar MySQL/MariaDB según `.env` y ejecutar `python manage.py migrate`.
5. Crear o cargar los usuarios, roles, delegaciones, catálogos y demás datos semilla según el procedimiento del equipo.
6. Ejecutar `python manage.py check`.
7. Ejecutar pruebas: `python manage.py test`.
8. Medir cobertura: `coverage run manage.py test && coverage report -m` (instalar `coverage` en el entorno).

## Protocolo de pruebas para la rúbrica

Para cada escenario registrar: ID RF/RNF, módulo, precondición, datos de prueba, pasos, esperado, obtenido, estado, evidencia (captura/log), responsable y fecha. Ejecutar pruebas negativas y de borde además del flujo feliz. Después de corregir un defecto, repetir el caso y sus regresiones relacionadas.

Para carga, definir antes de ejecutar el umbral aceptable, entorno AWS, tamaño de base de datos, concurrencia por escalones, duración, solicitudes/s, latencia media y p95, tasa de errores, CPU y memoria. No realizar pruebas de estrés sobre producción sin autorización.

## Resultado de validación de esta sesión

- Compilación sintáctica de archivos Python (`compileall`): correcta en el entorno de análisis.
- Se identificaron 262 métodos de prueba existentes y se agregaron 10 escenarios automatizados (272 métodos `test_*` en total al empaquetar).
- `manage.py check` y `manage.py test`: **no ejecutados**, porque este entorno no dispone de Django y no tuvo acceso a Internet para instalar las dependencias.
- Cobertura porcentual: **no medida**. No se declara 100 % de cobertura ni 100 % de aprobación sin ejecutar el conjunto de pruebas en el entorno real del proyecto.
- No se ejecutaron migraciones, semillas, AWS ni envíos SMTP.
