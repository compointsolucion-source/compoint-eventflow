import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";

/**
 * Vista de Bodega e Inventario (Módulo D). Muestra:
 * 1) el inventario general de equipo (vajilla, cristalería, cubertería,
 *    mobiliario) con su stock disponible y costo de reposición, y
 * 2) las listas de carga generadas automáticamente por evento, cruzando
 *    los tiempos de menú contratados con `RequerimientoEquipoTiempo`.
 *    "Cantidad a cargar" ya trae aplicado el Factor +10% de Rotura para
 *    nunca salir cortos de la bodega.
 */

const TIPO_LABELS = {
  VAJILLA: "Vajilla / Loza",
  CRISTALERIA: "Cristalería",
  CUBERTERIA: "Cubertería",
  MOBILIARIO: "Mobiliario",
  OTRO: "Otro",
};

function formatoMoneda(valor) {
  const numero = Number(valor);
  if (Number.isNaN(numero)) return valor;
  return numero.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

export default function Bodega() {
  const [inventario, setInventario] = useState([]);
  const [listas, setListas] = useState([]);
  const [estado, setEstado] = useState("cargando"); // "cargando" | "ok" | "error"

  useEffect(() => {
    let cancelado = false;
    Promise.all([
      fetch(`${API_BASE}/inventario-equipo/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      fetch(`${API_BASE}/listas-carga/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
    ])
      .then(([inv, lc]) => {
        if (cancelado) return;
        const listaInventario = Array.isArray(inv) ? inv : inv.results;
        const listaCargas = Array.isArray(lc) ? lc : lc.results;
        setInventario(Array.isArray(listaInventario) ? listaInventario : []);
        setListas(Array.isArray(listaCargas) ? listaCargas : []);
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
        <h1 className="text-2xl font-semibold text-navy-900">Bodega e Inventario</h1>
        <p className="text-sm text-slate-500">
          Inventario general de equipo y listas de carga automáticas por evento, con el
          Factor +10% de Rotura ya aplicado.
        </p>
      </header>

      {estado === "error" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          No se pudo conectar al backend para traer los datos de bodega. Verifica tu
          conexión e intenta recargar la página.
        </div>
      )}

      {estado === "cargando" && <p className="text-sm text-slate-500">Cargando…</p>}

      {estado === "ok" && (
        <>
          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-navy-900">Inventario general</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-4">Artículo</th>
                    <th className="py-2 pr-4">Tipo</th>
                    <th className="py-2 pr-4">Stock disponible</th>
                    <th className="py-2 pr-4">Costo de reposición</th>
                  </tr>
                </thead>
                <tbody>
                  {inventario.map((art) => (
                    <tr key={art.id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-4 font-medium text-navy-900">{art.nombre}</td>
                      <td className="py-2 pr-4 text-slate-600">
                        {TIPO_LABELS[art.tipo] ?? art.tipo}
                      </td>
                      <td className="py-2 pr-4 text-slate-600">{art.stock_disponible}</td>
                      <td className="py-2 pr-4 text-slate-600">
                        {formatoMoneda(art.costo_reposicion_unitario)}
                      </td>
                    </tr>
                  ))}
                  {!inventario.length && (
                    <tr>
                      <td colSpan={4} className="py-3 italic text-slate-400">
                        Sin artículos capturados todavía.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-1 text-lg font-semibold text-navy-900">
              Listas de carga por evento
            </h2>
            <p className="mb-4 text-xs text-slate-500">
              "A cargar" ya incluye el +10% de margen de rotura sobre lo estrictamente
              necesario para los invitados.
            </p>
            <div className="flex flex-col gap-5">
              {listas.map((lista) => (
                <div key={lista.id} className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold text-navy-900">{lista.evento_nombre}</p>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        lista.conteo_retorno_completado
                          ? "border border-teal-500/20 bg-teal-500/10 text-teal-700"
                          : "border border-amber-300 bg-amber-100 text-amber-800"
                      }`}
                    >
                      {lista.conteo_retorno_completado
                        ? "Conteo de retorno completado"
                        : "Pendiente conteo de retorno"}
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                          <th className="py-1.5 pr-4">Artículo</th>
                          <th className="py-1.5 pr-4">Requerido</th>
                          <th className="py-1.5 pr-4">A cargar (+10%)</th>
                          <th className="py-1.5 pr-4">Surtido</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lista.detalles?.map((det) => (
                          <tr key={det.id} className="border-b border-slate-100 last:border-0">
                            <td className="py-1.5 pr-4 text-slate-700">
                              {det.articulo_nombre}
                            </td>
                            <td className="py-1.5 pr-4 text-slate-600">
                              {det.cantidad_requerida}
                            </td>
                            <td className="py-1.5 pr-4 font-medium text-navy-900">
                              {det.cantidad_a_cargar}
                            </td>
                            <td className="py-1.5 pr-4">
                              {det.surtido ? (
                                <span className="text-teal-600">✓</span>
                              ) : (
                                <span className="text-slate-300">—</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
              {!listas.length && (
                <p className="text-sm italic text-slate-400">
                  Todavía no hay listas de carga generadas. Se crean automáticamente al
                  registrar el menú de un evento (o desde /admin/ con la acción
                  "Recalcular detalles").
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
