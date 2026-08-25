export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const TOKEN_KEY = "compoint_auth_token";
const USERNAME_KEY = "compoint_auth_username";

/**
 * Sesión del equipo interno de la banquetera (Módulo A: autenticación y
 * roles). El token se guarda en localStorage del navegador de quien inició
 * sesión — es normal que no se comparta entre dispositivos ni navegadores,
 * y que se pierda si borran los datos del sitio.
 */
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getUsername() {
  try {
    return localStorage.getItem(USERNAME_KEY);
  } catch {
    return null;
  }
}

export function guardarSesion(token, username) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USERNAME_KEY, username);
  } catch {
    // Si el navegador bloquea localStorage (modo privado, etc.) la sesión
    // simplemente no persiste entre recargas; no rompe el resto de la app.
  }
}

export function cerrarSesion() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
  } catch {
    // no-op
  }
}

/**
 * fetch con el header de autenticación agregado automáticamente. Se usa en
 * vez de `fetch` normal en todas las pantallas internas (Dashboard,
 * Recetario, Bodega, Personal, Finanzas). Si el backend responde 401
 * (sesión vencida o token inválido), limpia la sesión guardada y recarga la
 * página para mostrar el login de nuevo — así nunca se queda "colgada" una
 * pantalla con una sesión muerta.
 */
export function authFetch(url, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Token ${token}`;
  return fetch(url, { ...options, headers }).then((res) => {
    if (res.status === 401) {
      cerrarSesion();
      window.location.reload();
    }
    return res;
  });
}
