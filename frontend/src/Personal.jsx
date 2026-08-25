import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";

/**
 * Vista de Personal Eventual (Módulo E): Bolsa de Trabajo y Check-In.
 * Muestra:
 * 1) el directorio de personal eventual registrado (meseros, bartenders,
 *    garroteros, capitanes) disponible para postularse a vacantes, y
 * 2) las vacantes abiertas por evento, con sus postulaciones y el estado
 *    de check-in de cada una (el código de verificación hace las veces de
 *    un QR/credencial que el Capitán de Meseros confirma el día del evento).
 */

const ROL_LABELS = {
  MESERO: "Mesero",
  BARTENDER: "Bartender",
  GARROTERO: "Garrotero",
  CAPITAN: "Capitán de Meseros",
  OTRO: "Otro",
};

const ESTADO_POSTULACION_STYLES = {
  ACEPTADO: "border border-teal-500/20 bg-teal-500/10 text-teal-700",
  POSTULADO: "border border-amber-300 bg-amber-100 text-amber-800",
  RECHAZADO: "border border-slate-300 bg-slate-100 text-slate-500",
};

const ESTADO_POSTULACION_LABELS = {
  ACEPTADO: "Aceptado",
  POSTULADO: "Postulado",
  RECHAZADO: "Rechazado",
};

function formatoFecha(fecha) {
  if (!fecha) return "—";
  return new Date(fecha + "T00:00:00").toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function Personal() {
  const [personal, setPersonal] = useState([]);
  const [vacantes, setVacantes] = useState([]);
  const [estado, setEstado] = useState("cargando"); // "cargando" | "ok" | "error"

  useEffect(() => {
    let cancelado = false;
    Promise.all([
      fetch(`${API_BASE}/personal-eventual/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      fetch(`${API_BASE}/vacantes/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
    ])
      .then(([per, vac]) => {
        if (cancelado) return;
        const listaPersonal = Array.isArray(per) ? per : per.results;
        const listaVacantes = Array.isArray(vac) ? vac : vac.results;
        setPersonal(Array.isArray(listaPersonal) ? listaPersonal : []);
        setVacantes(Array.isArray(listaVacantes) ? listaVacantes : []);
        setEstado("ok");
      })
      .catch(() => {
        if (!cancelado) setEstado("error");
      });
    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold text-navy-900">Personal Eventual</h1>
        <p className="text-sm text-slate-500">
          Bolsa de Trabajo por evento y Check-In del día: quién se postuló, quién fue
          aceptado y quién ya confirmó su asistencia.
        </p>
      </header>

      {estado === "error" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          No se pudo conectar al backend para traer los datos de personal eventual.
          Verifica tu conexión e intenta recargar la página.
        </div>
      )}

      {estado === "cargando" && <p className="text-sm text-slate-500">Cargando…</p>}

      {estado === "ok" && (
        <>
          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-navy-900">
              Personal registrado
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-4">Nombre</th>
                    <th className="py-2 pr-4">Rol principal</th>
                    <th className="py-2 pr-4">Teléfono</th>
                    <th className="py-2 pr-4">Disponibilidad</th>
                  </tr>
                </thead>
                <tbody>
                  {personal.map((p) => (
                    <tr key={p.id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-4 font-medium text-navy-900">{p.nombre}</td>
                      <td className="py-2 pr-4 text-slate-600">
                        {ROL_LABELS[p.rol_principal] ?? p.rol_principal}
                      </td>
                      <td className="py-2 pr-4 text-slate-600">{p.telefono}</td>
                      <td className="py-2 pr-4">
                        {p.activo ? (
                          <span className="rounded-full border border-teal-500/20 bg-teal-500/10 px-3 py-1 text-xs font-medium text-teal-700">
                            Disponible
                          </span>
                        ) : (
                          <span className="rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                            No disponible
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!personal.length && (
                    <tr>
                      <td colSpan={4} className="py-3 italic text-slate-400">
                        Sin personal capturado todavía.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-1 text-lg font-semibold text-navy-900">
              Bolsa de Trabajo por evento
            </h2>
            <p className="mb-4 text-xs text-slate-500">
              El código de verificación equivale al QR/credencial que el Capitán de
              Meseros confirma el día del evento.
            </p>
            <div className="flex flex-col gap-5">
              {vacantes.map((vac) => (
                <div key={vac.id} className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold text-navy-900">{vac.evento_nombre}</p>
                      <p className="text-xs text-slate-500">
                        {formatoFecha(vac.fecha_evento)} · {ROL_LABELS[vac.rol] ?? vac.rol}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                        {vac.cantidad_aceptada}/{vac.cantidad_requerida} cubiertos
                      </span>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          vac.cubierta
                            ? "border border-teal-500/20 bg-teal-500/10 text-teal-700"
                            : "border border-amber-300 bg-amber-100 text-amber-800"
                        }`}
                      >
                        {vac.cubierta ? "Vacante cubierta" : "Faltan postulantes"}
                      </span>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                          <th className="py-1.5 pr-4">Postulante</th>
                          <th className="py-1.5 pr-4">Teléfono</th>
                          <th className="py-1.5 pr-4">Estado</th>
                          <th className="py-1.5 pr-4">Check-in</th>
                          <th className="py-1.5 pr-4">Código</th>
                        </tr>
                      </thead>
                      <tbody>
                        {vac.postulaciones?.map((post) => (
                          <tr key={post.id} className="border-b border-slate-100 last:border-0">
                            <td className="py-1.5 pr-4 font-medium text-navy-900">
                              {post.personal_nombre}
                            </td>
                            <td className="py-1.5 pr-4 text-slate-600">
                              {post.personal_telefono}
                            </td>
                            <td className="py-1.5 pr-4">
                              <span
                                className={`rounded-full px-3 py-1 text-xs font-medium ${
                                  ESTADO_POSTULACION_STYLES[post.estado] ?? ""
                                }`}
                              >
                                {ESTADO_POSTULACION_LABELS[post.estado] ?? post.estado}
                              </span>
                            </td>
                            <td className="py-1.5 pr-4">
                              {post.check_in ? (
                                post.check_in.asistio ? (
                                  <span className="text-teal-600">✓ Presente</span>
                                ) : (
                                  <span className="text-amber-600">Pendiente</span>
                                )
                              ) : (
                                <span className="text-slate-300">—</span>
                              )}
                            </td>
                            <td className="py-1.5 pr-4 font-mono text-xs text-slate-500">
                              {post.check_in?.codigo_verificacion ?? "—"}
                            </td>
                          </tr>
                        ))}
                        {!vac.postulaciones?.length && (
                          <tr>
                            <td colSpan={5} className="py-2 italic text-slate-400">
                              Sin postulaciones todavía.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
              {!vacantes.length && (
                <p className="text-sm italic text-slate-400">
                  Todavía no hay vacantes abiertas. Se crean por evento desde /admin/ (una
                  por rol requerido, ej. 3 meseros, 1 bartender).
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
