
document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    const root = document.getElementById("sgrTutorialChat");
    if (!root) return;

    const toggle = document.getElementById("sgrChatToggle");
    const close = document.getElementById("sgrChatClose");
    const windowChat = document.getElementById("sgrChatWindow");
    const messages = document.getElementById("sgrChatMessages");
    const options = document.getElementById("sgrChatOptions");
    const tutorial = document.getElementById("sgrChatTutorial");
    const questionArea = document.getElementById("sgrChatQuestionArea");
    const form = document.getElementById("sgrChatForm");
    const input = document.getElementById("sgrChatInput");

    const moduleName = root.dataset.module || "";
    const urlName = root.dataset.urlName || "";

    const link = (id) => {
        const element = document.getElementById(id);
        return element ? element.getAttribute("href") : null;
    };

    let currentTutorial = null;
    let currentStep = 0;

    const tutorials = {
        dashboard: {
            title: "Conocer el panel principal",
            keywords: ["panel", "inicio", "dashboard", "principal"],
            steps: [
                {
                    title: "Paso 1. Panel principal",
                    text: "El panel principal es la pantalla de inicio del SGR. Desde aquí puedes consultar información general y acceder a las funciones disponibles para tu cuenta."
                },
                {
                    title: "Paso 2. Menú lateral",
                    text: "Utiliza el menú lateral para acceder a los módulos habilitados. Las opciones visibles dependen de tus permisos y del rol asignado."
                },
                {
                    title: "Paso 3. Indicadores y alertas",
                    text: "Revisa los indicadores y alertas disponibles. Estos elementos ayudan a identificar actividades, compromisos y situaciones que requieren atención."
                },
                {
                    title: "Paso 4. Notificaciones",
                    text: "En la parte superior puedes consultar las notificaciones del sistema y revisar la actividad reciente."
                },
                {
                    title: "Paso 5. Perfil y sesión",
                    text: "Desde el menú de usuario puedes consultar o editar tu perfil y cerrar la sesión de forma segura."
                }
            ],
            link: "chatDashboard"
        },

        actividades: {
            title: "Registrar y consultar actividades",
            keywords: ["actividad", "actividades", "registro", "evidencia"],
            steps: [
                {
                    title: "Paso 1. Ingresar a actividades",
                    text: "Accede al módulo Actividades desde el menú lateral para consultar los registros que están disponibles para tu usuario."
                },
                {
                    title: "Paso 2. Crear una actividad",
                    text: "Si tienes permiso para registrar, utiliza la opción Registrar actividad. El sistema abrirá el formulario correspondiente."
                },
                {
                    title: "Paso 3. Completar el formulario",
                    text: "Completa los campos obligatorios de acuerdo con la información real de la actividad. Revisa especialmente fechas, descripción, responsable y los datos de clasificación que solicite el formulario."
                },
                {
                    title: "Paso 4. Guardar",
                    text: "Antes de guardar, revisa que la información sea correcta. Si el formulario presenta errores, corrige los campos indicados por el sistema."
                },
                {
                    title: "Paso 5. Consultar y respaldar",
                    text: "Desde el listado puedes consultar los registros y acceder a sus detalles. Cuando corresponda, utiliza las opciones de evidencias para adjuntar respaldos."
                }
            ],
            link: "chatActividades",
            createLink: "chatNuevaActividad"
        },

        validaciones: {
            title: "Validar evidencias",
            keywords: ["validar", "validacion", "validación", "evidencia", "revisar"],
            steps: [
                {
                    title: "Paso 1. Abrir validaciones",
                    text: "Ingresa a Validación de evidencias desde el menú lateral. Esta opción está disponible para los perfiles autorizados."
                },
                {
                    title: "Paso 2. Revisar los antecedentes",
                    text: "Selecciona un registro pendiente y revisa la información de la actividad y los archivos de respaldo disponibles."
                },
                {
                    title: "Paso 3. Evaluar la evidencia",
                    text: "Comprueba que el archivo y la información presentada correspondan a la actividad registrada y permitan respaldar lo informado."
                },
                {
                    title: "Paso 4. Registrar la decisión",
                    text: "Utiliza las opciones de validación que presenta el sistema y completa las observaciones que correspondan."
                },
                {
                    title: "Paso 5. Confirmar",
                    text: "Revisa la decisión antes de confirmar. La operación quedará registrada en el sistema."
                }
            ],
            link: "chatValidaciones"
        },

        agenda: {
            title: "Utilizar la agenda colectiva",
            keywords: ["agenda", "compromiso", "compromisos", "calendario"],
            steps: [
                {
                    title: "Paso 1. Abrir la agenda",
                    text: "Ingresa a Agenda colectiva para consultar los compromisos que puedes visualizar según tu ámbito de acceso."
                },
                {
                    title: "Paso 2. Crear un compromiso",
                    text: "Si tienes permiso de registro, utiliza Nuevo compromiso desde el menú lateral."
                },
                {
                    title: "Paso 3. Completar los datos",
                    text: "Registra la información solicitada en el formulario. Comprueba responsables, fechas y descripción antes de guardar."
                },
                {
                    title: "Paso 4. Consultar compromisos",
                    text: "Desde el listado puedes revisar los compromisos y acceder al detalle de cada uno."
                },
                {
                    title: "Paso 5. Revisar el resumen",
                    text: "El resumen de agenda permite consultar información consolidada de los compromisos disponibles para tu usuario."
                }
            ],
            link: "chatAgenda",
            createLink: "chatNuevoCompromiso"
        },

        social: {
            title: "Gestionar atención social",
            keywords: ["social", "atencion", "atención", "caso", "casos", "subatencion"],
            steps: [
                {
                    title: "Paso 1. Abrir atención social",
                    text: "Ingresa al módulo Atención social si está habilitado para tu perfil."
                },
                {
                    title: "Paso 2. Consultar casos",
                    text: "El listado permite consultar los casos visibles según los permisos y el ámbito de acceso de tu cuenta."
                },
                {
                    title: "Paso 3. Registrar un caso",
                    text: "Si tienes autorización, utiliza la opción de nuevo caso y completa los antecedentes solicitados."
                },
                {
                    title: "Paso 4. Revisar clasificación",
                    text: "Comprueba que la atención y subatención seleccionadas correspondan a la situación registrada."
                },
                {
                    title: "Paso 5. Consultar gestiones",
                    text: "Accede al detalle del caso para revisar su información y las gestiones disponibles."
                }
            ],
            link: "chatAtencionSocial"
        },

        desempeno: {
            title: "Consultar mi desempeño",
            keywords: ["desempeno", "desempeño", "mis metas", "mi desempeño"],
            steps: [
                {
                    title: "Paso 1. Abrir mi desempeño",
                    text: "Ingresa a Mi desempeño desde el menú lateral, si esta opción está habilitada para tu cuenta."
                },
                {
                    title: "Paso 2. Revisar el período",
                    text: "Identifica el período de medición al que corresponde la información que estás consultando."
                },
                {
                    title: "Paso 3. Consultar metas",
                    text: "Revisa las metas e indicadores que aparecen asociados a tu desempeño."
                },
                {
                    title: "Paso 4. Revisar resultados",
                    text: "Consulta los avances y resultados que presenta el sistema. Si tienes dudas sobre un dato, contacta a la unidad responsable de su gestión."
                }
            ],
            link: "chatDesempeno"
        },

        supervision: {
            title: "Supervisión y medición",
            keywords: ["metas", "periodos", "períodos", "semaforo", "semáforo", "supervision", "supervisión"],
            steps: [
                {
                    title: "Paso 1. Acceder a medición",
                    text: "El área de medición y supervisión agrupa las funciones habilitadas para los perfiles autorizados."
                },
                {
                    title: "Paso 2. Consultar períodos",
                    text: "Desde Períodos puedes revisar los períodos de medición y las opciones que correspondan a tu rol."
                },
                {
                    title: "Paso 3. Consultar metas",
                    text: "Desde Metas puedes revisar los registros y acceder a las acciones disponibles según tus permisos."
                },
                {
                    title: "Paso 4. Revisar el semáforo",
                    text: "El semáforo de delegación permite consultar el estado de avance que presenta el sistema."
                },
                {
                    title: "Paso 5. Verificar antes de modificar",
                    text: "Si tu perfil permite administrar información, revisa cuidadosamente el período y los antecedentes antes de guardar cualquier cambio."
                }
            ],
            link: "chatMetas"
        },

        organizacion: {
            title: "Administrar la organización",
            keywords: ["funcionario", "funcionarios", "delegacion", "delegación", "roles", "cargo", "cargos", "usuarios"],
            steps: [
                {
                    title: "Paso 1. Abrir organización",
                    text: "El módulo Organización contiene funciones de administración de funcionarios, delegaciones, cargos y roles para los perfiles autorizados."
                },
                {
                    title: "Paso 2. Seleccionar el registro",
                    text: "Ingresa a la sección correspondiente y consulta los registros disponibles."
                },
                {
                    title: "Paso 3. Crear o editar",
                    text: "Utiliza las opciones disponibles para crear o modificar información. Solo realiza cambios para los que tengas autorización."
                },
                {
                    title: "Paso 4. Revisar los datos",
                    text: "Comprueba que los datos ingresados sean correctos antes de guardar."
                },
                {
                    title: "Paso 5. Comprobar los permisos",
                    text: "Recuerda que las acciones visibles dependen de los permisos asignados a tu cuenta."
                }
            ],
            link: "chatFuncionarios"
        }
    };

    function addMessage(text, type = "bot", linkUrl = null, linkLabel = null) {
        const message = document.createElement("div");
        message.className = "sgr-chat-message sgr-chat-" + type;

        if (type === "bot") {
            const avatar = document.createElement("div");
            avatar.className = "sgr-chat-message-avatar";
            avatar.innerHTML = '<i class="bi bi-mortarboard-fill"></i>';
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
            anchor.textContent = linkLabel || "Abrir módulo";
            anchor.className = "d-inline-block mt-2";
            bubble.appendChild(anchor);
        }

        message.appendChild(bubble);
        messages.appendChild(message);
        messages.scrollTop = messages.scrollHeight;
    }

    function openChat() {
        windowChat.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        toggle.innerHTML = '<i class="bi bi-chat-dots-fill"></i>';
        input.focus();
    }

    function closeChat() {
        windowChat.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        toggle.innerHTML = '<i class="bi bi-chat-dots-fill"></i>';
    }

    function getLink(id) {
        return link(id);
    }

    function showOptions() {
        options.hidden = false;
        tutorial.hidden = true;
        questionArea.hidden = false;
    }

    function findTutorialByName(name) {
        return tutorials[name] || null;
    }

    function startTutorial(name) {
        const selected = findTutorialByName(name);

        if (!selected) {
            addMessage("No encontré ese tutorial. Puedes elegir otro tema o escribir tu pregunta.");
            return;
        }

        if (selected.link && !getLink(selected.link)) {
            addMessage("Esta función no está habilitada para tu perfil. Puedes consultar otro tutorial disponible.");
            return;
        }

        currentTutorial = selected;
        currentStep = 0;

        options.hidden = true;
        tutorial.hidden = false;
        questionArea.hidden = true;

        renderTutorialStep();

        addMessage("Comenzaremos el tutorial: " + selected.title + ".");
    }

    function renderTutorialStep() {
        if (!currentTutorial) return;

        const step = currentTutorial.steps[currentStep];

        document.getElementById("sgrTutorialTitle").textContent =
            currentTutorial.title;

        document.getElementById("sgrTutorialProgress").textContent =
            "Paso " + (currentStep + 1) + " de " + currentTutorial.steps.length;

        document.getElementById("sgrTutorialProgressBar").style.width =
            ((currentStep + 1) / currentTutorial.steps.length * 100) + "%";

        const stepContainer = document.getElementById("sgrTutorialStep");
        stepContainer.replaceChildren();

        const title = document.createElement("strong");
        title.textContent = step.title;

        const description = document.createElement("p");
        description.textContent = step.text;

        stepContainer.append(title, description);

        const previous = document.getElementById("sgrTutorialPrevious");
        const next = document.getElementById("sgrTutorialNext");

        previous.disabled = currentStep === 0;

        next.innerHTML = currentStep === currentTutorial.steps.length - 1
            ? 'Finalizar <i class="bi bi-check-lg"></i>'
            : 'Siguiente <i class="bi bi-arrow-right"></i>';
    }

    function finishTutorial() {
        if (currentTutorial) {
            const destination = getLink(currentTutorial.link);
            addMessage("¡Has terminado el tutorial! Puedes consultar otro tema cuando lo necesites.",
                "bot",
                destination,
                "Abrir módulo relacionado");
        }

        currentTutorial = null;
        currentStep = 0;
        showOptions();
    }

    function getContextTutorial() {
        if (moduleName === "activities") {
            if (urlName.includes("validacion")) {
                return "validaciones";
            }
            return "actividades";
        }

        if (moduleName === "agenda") return "agenda";
        if (moduleName === "social") return "social";
        if (moduleName === "measurement") {
            if (urlName.includes("mi_desempeno")) return "desempeno";
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
            ["agenda", "Agenda colectiva"],
            ["desempeno", "Mi desempeño"],
            ["social", "Atención social"],
            ["validaciones", "Validación de evidencias"],
            ["supervision", "Medición y supervisión"],
            ["organizacion", "Organización"]
        ];

        const wrapper = document.createElement("div");
        wrapper.className = "sgr-chat-message sgr-chat-bot";

        const bubble = document.createElement("div");
        bubble.className = "sgr-chat-bubble";

        available.forEach(([key, label]) => {
            const item = tutorials[key];

            if (item.link && !getLink(item.link)) return;

            const button = document.createElement("button");
            button.type = "button";
            button.className = "btn btn-sm btn-outline-danger d-block w-100 text-start mb-2";
            button.textContent = label;
            button.addEventListener("click", () => {
                wrapper.remove();
                addMessage(label, "user");
                startTutorial(key);
            });

            bubble.appendChild(button);
        });

        wrapper.appendChild(bubble);
        messages.appendChild(wrapper);
        messages.scrollTop = messages.scrollHeight;
    }

    function normalize(text) {
        return text
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[¿?¡!.,]/g, "")
            .trim();
    }

    const answers = [
        {
            keywords: ["actividad", "registrar actividad", "crear actividad"],
            response: "Para registrar una actividad, utiliza la opción Registrar actividad si está habilitada para tu cuenta. Puedo acompañarte con un tutorial paso a paso.",
            tutorial: "actividades"
        },
        {
            keywords: ["evidencia", "validar", "validacion"],
            response: "Las evidencias se consultan desde el módulo de Actividades. La validación está disponible para los perfiles autorizados.",
            tutorial: "validaciones"
        },
        {
            keywords: ["agenda", "compromiso", "compromisos"],
            response: "La Agenda colectiva permite consultar los compromisos disponibles para tu usuario. También puedes revisar su resumen.",
            tutorial: "agenda"
        },
        {
            keywords: ["meta", "metas", "desempeno"],
            response: "Puedes consultar tu desempeño desde Mi desempeño. Las funciones de administración de metas dependen de tus permisos.",
            tutorial: "desempeno"
        },
        {
            keywords: ["social", "caso", "atencion social"],
            response: "El módulo de Atención social permite consultar y gestionar los casos disponibles para tu ámbito de acceso.",
            tutorial: "social"
        },
        {
            keywords: ["funcionario", "delegacion", "rol", "cargo", "usuario"],
            response: "Las funciones de organización permiten administrar funcionarios, delegaciones, cargos y roles cuando tu perfil tiene autorización.",
            tutorial: "organizacion"
        },
        {
            keywords: ["panel", "inicio", "dashboard"],
            response: "El panel principal presenta información general y accesos a los módulos habilitados para tu cuenta.",
            tutorial: "dashboard"
        },
        {
            keywords: ["notificacion", "notificaciones"],
            response: "Puedes revisar las notificaciones desde el ícono de campana de la barra superior.",
            tutorial: "dashboard"
        },
        {
            keywords: ["perfil", "contrasena", "contrasena", "sesion"],
            response: "Puedes consultar tu perfil desde el menú de usuario ubicado en la parte superior derecha. Allí también encontrarás la opción para cerrar sesión."
        },
        {
            keywords: ["ayuda", "tutorial", "como funciona", "como usar"],
            response: "Puedo guiarte paso a paso por los módulos del SGR. Selecciona Tutorial paso a paso para comenzar."
        }
    ];

    function answerQuestion(question) {
        const normalized = normalize(question);

        if (!normalized) return;

        addMessage(question, "user");

        const answer = answers.find(item =>
            item.keywords.some(keyword =>
                normalized.includes(normalize(keyword))
            )
        );

        if (answer) {
            const selected = answer.tutorial;
            const selectedTutorial = selected ? tutorials[selected] : null;
            const destination = selectedTutorial
                ? getLink(selectedTutorial.link)
                : null;

            addMessage(
                answer.response,
                "bot",
                destination,
                destination ? "Abrir módulo" : null
            );

            if (selected) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn btn-sm btn-outline-danger ms-5 mb-3";
                button.textContent = "Ver tutorial paso a paso";

                button.addEventListener("click", () => {
                    button.remove();
                    startTutorial(selected);
                });

                messages.appendChild(button);
                messages.scrollTop = messages.scrollHeight;
            }

            return;
        }

        addMessage(
            "No encontré una respuesta específica para esa pregunta. Prueba con palabras como actividades, agenda, metas, evidencias, atención social o funcionarios. También puedes elegir un tutorial paso a paso."
        );
    }

    toggle.addEventListener("click", () => {
        if (windowChat.hidden) openChat();
        else closeChat();
    });

    close.addEventListener("click", closeChat);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !windowChat.hidden) {
            closeChat();
        }
    });

    options.addEventListener("click", (event) => {
        const button = event.target.closest("[data-chat-action]");
        if (!button) return;

        const action = button.dataset.chatAction;

        if (action === "tutorial") {
            showTutorialMenu();
        }

        if (action === "question") {
            input.focus();
            addMessage("Escribe tu pregunta sobre el funcionamiento del SGR.");
        }

        if (action === "context") {
            const key = getContextTutorial();
            addMessage("Te mostraré la orientación relacionada con esta pantalla.");
            startTutorial(key);
        }
    });

    document.getElementById("sgrTutorialPrevious")
        .addEventListener("click", () => {
            if (currentStep > 0) {
                currentStep--;
                renderTutorialStep();
            }
        });

    document.getElementById("sgrTutorialNext")
        .addEventListener("click", () => {
            if (!currentTutorial) return;

            if (currentStep < currentTutorial.steps.length - 1) {
                currentStep++;
                renderTutorialStep();
            } else {
                finishTutorial();
            }
        });

    document.getElementById("sgrTutorialExit")
        .addEventListener("click", () => {
            currentTutorial = null;
            showOptions();
            addMessage("Has salido del tutorial. Puedes iniciar otro cuando quieras.");
        });

    form.addEventListener("submit", (event) => {
        event.preventDefault();

        const question = input.value.trim();
        if (!question) return;

        input.value = "";
        answerQuestion(question);
    });
});
