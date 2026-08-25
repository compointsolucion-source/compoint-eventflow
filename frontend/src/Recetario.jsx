import { useEffect, useState } from "react";
import { API_BASE, authFetch } from "./api.js";

/**
 * Vista de Recetario / Food Cost. Trae el recetario maestro real del backend
 * (`GET /api/recetas/`), que ya incluye los ingredientes de cada receta con
 * su cantidad y unidad de medida. El margen de merma por insumo y el
 * algoritmo de Explosión de Insumos (Módulo C) viven en el backend
 * (`food_cost/services.py`) y se calculan por evento vía
 * `GET /api/eventos/<id>/explosion-insumos/`.
 */

const TIEMPO_LABELS = {
  ENTRADA: "Entrada",
  FUERTE: "Plato fuerte",
  POSTRE: "Postre",
  BEBIDA: "Bebida",
  BOTANA: "Botana / Coctel",
};

function formatoMoneda(valor) {
  const numero = Number(valor);
  if (Number.isNaN(numero)) return valor;
  return numero.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

export default function Recetario() {
  const [recetas, setRecetas] = useState([]);
  const [estado, setEstado] = useState("cargando"); // "cargando" | "ok" | "error"

  useEffect(() => {
    let cancelado = false;
    authFetch(`${API_BASE}/recetas/`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => {
        if (cancelado) return;
        const lista = Array.isArray(data) ? data : data.results;
        setRecetas(Array.isArray(lista) ? lista : []);
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
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-navy-900">Recetario / Food Cost</h1>
        <p className="text-sm text-slate-500">
          Recetario maestro escalable: ingredientes por receta base, costo estimado y
          margen de merma ya considerado en cada insumo.
        </p>
      </header>

      {estado === "error" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          No se pudo conectar al backend para traer el recetario. Verifica tu conexión e
          intenta recargar la página.
        </div>
      )}

      {estado === "cargando" && <p className="text-sm text-slate-500">Cargando recetario…</p>}

      {estado === "ok" && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {recetas.map((receta) => (
            <div key={receta.id} className="rounded-2xl bg-white p-5 shadow-sm">
              <div className="mb-3 flex items-start justify-between gap-2">
                <h2 className="font-semibold text-navy-900">{receta.nombre}</h2>
                <span className="shrink-0 rounded-full border border-teal-500/20 bg-teal-500/10 px-3 py-1 text-xs font-medium text-teal-700">
                  {TIEMPO_LABELS[receta.tiempo_menu] ?? receta.tiempo_menu}
                </span>
              </div>
              <p className="mb-3 text-xs text-slate-500">
                Receta base para {receta.porciones_base} porciones · Costo estimado{" "}
                {formatoMoneda(receta.costo_estimado)}
              </p>
              <ul className="flex flex-col gap-1.5">
                {receta.ingredientes?.map((ing) => (
                  <li
                    key={ing.id}
                    className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-sm text-slate-700"
                  >
                    <span>{ing.insumo_nombre}</span>
                    <span className="text-slate-500">
                      {ing.cantidad} {ing.unidad_medida}
                    </span>
                  </li>
                ))}
                {!receta.ingredientes?.length && (
                  <li className="text-xs italic text-slate-400">Sin ingredientes capturados.</li>
                )}
              </ul>
            </div>
          ))}
          {!recetas.length && (
            <p className="text-sm text-slate-500">
              Todavía no hay recetas capturadas. Agrégalas desde el panel de administración
              (/admin/).
            </p>
          )}
        </div>
      )}
    </div>
  );
}
