import { useState } from "react";
import { API_BASE, guardarSesion } from "./api.js";
import logoIcono from "./assets/logo-icono.png";

/**
 * Login del equipo interno de la banquetera (Módulo A: autenticación y
 * roles). No hay registro público: las cuentas se crean desde /admin/
 * (sección Usuarios) o al correr `manage.py createsuperuser`.
 *
 * El Event Planner NO usa esta pantalla — entra por su link único de
 * `/planner/<token>/`, sin cuenta ni contraseña (ver PlannerView.jsx).
 */
function IconOjo(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconOjoTachado(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <path d="M3 3l18 18" strokeLinecap="round" />
      <path d="M10.6 5.2A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a15.6 15.6 0 0 1-4.2 4.9M6.6 6.6C3.9 8.3 2 12 2 12s3.6 7 10 7a9.8 9.8 0 0 0 3.4-.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.9 10a3 3 0 0 0 4.1 4.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Login({ onIngreso }) {
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [mostrarContrasena, setMostrarContrasena] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setEnviando(true);
    fetch(`${API_BASE}/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: usuario, password: contrasena }),
    })
      .then(async (res) => {
        if (!res.ok) {
          const datos = await res.json().catch(() => ({}));
          throw new Error(datos.detail || "No se pudo iniciar sesión.");
        }
        return res.json();
      })
      .then((datos) => {
        guardarSesion(datos.token, datos.username);
        onIngreso(datos.username);
      })
      .catch((err) => setError(err.message || "No se pudo iniciar sesión."))
      .finally(() => setEnviando(false));
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <img src={logoIcono} alt="COMPOINT EventFlow" className="h-20 w-20 shrink-0 object-contain" />
          <div>
            <p className="text-lg font-semibold leading-tight text-navy-900">COMPOINT</p>
            <p className="-mt-1 text-lg font-semibold leading-tight text-teal-600">
              EventFlow
            </p>
          </div>
        </div>

        <h1 className="mb-1 text-lg font-semibold text-navy-900">Iniciar sesión</h1>
        <p className="mb-5 text-sm text-slate-500">
          Acceso del equipo interno de la banquetera.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-600">Usuario</label>
            <input
              type="text"
              autoFocus
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              required
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-600">Contraseña</label>
            <div className="relative">
              <input
                type={mostrarContrasena ? "text" : "password"}
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 pr-10 text-sm"
                required
              />
              <button
                type="button"
                onClick={() => setMostrarContrasena((v) => !v)}
                aria-label={mostrarContrasena ? "Ocultar contraseña" : "Mostrar contraseña"}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 hover:text-slate-600"
              >
                {mostrarContrasena ? (
                  <IconOjoTachado className="h-4.5 w-4.5" />
                ) : (
                  <IconOjo className="h-4.5 w-4.5" />
                )}
              </button>
            </div>
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
          )}

          <button
            type="submit"
            disabled={enviando}
            className="mt-2 rounded-lg bg-navy-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-400">
          ¿Eres Event Planner? Pídele a la banquetera el link de tu evento — no necesitas
          entrar por aquí.
        </p>
      </div>
    </div>
  );
}
