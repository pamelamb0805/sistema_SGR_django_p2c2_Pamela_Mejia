
document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    const root = document.getElementById("sgrTutorialChat");
    if (!root || root.dataset.initialized === "true") return;
    root.dataset.initialized = "true";

    const $ = (id) => document.getElementById(id);

    const toggle = $("sgrChatToggle");
    const close = $("sgrChatClose");
    const windowChat = $("sgrChatWindow");
    const messages = $("sgrChatMessages");
    const options = $("sgrChatOptions");
    const tutorialPanel = $("sgrChatTutorial");
    const questionArea = $("sgrChatQuestionArea");
    const form = $("sgrChatForm");
    const input = $("sgrChatInput");

    const required = [
        toggle, close, windowChat, messages, options,
        tutorialPanel, questionArea, form, input,
        $("sgrTutorialTitle"), $("sgrTutorialProgress"),
        $("sgrTutorialProgressBar"), $("sgrTutorialStep"),
        $("sgrTutorialPrevious"), $("sgrTutorialNext"),
        $("sgrTutorialExit")
    ];

    if (required.some((element) => !element)) return;

    const moduleName = root.dataset.module || "";
    const urlName = root.dataset.urlName || "";

    let currentTutorial = null;
    let currentStep = 0;

    function getLink(id) {
        const element = $(id);
        return element ? element.getAttribute("href") : null;
    }

    function firstAvailableLink(ids) {
        for (const id of ids || []) {
            const destination = getLink(id);
            if (destination) return destination;
        }
        return null;
    }

    function addMessage(text, type = "bot", linkUrl = null, linkLabel = null) {
        const message = document.createElement("div");
        message.className = "sgr-chat-message sgr-chat-" + type;

        if (type === "bot") {
            const avatar = document.createElement("div");
            avatar.className = "sgr-chat-message-avatar";
            avatar.innerHTML = '<i class="bi bi-mortarboard-fill" aria-hidden="true"></i>';
            message.appendChild(avatar);
        }

        const bubble = document.createElement("div");
        bubble.className = "sgr-chat-bubble";

        const paragraph = document.createElement("p");
        paragraph.textContent = text;
        bubble.appendChild(paragraph);

        if (linkUrl) {
            const anchor = document.createElement("a");
            anchor.href = linkUrl;
            anchor.textContent = linkLabel || "Abrir sección";
            anchor.className = "d-inline-block mt-2";
            bubble.appendChild(anchor);
        }

        message.appendChild(bubble);
        messages.appendChild(message);
        messages.scrollTop = messages.scrollHeight;
    }

    function addActionButton(label, destination, icon = "bi-arrow-up-right") {
        if (!destination) return;

        const button = document.createElement("a");
        button.href = destination;
        button.className = "btn btn-sm btn-outline-danger ms-5 mb-2";
        button.innerHTML =
            '<i class="bi ' + icon + ' me-1" aria-hidden="true"></i>';
        button.appendChild(document.createTextNode(label));
        messages.appendChild(button);
        messages.scrollTop = messages.scrollHeight;
    }

    function openChat() {
        windowChat.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        input.focus();
    }

    function closeChat() {
        windowChat.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
    }

    function showOptions() {
        options.hidden = false;
        tutorialPanel.hidden = true;
        questionArea.hidden = false;
    }

    const tutorials = {
        dashboard: {
            title: "Panel principal",
            links: ["chatDashboard"],
            steps: [
                {
                    title: "Paso 1. Reconocer el panel principal",
                    text: "El panel principal es el punto de entrada al Sistema de Gestión de Resultados. Desde esta pantalla puedes consultar los accesos y la información que se encuentra habilitada para tu cuenta."
                },
                {
                    title: "Paso 2. Utilizar el menú de navegación",
                    text: "El menú lateral organiza las funciones por módulo. Selecciona la sección que necesitas. Las opciones disponibles dependen de los permisos asociados a tu usuario."
                },
                {
                    title: "Paso 3. Revisar los indicadores",
                    text: "Consulta los indicadores y resúmenes que presenta el panel. Considera el período y el ámbito al que corresponde la información antes de interpretar los resultados."
                },
                {
                    title: "Paso 4. Consultar notificaciones",
                    text: "Utiliza el ícono de campana de la barra superior para revisar las notificaciones disponibles. Abre cada aviso para consultar el antecedente relacionado, cuando corresponda."
                },
                {
                    title: "Paso 5. Gestionar tu sesión",
                    text: "Desde el menú de usuario puedes acceder a las opciones de perfil disponibles y cerrar sesión. Cierra la sesión al terminar de utilizar el sistema, especialmente en equipos compartidos."
                }
            ]
        },

        actividades: {
            title: "Registro y consulta de actividades",
            links: ["chatActividades"],
            steps: [
                {
                    title: "Paso 1. Ingresar al módulo",
                    text: "Abre Actividades desde el menú lateral. El listado presenta los registros que puedes consultar de acuerdo con tu perfil y ámbito de acceso.",
                    action: "chatActividades",
                    actionLabel: "Abrir actividades"
                },
                {
                    title: "Paso 2. Iniciar un registro",
                    text: "Si tu cuenta tiene permiso para registrar, utiliza el botón «Registrar actividad». Se abrirá el formulario de creación.",
                    action: "chatNuevaActividad",
                    actionLabel: "Registrar actividad"
                },
                {
                    title: "Paso 3. Completar los antecedentes",
                    text: "Completa los campos que muestra el formulario. La pantalla identifica los campos obligatorios. Revisa especialmente la fecha, el funcionario, la clasificación, el período y la descripción de la acción ejecutada, según los campos que estén habilitados."
                },
                {
                    title: "Paso 4. Revisar y guardar",
                    text: "Antes de guardar, verifica que la información describa correctamente la actividad realizada. Si el sistema muestra errores, lee los mensajes junto a los campos, corrige los datos y vuelve a enviar el formulario."
                },
                {
                    title: "Paso 5. Consultar el detalle",
                    text: "Desde el listado puedes abrir el detalle de una actividad. Allí se muestran sus antecedentes, estado, período y datos asociados."
                },
                {
                    title: "Paso 6. Adjuntar respaldos",
                    text: "Cuando la operación y tus permisos lo permitan, utiliza «Adjuntar evidencia» desde el detalle de la actividad. El formulario permite cargar archivos JPG, JPEG, PNG o PDF, sujetos a los límites configurados en el sistema."
                },
                {
                    title: "Paso 7. Revisar el estado de la evidencia",
                    text: "Después de adjuntar un respaldo, consulta su estado. La revisión y decisión de validación corresponden a los perfiles autorizados."
                }
            ]
        },

        validaciones: {
            title: "Validación de evidencias",
            links: ["chatValidaciones"],
            steps: [
                {
                    title: "Paso 1. Abrir la bandeja",
                    text: "Ingresa a Validación de evidencias. Esta sección está destinada a los perfiles autorizados para revisar respaldos.",
                    action: "chatValidaciones",
                    actionLabel: "Abrir validaciones"
                },
                {
                    title: "Paso 2. Seleccionar una evidencia",
                    text: "Abre un registro pendiente. Revisa el código de la evidencia y los antecedentes de la actividad asociada."
                },
                {
                    title: "Paso 3. Examinar el archivo",
                    text: "Abre el archivo adjunto y comprueba que sea legible y que corresponda a la actividad informada. Contrasta el respaldo con la descripción y los antecedentes disponibles."
                },
                {
                    title: "Paso 4. Registrar la decisión",
                    text: "Selecciona la decisión que corresponda en el formulario. Si rechazas la evidencia o solicitas una corrección, debes ingresar una observación que explique el motivo."
                },
                {
                    title: "Paso 5. Confirmar la revisión",
                    text: "Antes de enviar, revisa la decisión y la observación. El sistema registra la revisión y la incorpora al historial de la evidencia."
                },
                {
                    title: "Paso 6. Considerar las restricciones",
                    text: "El sistema impide que un usuario valide una evidencia asociada a una actividad propia. Si aparece ese aviso, no intentes continuar con esa validación."
                }
            ]
        },

        agenda: {
            title: "Agenda colectiva y compromisos",
            links: ["chatAgenda", "chatResumenAgenda"],
            steps: [
                {
                    title: "Paso 1. Consultar la agenda",
                    text: "Ingresa a Agenda colectiva para revisar los compromisos disponibles para tu usuario. El listado permite consultar los antecedentes y el estado de cada compromiso.",
                    action: "chatAgenda",
                    actionLabel: "Abrir agenda"
                },
                {
                    title: "Paso 2. Registrar un compromiso",
                    text: "Si tienes autorización, selecciona «Nuevo compromiso». Completa el formulario con los antecedentes solicitados.",
                    action: "chatNuevoCompromiso",
                    actionLabel: "Nuevo compromiso"
                },
                {
                    title: "Paso 3. Revisar los datos",
                    text: "Comprueba el origen, solicitante, territorio, responsable, fecha comprometida y demás antecedentes que solicite el formulario. Verifica especialmente la fecha y la persona responsable antes de guardar."
                },
                {
                    title: "Paso 4. Consultar el detalle",
                    text: "Abre un compromiso del listado para revisar sus datos, plazo, estado, observaciones y acciones disponibles según tus permisos."
                },
                {
                    title: "Paso 5. Actualizar o reasignar",
                    text: "Cuando tengas autorización, utiliza las acciones del detalle para actualizar el estado o reasignar al responsable. Revisa cuidadosamente los cambios antes de confirmarlos."
                },
                {
                    title: "Paso 6. Revisar el historial",
                    text: "El detalle dispone de una opción para consultar el historial del compromiso. Úsala para revisar los cambios registrados."
                },
                {
                    title: "Paso 7. Consultar el resumen",
                    text: "El resumen de agenda presenta información colectiva de los compromisos que puedes consultar. Puedes acceder a él desde la sección correspondiente.",
                    action: "chatResumenAgenda",
                    actionLabel: "Abrir resumen de agenda"
                }
            ]
        },

        social: {
            title: "Atención social y gestión de casos",
            links: ["chatAtencionSocial"],
            steps: [
                {
                    title: "Paso 1. Ingresar a Atención social",
                    text: "Abre Atención social para consultar los casos que están disponibles dentro de tu ámbito de acceso.",
                    action: "chatAtencionSocial",
                    actionLabel: "Abrir atención social"
                },
                {
                    title: "Paso 2. Buscar un caso",
                    text: "Utiliza los filtros del listado para localizar los registros. Comprueba los datos de la persona atendida y los antecedentes del caso antes de abrirlo."
                },
                {
                    title: "Paso 3. Registrar un caso",
                    text: "Si tu perfil tiene autorización, utiliza «Registrar caso». Completa los antecedentes solicitados y revisa la información antes de guardar.",
                    action: "chatNuevoCaso",
                    actionLabel: "Registrar caso"
                },
                {
                    title: "Paso 4. Revisar la clasificación",
                    text: "Comprueba que el tipo de atención y la subatención seleccionados correspondan al caso. Si el sistema utiliza un selector dependiente, selecciona primero el tipo de atención para cargar las subatenciones disponibles."
                },
                {
                    title: "Paso 5. Abrir el detalle",
                    text: "Desde el listado puedes abrir el detalle del caso para revisar la información de la persona atendida, territorio, delegación y estado."
                },
                {
                    title: "Paso 6. Registrar una gestión",
                    text: "Cuando corresponda y tengas autorización, ingresa al caso y utiliza la opción para agregar una gestión. La delegación, el responsable y la fecha de registro se asignan automáticamente según la configuración del sistema."
                },
                {
                    title: "Paso 7. Consultar estadísticas",
                    text: "Si tu perfil tiene acceso, puedes consultar las estadísticas sociales para revisar información consolidada.",
                    action: "chatEstadisticasSociales",
                    actionLabel: "Consultar estadísticas sociales"
                }
            ]
        },

        desempeno: {
            title: "Consulta de mi desempeño",
            links: ["chatDesempeno"],
            steps: [
                {
                    title: "Paso 1. Abrir Mi desempeño",
                    text: "Ingresa a Mi desempeño para consultar la información asociada a tu usuario y a los períodos de medición disponibles.",
                    action: "chatDesempeno",
                    actionLabel: "Abrir mi desempeño"
                },
                {
                    title: "Paso 2. Identificar el período",
                    text: "Comprueba a qué período corresponde la información mostrada. Los resultados deben interpretarse considerando las fechas y reglas aplicables a ese período."
                },
                {
                    title: "Paso 3. Revisar metas e ítems",
                    text: "Consulta las metas e ítems medibles que aparecen asociados a tu desempeño. Revisa sus ponderaciones y los antecedentes que se muestran."
                },
                {
                    title: "Paso 4. Interpretar los resultados",
                    text: "Revisa los avances y resultados presentados por el sistema. Si detectas una diferencia o tienes dudas sobre un dato, consulta a la unidad responsable de la medición."
                },
                {
                    title: "Paso 5. Distinguir consulta y administración",
                    text: "Mi desempeño es una vista de consulta personal. La creación o modificación de metas y períodos corresponde a funciones de administración y requiere permisos específicos."
                }
            ]
        },

        supervision: {
            title: "Administración de metas y medición",
            links: ["chatMetas", "chatPeriodos", "chatSemaforo"],
            steps: [
                {
                    title: "Paso 1. Abrir la administración de metas",
                    text: "Si tu perfil tiene permisos de supervisión, ingresa al listado de metas. Desde allí puedes consultar registros y acceder a las acciones que estén habilitadas.",
                    action: "chatMetas",
                    actionLabel: "Abrir metas"
                },
                {
                    title: "Paso 2. Aplicar filtros",
                    text: "En el listado puedes filtrar por período, cargo, funcionario e ítem medible. Utiliza los filtros para acotar la consulta y revisa que los criterios seleccionados sean correctos."
                },
                {
                    title: "Paso 3. Crear o editar una meta",
                    text: "Cuando esté habilitado, utiliza la opción para crear o editar una meta. Comprueba el funcionario, período, ítem medible y ponderación. La suma de ponderaciones por funcionario dentro de un período no debe superar el 100 %."
                },
                {
                    title: "Paso 4. Revisar períodos",
                    text: "En Períodos puedes consultar los períodos de medición, sus fechas, estado y versión. Las acciones de edición dependen de que el período y tus permisos lo permitan.",
                    action: "chatPeriodos",
                    actionLabel: "Abrir períodos"
                },
                {
                    title: "Paso 5. Configurar reglas",
                    text: "Desde el detalle de un período, los perfiles autorizados pueden acceder a la configuración de reglas y a su historial. Verifica el período antes de modificar una regla."
                },
                {
                    title: "Paso 6. Consultar el semáforo",
                    text: "El semáforo permite consultar el estado de avance de la medición según los datos disponibles. Interpreta sus resultados considerando el período seleccionado.",
                    action: "chatSemaforo",
                    actionLabel: "Abrir semáforo"
                },
                {
                    title: "Paso 7. Revisar antes de confirmar",
                    text: "Antes de guardar cambios de metas, períodos o reglas, verifica los datos y sus efectos. No modifiques registros si tu perfil no tiene autorización."
                }
            ]
        },

        organizacion: {
            title: "Administración de la organización",
            links: [
                "chatFuncionarios",
                "chatDelegaciones",
                "chatCargos",
                "chatRoles",
                "chatCatalogos"
            ],
            steps: [
                {
                    title: "Paso 1. Ingresar a Organización",
                    text: "El módulo Organización reúne las funciones para consultar y administrar funcionarios, delegaciones, cargos, ítems y roles. Los accesos dependen de los permisos de tu cuenta."
                },
                {
                    title: "Paso 2. Consultar funcionarios",
                    text: "En el listado de funcionarios puedes buscar registros y abrir su detalle. Según tus permisos, podrás crear, editar, cambiar el estado o gestionar el acceso de un funcionario.",
                    action: "chatFuncionarios",
                    actionLabel: "Abrir funcionarios"
                },
                {
                    title: "Paso 3. Administrar delegaciones",
                    text: "La sección de delegaciones permite consultar los registros territoriales. Si tienes autorización, puedes crear, editar o cambiar el estado de una delegación.",
                    action: "chatDelegaciones",
                    actionLabel: "Abrir delegaciones"
                },
                {
                    title: "Paso 4. Revisar cargos e ítems",
                    text: "En Cargos puedes consultar los cargos y sus ítems medibles asociados. Las opciones disponibles pueden incluir creación, edición, eliminación y revisión del historial de ítems.",
                    action: "chatCargos",
                    actionLabel: "Abrir cargos"
                },
                {
                    title: "Paso 5. Administrar roles",
                    text: "La sección de roles permite revisar los perfiles y las opciones de administración habilitadas para tu cuenta. Verifica los permisos y el alcance autorizado antes de guardar modificaciones.",
                    action: "chatRoles",
                    actionLabel: "Abrir roles"
                },
                {
                    title: "Paso 6. Consultar catálogos",
                    text: "Los catálogos contienen opciones de clasificación utilizadas por los módulos del sistema. Modifica sus registros únicamente si tu perfil tiene autorización y conoces el efecto que tendrán en los formularios.",
                    action: "chatCatalogos",
                    actionLabel: "Abrir catálogos"
                },
                {
                    title: "Paso 7. Verificar los cambios",
                    text: "Después de crear o modificar un registro, vuelve al listado y comprueba que la información se haya guardado correctamente."
                }
            ]
        }
    };

    function tutorialAvailable(item) {
        return !!firstAvailableLink(item.links);
    }

    function startTutorial(name) {
        const selected = tutorials[name];

        if (!selected) {
            addMessage("No encontré ese tutorial. Puedes seleccionar otro tema disponible.");
            return;
        }

        if (!tutorialAvailable(selected)) {
            addMessage("Este módulo no está habilitado para tu perfil. Puedes consultar otro tutorial disponible.");
            return;
        }

        currentTutorial = selected;
        currentStep = 0;

        options.hidden = true;
        tutorialPanel.hidden = false;
        questionArea.hidden = true;

        renderTutorialStep();
        addMessage("Comenzaremos el tutorial: " + selected.title + ".");
    }

    function renderTutorialStep() {
        if (!currentTutorial) return;

        const step = currentTutorial.steps[currentStep];

        $("sgrTutorialTitle").textContent = currentTutorial.title;
        $("sgrTutorialProgress").textContent =
            "Paso " + (currentStep + 1) + " de " + currentTutorial.steps.length;

        $("sgrTutorialProgressBar").style.width =
            ((currentStep + 1) / currentTutorial.steps.length * 100) + "%";

        const stepContainer = $("sgrTutorialStep");
        stepContainer.replaceChildren();

        const heading = document.createElement("strong");
        heading.textContent = step.title;

        const description = document.createElement("p");
        description.textContent = step.text;

        stepContainer.append(heading, description);

        const actionUrl = step.action ? getLink(step.action) : null;

        if (actionUrl) {
            const action = document.createElement("a");
            action.href = actionUrl;
            action.className = "btn btn-sm btn-outline-danger mt-2";
            action.textContent = step.actionLabel || "Abrir sección";
            stepContainer.appendChild(action);
        }

        $("sgrTutorialPrevious").disabled = currentStep === 0;
        $("sgrTutorialNext").textContent =
            currentStep === currentTutorial.steps.length - 1
                ? "Finalizar"
                : "Siguiente";
    }

    function finishTutorial() {
        if (currentTutorial) {
            const destination = firstAvailableLink(currentTutorial.links);
            addMessage(
                "¡Has terminado el tutorial! Puedes volver a realizarlo cuando necesites orientación.",
                "bot",
                destination,
                "Abrir módulo relacionado"
            );
        }

        currentTutorial = null;
        currentStep = 0;
        showOptions();
    }

    function getContextTutorial() {
        if (moduleName === "activities") {
            if (urlName.includes("validacion")) return "validaciones";
            return "actividades";
        }

        if (moduleName === "agenda") return "agenda";
        if (moduleName === "social") return "social";

        if (moduleName === "measurement") {
            if (urlName.includes("mi_desempeno") ||
                urlName.includes("desempeno_funcionario")) {
                return "desempeno";
            }
            return "supervision";
        }

        if (moduleName === "organizations") return "organizacion";

        return "dashboard";
    }

    function showTutorialMenu() {
        addMessage("Selecciona el tutorial que quieres realizar:");

        const available = [
            ["dashboard", "Panel principal"],
            ["actividades", "Actividades"],
            ["validaciones", "Validación de evidencias"],
            ["agenda", "Agenda colectiva"],
            ["social", "Atención social"],
            ["desempeno", "Mi desempeño"],
            ["supervision", "Metas y medición"],
            ["organizacion", "Organización"]
        ];

        const wrapper = document.createElement("div");
        wrapper.className = "sgr-chat-message sgr-chat-bot";

        const bubble = document.createElement("div");
        bubble.className = "sgr-chat-bubble";

        available.forEach(([key, label]) => {
            const item = tutorials[key];
            if (!tutorialAvailable(item)) return;

            const button = document.createElement("button");
            button.type = "button";
            button.className =
                "btn btn-sm btn-outline-danger d-block w-100 text-start mb-2";
            button.textContent = label;

            button.addEventListener("click", function () {
                wrapper.remove();
                addMessage(label, "user");
                startTutorial(key);
            });

            bubble.appendChild(button);
        });

        if (!bubble.children.length) {
            addMessage("No hay tutoriales de módulos habilitados para tu perfil.");
            return;
        }

        wrapper.appendChild(bubble);
        messages.appendChild(wrapper);
        messages.scrollTop = messages.scrollHeight;
    }

    function normalize(value) {
        return value
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[¿?¡!.,;:]/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    const answers = [
        {
            keywords: ["mi desempeno", "mi rendimiento", "mis resultados", "desempeno personal"],
            response: "Mi desempeño permite consultar tus metas y resultados personales para el período disponible. Es una vista de consulta; no es la sección para administrar metas.",
            tutorial: "desempeno"
        },
        {
            keywords: ["administrar metas", "crear meta", "nueva meta", "editar meta", "metas", "ponderacion", "ponderaciones"],
            response: "La administración de metas corresponde al área de medición y requiere permisos de supervisión. Desde allí puedes consultar metas, aplicar filtros y, si está habilitado, crear o editar registros. Recuerda revisar que las ponderaciones no superen el 100 % por funcionario y período.",
            tutorial: "supervision"
        },
        {
            keywords: ["periodo", "periodos", "medicion", "reglas de periodo", "cerrar periodo", "reabrir periodo"],
            response: "Los períodos de medición se consultan en la sección Períodos. Sus opciones de edición, cierre, reapertura y configuración de reglas dependen del estado del período y de tus permisos.",
            tutorial: "supervision"
        },
        {
            keywords: ["semaforo", "avance", "estado de avance"],
            response: "El semáforo presenta el estado de avance de la medición según los datos disponibles. Debes revisar el período al que corresponden los resultados.",
            tutorial: "supervision"
        },
        {
            keywords: ["actividad", "actividades", "registrar actividad", "crear actividad"],
            response: "El módulo Actividades permite registrar y consultar acciones ejecutadas. Desde el detalle también puedes revisar los antecedentes y adjuntar evidencias cuando tu perfil lo permita.",
            tutorial: "actividades"
        },
        {
            keywords: ["evidencia", "evidencias", "archivo adjunto", "adjuntar archivo"],
            response: "Las evidencias se adjuntan desde el detalle de una actividad. El sistema admite archivos JPG, JPEG, PNG y PDF, sujetos a los límites configurados. Su validación corresponde a los perfiles autorizados.",
            tutorial: "actividades"
        },
        {
            keywords: ["validar", "validacion", "rechazar evidencia", "aprobar evidencia", "bandeja de validacion"],
            response: "La bandeja de validación permite revisar evidencias pendientes. Debes comprobar el archivo y los antecedentes. Si rechazas o solicitas corrección, registra una observación. No puedes validar evidencias de actividades propias.",
            tutorial: "validaciones"
        },
        {
            keywords: ["agenda", "compromiso", "compromisos", "nuevo compromiso"],
            response: "La Agenda colectiva permite consultar compromisos, revisar su detalle, plazo, estado e historial. Si tienes permiso, también puedes registrar compromisos y utilizar las acciones habilitadas.",
            tutorial: "agenda"
        },
        {
            keywords: ["caso social", "casos sociales", "atencion social", "persona atendida", "subatencion", "subatenciones"],
            response: "Atención social permite consultar y gestionar casos dentro de tu ámbito de acceso. La clasificación debe corresponder al tipo de atención y subatención seleccionados. En las gestiones, la delegación, el responsable y la fecha se asignan automáticamente.",
            tutorial: "social"
        },
        {
            keywords: ["funcionario", "funcionarios", "delegacion", "delegaciones", "rol", "roles", "cargo", "cargos", "usuario", "usuarios", "catalogo", "catalogos"],
            response: "Organización reúne la administración de funcionarios, delegaciones, cargos, ítems y roles. Las opciones para crear, editar o cambiar estados dependen de los permisos de tu cuenta.",
            tutorial: "organizacion"
        },
        {
            keywords: ["notificacion", "notificaciones", "campana", "avisos"],
            response: "Las notificaciones se consultan desde el ícono de campana ubicado en la barra superior. Abre el aviso para revisar su contenido y el registro relacionado, si corresponde.",
            tutorial: "dashboard"
        },
        {
            keywords: ["perfil", "contrasena", "cambiar clave", "cerrar sesion", "salir"],
            response: "Las opciones de perfil y cierre de sesión se encuentran en el menú de usuario de la barra superior. Cierra la sesión al terminar, especialmente si utilizas un equipo compartido."
        },
        {
            keywords: ["panel", "inicio", "dashboard", "pagina principal"],
            response: "El panel principal reúne accesos e información general del SGR. Utiliza el menú lateral para entrar a los módulos habilitados para tu cuenta.",
            tutorial: "dashboard"
        },
        {
            keywords: ["ayuda", "tutorial", "como funciona", "como usar", "orientacion"],
            response: "Puedo orientarte sobre el uso de los módulos del SGR y guiarte paso a paso. Selecciona «Tutorial paso a paso» para elegir un módulo o «Ayuda de esta pantalla» para recibir orientación contextual."
        }
    ];

    function answerQuestion(question) {
        const normalized = normalize(question);
        if (!normalized) return;

        addMessage(question, "user");

        const answer = answers.find((item) =>
            item.keywords.some((keyword) =>
                normalized.includes(normalize(keyword))
            )
        );

        if (!answer) {
            addMessage(
                "No encontré una respuesta específica para esa consulta. Puedes preguntar por actividades, evidencias, validaciones, agenda, compromisos, atención social, metas, períodos, desempeño, funcionarios, delegaciones, roles o notificaciones. También puedes iniciar un tutorial paso a paso."
            );
            return;
        }

        addMessage(answer.response);

        if (answer.tutorial) {
            const selected = tutorials[answer.tutorial];

            if (selected && tutorialAvailable(selected)) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn btn-sm btn-outline-danger ms-5 mb-3";
                button.textContent = "Ver tutorial paso a paso";

                button.addEventListener("click", function () {
                    button.remove();
                    startTutorial(answer.tutorial);
                });

                messages.appendChild(button);
            } else if (selected) {
                addMessage("El tutorial de esa sección no está habilitado para tu perfil. Puedes consultar otra orientación desde el menú de tutoriales.");
            }
        }

        messages.scrollTop = messages.scrollHeight;
    }

    toggle.addEventListener("click", function () {
        if (windowChat.hidden) openChat();
        else closeChat();
    });

    close.addEventListener("click", closeChat);

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !windowChat.hidden) {
            closeChat();
        }
    });

    options.addEventListener("click", function (event) {
        const button = event.target.closest("[data-chat-action]");
        if (!button) return;

        const action = button.dataset.chatAction;

        if (action === "tutorial") {
            showTutorialMenu();
        } else if (action === "question") {
            input.focus();
            addMessage("Escribe tu pregunta sobre el funcionamiento del SGR.");
        } else if (action === "context") {
            const key = getContextTutorial();
            addMessage("Esta es la orientación relacionada con la sección en la que te encuentras.");
            startTutorial(key);
        }
    });

    $("sgrTutorialPrevious").addEventListener("click", function () {
        if (currentStep > 0) {
            currentStep--;
            renderTutorialStep();
        }
    });

    $("sgrTutorialNext").addEventListener("click", function () {
        if (!currentTutorial) return;

        if (currentStep < currentTutorial.steps.length - 1) {
            currentStep++;
            renderTutorialStep();
        } else {
            finishTutorial();
        }
    });

    $("sgrTutorialExit").addEventListener("click", function () {
        currentTutorial = null;
        currentStep = 0;
        showOptions();
        addMessage("Has salido del tutorial. Puedes iniciar otro cuando quieras.");
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();

        const question = input.value.trim();
        if (!question) return;

        input.value = "";
        answerQuestion(question);
    });
});
