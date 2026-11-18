# Solicitudes vecinales y regalos de Navidad

## Alcance

La funcionalidad se implementa sobre el modelo existente del diagrama E-R, sin crear tablas o entidades nuevas:

- `COMPROMISO`: representa la solicitud vecinal, su categoría, canal, RUT del solicitante, solución, estado de solicitud, fecha de creación y fecha propuesta de solución.
- `HISTORIAL_TRANSICIONES`: conserva eventos y cambios de estado en orden cronológico. El modelo ya impide editar o eliminar transiciones.
- `USUARIO`: se amplía con el RUT opcional y único del usuario social para verificar al adulto/tutor contra la semilla existente.
- Se mantienen las relaciones originales con `DELEGACION` y `FUNCIONARIO`.

No se crea una tabla `Solicitud`, `Regalo`, `Menor` o `Evento`. Esto conserva el conjunto de entidades del diagrama. Los campos agregados son extensiones de las entidades existentes.

## Flujo público

1. Desde el formulario de acceso se puede abrir el formulario vecinal sin iniciar sesión.
2. El vecino ingresa nombre, RUT, relación con la junta de vecinos, delegación, territorio, área y descripción.
3. El RUT se normaliza y valida con módulo 11 en servidor.
4. El canal queda fijado como `Presencial`; el usuario no puede alterarlo.
5. Para una solicitud general, la delegación se selecciona en el formulario.
6. Para un regalo, primero se verifica que el RUT del adulto/tutor exista en `social.UsuarioSocial`. La delegación se obtiene desde ese registro; se ignora la delegación elegida en el formulario.
7. Tras validar al tutor, se consulta el RUT del menor. El sistema informa si ya fue registrado en la misma delegación o en otra.
8. La inscripción del menor se protege con un campo `UNIQUE` en la base de datos (`Compromiso.rut_menor`), no solo con una validación de formulario. Así se rechazan duplicados concurrentes y entre delegaciones.
9. La fecha de creación se asigna desde el servidor. No forma parte del formulario y el modelo la conserva en modificaciones.

## Estados y trazabilidad

Estados de solicitud: `Creado` → `Pendiente` → `Proceso` → `Concluido`. Se permite devolver `Proceso` a `Pendiente`; una solicitud concluida no admite cambios de gestión.

La solución asignada, la fecha propuesta y los eventos se registran en el mismo compromiso y su historial. La fecha/hora del evento es automática. El Excel exporta dos hojas: resumen de solicitudes y trazabilidad cronológica.

## Visibilidad

| Perfil/cargo | Alcance |
|---|---|
| Delegado | Todas las solicitudes de su delegación, sin ampliar el alcance aunque tenga otros roles. |
| Gestor Social | Solicitudes sociales y solicitudes asignadas. |
| Apoyo Administrativo | Consulta de solicitudes de su delegación. Puede ingresar solicitudes usando el formulario público en representación del vecino. |
| Organizaciones Comunitarias | Solicitudes de organizaciones vecinales. |
| Gestión y Planificación | Consulta de solicitudes de su delegación. |
| Coordinador de Servicios Comunitarios | Aseo, ornato, espacios públicos y servicios comunitarios. |
| Administrador/Coordinador | Según el alcance de delegaciones configurado en el usuario. |

La visibilidad se calcula en servidor. El menú solo mejora la navegación y no reemplaza la autorización de vistas.

## Semilla

No se generan ni modifican registros. La migración agrega `social.UsuarioSocial.rut` nullable y único. Para habilitar regalos, la semilla que mantendrá el equipo debe poblar ese campo con el RUT normalizado de cada adulto/tutor (`12345678-5`, sin puntos). Los registros antiguos sin RUT no podrán validar tutores hasta que se complete ese dato. Los menores no se precargan ni se insertan automáticamente.

## Instalación local

1. Respaldar la base de datos.
2. Copiar los archivos del ZIP respetando sus rutas relativas.
3. Ejecutar `python manage.py migrate`.
4. Ejecutar `python manage.py check`.
5. Ejecutar `python manage.py test`.
6. Probar manualmente el formulario público, la visibilidad por cargo, la actualización de estado y la exportación Excel.

No ejecutar `loaddata` ni scripts de semilla para esta actualización.

## Seguridad y límites conocidos

- CSRF permanece activo en formularios POST.
- RUT se valida en backend; el JavaScript solo controla la presentación.
- La verificación de tutor/menor usa sesión y tiene limitación de intentos por IP mediante el caché Django. En producción debe configurarse un caché compartido (por ejemplo Redis) para que el límite sea consistente entre procesos.
- El RUT del menor es único en base de datos. La consulta previa no sustituye la restricción única, que es la defensa ante concurrencia.
- La aplicación no recibe documentos ni adjuntos en este módulo.
- MFA, HTTPS, backups automatizados, antivirus de archivos, monitorización de infraestructura y pruebas de carga AWS dependen de la configuración del entorno; no se declaran aprobados por esta entrega de código.
