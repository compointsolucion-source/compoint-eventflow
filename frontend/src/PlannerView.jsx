import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";
import logoIcono from "./assets/logo-icono.png";

/**
 * Portal del Event Planner (Módulo A): acceso de solo lectura a UN evento,
 * mediante el link único que le manda la banquetera (sin cuenta ni
 * contraseña). Nunca muestra costos, márgenes, cotización ni otros eventos
 * de la banquetera — solo el cronograma de este evento.
 */

const SEMAFORO_STYLES = {
  PROSPECTO: { emoji: "🟡", badge: "bg-amber-100 text-amber-800 border border-amber-300" },
  APARTADO: { emoji: "🟠", badge: "bg-orange-100 text-orange-800 border border-orange-300" },
  CONFIRMADO: { emoji: "🔴", badge: "bg-red-100 text-red-800 border border-red-300" },
};

const TIEMPO_LABELS = {
  ENTRADA: "Entrada",
  FUERTE: "Plato fuerte",
  POSTRE: "Postre",
  BEBIDA: "Bebida",
  BOTANA: "Botana / Coctel",
};

function formatoFecha(fecha) {
  if (!fecha) return "—";
  return new Date(fecha + "T00:00:00").toLocaleDateString("es-MX", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export default function PlannerView({ token }) {
  const [evento, setEvento] = useState(null);
  const [estado, setEstado] = useState("cargando"); // "cargando" | "ok" | "no-encontrado" | "error"

  useEffect(() => {
    let cancelado = false;
    fetch(`${API_BASE}/planner/${token}/`)
      .then((res) => {
        if (res.status === 404) throw new Error("no-encontrado");
        if (!res.ok) throw new Error("error");
        return res.json();
      })
      .then((datos) => {
        if (cancelado) return;
        setEvento(datos);
        setEstado("ok");
      })
      .catch((err) => {
        if (cancelado) return;
        setEstado(err.message === "no-encontrado" ? "no-encontrado" : "error");
      });
    return () => {
      cancelado = true;
    };
  }, [token]);

  if (estado === "cargando") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-500">Cargando…</p>
      </div>
    );
  }

  if (estado === "no-encontrado") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="max-w-sm rounded-2xl bg-white p-8 text-center shadow-sm">
          <h1 className="text-lg font-semibold text-navy-900">Link no válido</h1>
          <p className="mt-2 text-sm text-slate-500">
            Este link ya no corresponde a ningún evento. Pídele a la banquetera que te
            comparta el link actualizado.
          </p>
        </div>
      </div>
    );
  }

  if (estado === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="max-w-sm rounded-2xl bg-white p-8 text-center shadow-sm">
          <h1 className="text-lg font-semibold text-navy-900">No se pudo conectar</h1>
          <p className="mt-2 text-sm text-slate-500">
            Intenta recargar la página en unos momentos.
          </p>
        </div>
      </div>
    );
  }

  const estilo = SEMAFORO_STYLES[evento.estado_semaforo] ?? SEMAFORO_STYLES.PROSPECTO;

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <header className="flex items-center gap-3">
          <img src={logoIcono} alt="COMPOINT EventFlow" className="h-10 w-10 shrink-0 object-contain" />
          <div>
            <p className="text-sm font-semibold leading-tight text-navy-900">COMPOINT</p>
            <p className="-mt-1 text-sm font-semibold leading-tight text-teal-600">
              EventFlow · Portal de Event Planner
            </p>
          </div>
        </header>

        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-2xl font-semibold text-navy-900">{evento.nombre_evento}</h1>
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${estilo.badge}`}>
              {estilo.emoji} {evento.estado_semaforo_display}
            </span>
          </div>
          <p className="text-sm capitalize text-slate-600">{formatoFecha(evento.fecha)}</p>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Invitados</p>
              <p className="mt-0.5 font-semibold text-navy-900">{evento.numero_invitados}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Sede</p>
              <p className="mt-0.5 font-semibold text-navy-900">{evento.sede_nombre}</p>
              <p className="text-xs text-slate-500">{evento.sede_direccion}</p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold text-navy-900">Menú seleccionado</h2>
          <ul className="flex flex-col gap-2">
            {evento.detalle_menu?.map((detalle) => (
              <li
                key={detalle.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 p-3"
              >
                <div>
                  <p className="font-medium text-navy-900">{detalle.receta_detalle?.nombre}</p>
                  {detalle.notas_personalizacion && (
                    <p className="text-xs text-slate-500">{detalle.notas_personalizacion}</p>
                  )}
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                  {TIEMPO_LABELS[detalle.receta_detalle?.tiempo_menu] ??
                    detalle.receta_detalle?.tiempo_menu}
                </span>
              </li>
            ))}
            {!evento.detalle_menu?.length && (
              <p className="text-sm italic text-slate-400">Menú aún por definir.</p>
            )}
          </ul>
        </section>

        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="mb-3 text-lg font-semibold text-navy-900">Pruebas de menú</h2>
          <ul className="flex flex-col gap-2">
            {evento.pruebas_menu?.map((prueba) => (
              <li key={prueba.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-navy-900 capitalize">
                    {formatoFecha(prueba.fecha_prueba)}
                  </p>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      prueba.aprobado
                        ? "border border-teal-500/20 bg-teal-500/10 text-teal-700"
                        : "border border-amber-300 bg-amber-100 text-amber-800"
                    }`}
                  >
                    {prueba.aprobado ? "Aprobada" : "Pendiente de aprobar"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {prueba.asistentes} asistentes
                  {prueba.excede_limite_cortesia && " · excede el límite de cortesía"}
                </p>
                {prueba.notas_chef && (
                  <p className="mt-2 text-sm text-slate-600">"{prueba.notas_chef}"</p>
                )}
              </li>
            ))}
            {!evento.pruebas_menu?.length && (
              <p className="text-sm italic text-slate-400">Sin pruebas de menú agendadas.</p>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
