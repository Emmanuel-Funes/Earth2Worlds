/**
 * Earth2Worlds - Utilidades globales de sesión JWT, peticiones autenticadas y sanitización XSS.
 */

const E2W_TOKEN_KEY = "earth2worlds_token";
const E2W_USER_KEY = "earth2worlds_user";
const E2W_MODO_KEY = "earth2worlds_modo";

/**
 * Sanitiza texto dinámico para evitar inyecciones XSS al insertar en HTML.
 * @param {any} valor
 * @returns {string}
 */
function escapeHtml(valor) {
    if (valor === null || valor === undefined) return "";
    return String(valor)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Guarda el token JWT y el objeto de usuario en localStorage.
 * @param {string} token
 * @param {object} usuario
 */
function saveSession(token, usuario) {
    localStorage.setItem(E2W_TOKEN_KEY, token);
    localStorage.setItem(E2W_USER_KEY, JSON.stringify(usuario || {}));
}

/**
 * Obtiene el token JWT almacenado.
 * @returns {string|null}
 */
function getToken() {
    return localStorage.getItem(E2W_TOKEN_KEY);
}

/**
 * Obtiene el modo activo ('basico', 'avanzado', 'admin').
 * @returns {string|null}
 */
function getModo() {
    return localStorage.getItem(E2W_MODO_KEY);
}

/**
 * Establece el modo activo.
 * @param {string} modo
 */
function setModo(modo) {
    localStorage.setItem(E2W_MODO_KEY, modo);
}

/**
 * Inicia una sesión de prueba efímera (Básico o Avanzado).
 * @param {'basico'|'avanzado'} modo
 * @returns {Promise<object>}
 */
async function iniciarSesionInvitado(modo = "basico") {
    try {
        const res = await fetch("/api/auth/guest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ modo }),
        });
        if (res.ok) {
            const data = await res.json();
            saveSession(data.access_token, data.usuario);
            setModo(modo);
            return data;
        }
    } catch (err) {
        console.warn("[Auth] No se pudo conectar con /api/auth/guest, aplicando credencial efímera local:", err);
    }

    // Fallback resiliente si el backend no responde o estamos offline/file://
    const fallbackData = {
        access_token: "guest_token_offline",
        token_type: "bearer",
        usuario: {
            id: 0,
            nombre: "Invitado",
            apellido: modo === "basico" ? "Agricultor" : "Técnico",
            email: `guest_${modo}@earth2worlds.local`,
            rol: modo === "basico" ? "propietario" : "operador",
            pais: "Global",
            provincia: "San Luis",
            ciudad: "Villa Mercedes",
            codigo_postal: "5730",
            campos_asignados: []
        }
    };
    saveSession(fallbackData.access_token, fallbackData.usuario);
    setModo(modo);
    return fallbackData;
}

/**
 * Obtiene el usuario cacheado en localStorage.
 * @returns {object|null}
 */
function getCachedUser() {
    try {
        const raw = localStorage.getItem(E2W_USER_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (_e) {
        return null;
    }
}

/**
 * Limpia los datos de sesión en localStorage.
 */
function clearSession() {
    localStorage.removeItem(E2W_TOKEN_KEY);
    localStorage.removeItem(E2W_USER_KEY);
    localStorage.removeItem(E2W_MODO_KEY);
}

/**
 * Construye las cabeceras HTTP incluyendo Authorization Bearer.
 * @param {object} extraHeaders
 * @returns {object}
 */
function getAuthHeaders(extraHeaders = {}) {
    const token = getToken();
    const headers = {
        "Content-Type": "application/json",
        ...extraHeaders,
    };
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
}

/**
 * Wrapper de fetch con cabeceras Bearer.
 * @param {string} url
 * @param {object} options
 * @returns {Promise<Response>}
 */
async function authFetch(url, options = {}) {
    const headers = getAuthHeaders(options.headers || {});
    const response = await fetch(url, {
        ...options,
        headers,
    });
    if (response.status === 401) {
        clearSession();
        if (typeof mostrarSelectorModalidad === "function") {
            mostrarSelectorModalidad();
        } else {
            window.location.reload();
        }
    }
    return response;
}

/**
 * Cierra la sesión actual y vuelve a la pantalla de selección.
 */
async function logout() {
    const token = getToken();
    if (token) {
        try {
            await fetch("/api/auth/logout", {
                method: "POST",
                headers: getAuthHeaders(),
            });
        } catch (_err) {
            // Ignorar error de red al cerrar sesión
        }
    }
    clearSession();

    // Ocultar vistas activas para que el mapa o paneles no queden debajo ni superpuestos
    const vBasico = document.getElementById("vistaModoBasico");
    const vAvanzado = document.getElementById("vistaModoAvanzado");
    if (vBasico) {
        vBasico.classList.add("hidden");
        vBasico.style.display = "none";
    }
    if (vAvanzado) {
        vAvanzado.classList.add("hidden");
        vAvanzado.style.display = "none";
    }

    if (typeof mostrarSelectorModalidad === "function") {
        mostrarSelectorModalidad();
    } else {
        window.location.reload();
    }
}

/**
 * Alterna la visibilidad de un campo de contraseña.
 * @param {string} inputId
 * @param {HTMLElement} btnEl
 */
function togglePasswordVisibility(inputId, btnEl) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === "password") {
        input.type = "text";
        if (btnEl) btnEl.textContent = "Ocultar";
    } else {
        input.type = "password";
        if (btnEl) btnEl.textContent = "Ver";
    }
}

window.escapeHtml = escapeHtml;
window.saveSession = saveSession;
window.getToken = getToken;
window.getModo = getModo;
window.setModo = setModo;
window.iniciarSesionInvitado = iniciarSesionInvitado;
window.getCachedUser = getCachedUser;
window.clearSession = clearSession;
window.getAuthHeaders = getAuthHeaders;
window.authFetch = authFetch;
window.logout = logout;
window.togglePasswordVisibility = togglePasswordVisibility;
