/**
 * Earth2Worlds - Utilidades globales de sesión JWT, peticiones autenticadas y sanitización XSS.
 */

const E2W_TOKEN_KEY = "earth2worlds_token";
const E2W_USER_KEY = "earth2worlds_user";

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
 * Wrapper de fetch con cabeceras Bearer y redirección automática en 401.
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
    if (response.status === 401 && !window.location.pathname.startsWith("/login")) {
        clearSession();
        window.location.href = "/login";
    }
    return response;
}

/**
 * Cierra la sesión actual de forma asíncrona contra /api/auth/logout y redirige a /login.
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
    window.location.href = "/login";
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
window.getCachedUser = getCachedUser;
window.clearSession = clearSession;
window.getAuthHeaders = getAuthHeaders;
window.authFetch = authFetch;
window.logout = logout;
window.togglePasswordVisibility = togglePasswordVisibility;
