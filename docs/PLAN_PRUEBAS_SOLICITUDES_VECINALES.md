# Plan de pruebas: solicitudes vecinales y regalos

**Estado de ejecución de esta entrega:** pruebas estáticas ejecutadas; pruebas Django/MySQL y de navegador pendientes de ejecución en el entorno del proyecto. No marcar como 100 % aprobado hasta adjuntar evidencia real.

| ID | Requisito | Escenario | Resultado esperado |
|---|---|---|---|
| SOL-001 | RF solicitud pública | Abrir el formulario sin sesión | Se muestra el formulario y no exige autenticación. |
| SOL-002 | RNF-004 | Enviar solicitud con usuario anónimo | El POST público funciona con CSRF; no crea sesión autenticada. |
| SOL-003 | RNF-007 | RUT válido con puntos y guion | Se normaliza y acepta. |
| SOL-004 | RNF-007 | RUT con DV incorrecto, incompleto o vacío | Se rechaza en servidor; no se crea compromiso. |
| SOL-005 | RF solicitud | Cada una de las cuatro relaciones vecinales | Se conserva la opción seleccionada. |
| SOL-006 | RF solicitud | Cambiar el canal desde el navegador | El servidor conserva `Presencial`. |
| SOL-007 | RNF-007 | Intentar enviar `fecha_creacion` desde POST | El campo se ignora; la fecha se asigna en servidor. |
| SOL-008 | RNF-008 | Modificar fecha de creación desde una instancia del modelo | El `save()` conserva el valor original. |
| SOL-009 | RF solicitud | Crear una solicitud general | Se asigna responsable activo de la delegación y estado `Creado`. |
| SOL-010 | RF solicitud | Delegación sin funcionarios activos | Se rechaza con mensaje controlado y no crea solicitud. |
| SOL-011 | RF regalos | RUT de tutor válido pero ausente de `UsuarioSocial` | Se impide continuar con el regalo. |
| SOL-012 | RF regalos | Tutor registrado y delegación elegida distinta | Se usa la delegación del tutor. |
| SOL-013 | RF regalos | RUT de menor no inscrito | Se informa disponibilidad y permite continuar. |
| SOL-014 | RF regalos | Menor ya inscrito en la misma delegación | Se informa duplicado en la misma delegación y bloquea. |
| SOL-015 | RF regalos | Menor ya inscrito en otra delegación | Se informa duplicado en otra delegación y bloquea. |
| SOL-016 | RNF-003/RNF-007 | Dos solicitudes concurrentes con el mismo RUT de menor | Solo una transacción puede guardar; la otra recibe error controlado por `UNIQUE`. |
| SOL-017 | RF solicitud | Avanzar Creado → Pendiente → Proceso → Concluido | Cada cambio genera transición con fecha/funcionario. |
| SOL-018 | RNF-007 | Intentar saltar de Creado a Concluido | Se rechaza la transición inválida. |
| SOL-019 | RNF-008 | Editar solución y fecha propuesta | Se registra evento con los valores anteriores/nuevos. |
| SOL-020 | RNF-008 | Agregar varios eventos | Se conservan y muestran cronológicamente. |
| SOL-021 | RNF-008 | Intentar editar/eliminar una transición histórica | El modelo lo rechaza. |
| SOL-022 | RF solicitud | Cambiar fecha propuesta | Se permite y la fecha de creación permanece intacta. |
| SOL-023 | RNF-005 | Delegado consulta su delegación | Ve todas las solicitudes de su delegación. |
| SOL-024 | RNF-005 | Delegado altera ID/URL para otra delegación | La solicitud no aparece; responde 404. |
| SOL-025 | RNF-005 | Gestor Social consulta | Solo ve solicitudes sociales y asignadas. |
| SOL-026 | RNF-005 | Organizaciones Comunitarias consulta | Solo ve solicitudes de organizaciones vecinales. |
| SOL-027 | RNF-005 | Coordinador Servicios Comunitarios consulta | Solo ve aseo, ornato, espacios públicos y servicios comunitarios. |
| SOL-028 | RNF-005/RNF-009 | Usuario sin cargo/rol habilitado consulta la lista | No ve el módulo ni obtiene registros por URL directa. |
| SOL-029 | RF-029 | Delegado inicia sesión | Dashboard muestra creadas, pendientes y concluidas de su delegación. |
| SOL-030 | RF-033/RNF-016 | Exportar con filtros | Excel contiene todos los registros autorizados filtrados, sin tokens ni RUT del menor. |
| SOL-031 | RNF-008/RNF-016 | Exportar trazabilidad | Segunda hoja contiene folio, fecha, actor, estados y evento ordenados cronológicamente. |
| SOL-032 | RNF-011/RNF-012 | Navegación por teclado y lector de pantalla | Controles con etiquetas, mensajes y foco utilizables. |
| SOL-033 | RNF-018 | Superar límite de intentos de verificación | Se responde HTTP 429 y no se procesa el exceso. |
| SOL-034 | RNF-003 | Carga concurrente de creación y cambios de estado | No se pierden eventos ni se duplican menores; medir latencia y errores. |

## Evidencia que debe adjuntarse al protocolo

Por cada caso: fecha/hora, ambiente, versión/commit, datos sintéticos, pasos, esperado, obtenido, estado (Aprobado/Rechazado/Pendiente), captura/log, responsable y defecto asociado. Para estrés: herramienta, concurrencia, duración, RPS, latencia promedio y p95, errores, CPU y memoria.

## Criterios de salida

- Ningún caso crítico de validación, unicidad, acceso horizontal o trazabilidad puede quedar fallido.
- Repetir los casos afectados después de corregir defectos.
- Ejecutar pruebas en MySQL compatible con el entorno objetivo; no basta con pruebas SQLite para certificar índices y concurrencia de MySQL.
- Ejecutar pruebas de navegador en Chrome y Edge soportados.
- Ejecutar `python manage.py check --deploy` con configuración de producción antes de AWS.
