import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";

/**
 * Vista de Bodega e Inventario (Módulo D). Muestra:
 * 1) el inventario general de equipo (vajilla, cristalería, cubertería,
 *    mobiliario) con su stock disponible y costo de reposición,
 * 2) las listas de carga generadas automáticamente por evento, cruzando
 *    los tiempos de menú contratados con `RequerimientoEquipoTiempo`
 *    ("Cantidad a cargar" ya trae aplicado el Factor +10% de Rotura), con
 *    casillas para ir marcando qué ya se surtió al camión, y
 * 3) el Control de Retorno: marcar el conteo como completado y registrar
 *    roturas/extravíos (el costo de reposición del "Cargo por Daños" lo
 *    calcula el backend solo, a partir del catálogo de inventario).
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

function RoturaForm({ lista, onRegistrar, guardando }) {
  const [articuloId, setArticuloId] = useState("");
  const [cantidad, setCantidad] = useState(1);
  const [registradoPor, setRegistradoPor] = useState("");

  const articulos = lista.detalles ?? [];

  function handleSubmit(e) {
    e.preventDefault();
    if (!articuloId) return;
    onRegistrar({
      evento: lista.evento,
      articulo: Number(articuloId),
      cantidad_rota: Number(cantidad) || 1,
      registrado_por: registradoPor,
    }).then((ok) => {
      if (ok) {
        setArticuloId("");
        setCantidad(1);
      }
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-3 flex flex-wrap items-end gap-2 rounded-lg bg-slate-50 p-3"
    >
      <div className="flex flex-col gap-1">
        <label className="text-xs text-slate-500">Artículo roto/extraviado</label>
        <select
          value={articuloId}
          onChange={(e) => setArticuloId(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">Selecciona…</option>
          {articulos.map((det) => (
            <option key={det.articulo} value={det.articulo}>
              {det.articulo_nombre}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-slate-500">Cantidad</label>
        <input
          type="number"
          min="1"
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
          className="w-20 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-slate-500">Registrado por</label>
        <input
          type="text"
          placeholder="Capitán de Meseros"
          value={registradoPor}
          onChange={(e) => setRegistradoPor(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        />
      </div>
      <button
        type="submit"
        disabled={!articuloId || guardando}
        className="rounded-lg bg-navy-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
      >
        {guardando ? "Guardando…" : "Registrar rotura"}
      </button>
    </form>
  );
}

export default function Bodega() {
  const [inventario, setInventario] = useState([]);
  const [listas, setListas] = useState([]);
  const [roturas, setRoturas] = useState([]);
  const [estado, setEstado] = useState("cargando"); // "cargando" | "ok" | "error"
  const [guardandoRoturaId, setGuardandoRoturaId] = useState(null);
  const [actualizandoDetalleId, setActualizandoDetalleId] = useState(null);
  const [actualizandoListaId, setActualizandoListaId] = useState(null);

  function cargarDatos() {
    return Promise.all([
      fetch(`${API_BASE}/inventario-equipo/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      fetch(`${API_BASE}/listas-carga/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      fetch(`${API_BASE}/registros-roturas/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
    ]).then(([inv, lc, rot]) => {
      const listaInventario = Array.isArray(inv) ? inv : inv.results;
      const listaCargas = Array.isArray(lc) ? lc : lc.results;
      const listaRoturas = Array.isArray(rot) ? rot : rot.results;
      setInventario(Array.isArray(listaInventario) ? listaInventario : []);
      setListas(Array.isArray(listaCargas) ? listaCargas : []);
      setRoturas(Array.isArray(listaRoturas) ? listaRoturas : []);
    });
  }

  useEffect(() => {
    let cancelado = false;
    cargarDatos()
      .then(() => {
        if (!cancelado) setEstado("ok");
      })
      .catch(() => {
        if (!cancelado) setEstado("error");
      });
    return () => {
      cancelado = true;
    };
  }, []);

  function toggleSurtido(detalle) {
    setActualizandoDetalleId(detalle.id);
    fetch(`${API_BASE}/detalle-lista-carga/${detalle.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surtido: !detalle.surtido }),
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((actualizado) => {
        setListas((prev) =>
          prev.map((lista) => ({
            ...lista,
            detalles: lista.detalles?.map((d) =>
              d.id === actualizado.id ? { ...d, surtido: actualizado.surtido } : d
            ),
          }))
        );
      })
      .catch(() => {
        // Si falla, no cambiamos el estado local; el usuario puede reintentar.
      })
      .finally(() => setActualizandoDetalleId(null));
  }

  function marcarConteoCompletado(lista) {
    setActualizandoListaId(lista.id);
    fetch(`${API_BASE}/listas-carga/${lista.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conteo_retorno_completado: true }),
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(() => {
        setListas((prev) =>
          prev.map((l) =>
            l.id === lista.id ? { ...l, conteo_retorno_completado: true } : l
          )
        );
      })
      .catch(() => {})
      .finally(() => setActualizandoListaId(null));
  }

  function registrarRotura(lista, datos) {
    setGuardandoRoturaId(lista.id);
    return fetch(`${API_BASE}/registros-roturas/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((nuevaRotura) => {
        setRoturas((prev) => [nuevaRotura, ...prev]);
        return true;
      })
      .catch(() => false)
      .finally(() => setGuardandoRoturaId(null));
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold text-navy-900">Bodega e Inventario</h1>
        <p className="text-sm text-slate-500">
          Inventario general de equipo, listas de carga automáticas y Control de Retorno,
          con el Factor +10% de Rotura ya aplicado.
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
              Listas de carga y Control de Retorno
            </h2>
            <p className="mb-4 text-xs text-slate-500">
              "A cargar" ya incluye el +10% de margen de rotura. Marca "Surtido" conforme
              se va cargando al camión, y al regresar de un evento registra roturas y
              cierra el conteo de retorno.
            </p>
            <div className="flex flex-col gap-5">
              {listas.map((lista) => {
                const roturasDelEvento = roturas.filter((r) => r.evento === lista.evento);
                return (
                  <div key={lista.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold text-navy-900">{lista.evento_nombre}</p>
                      <div className="flex items-center gap-2">
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
                        {!lista.conteo_retorno_completado && (
                          <button
                            type="button"
                            onClick={() => marcarConteoCompletado(lista)}
                            disabled={actualizandoListaId === lista.id}
                            className="rounded-lg border border-navy-900/20 px-3 py-1 text-xs font-medium text-navy-900 hover:bg-navy-900/5 disabled:opacity-40"
                          >
                            {actualizandoListaId === lista.id
                              ? "Guardando…"
                              : "Marcar completado"}
                          </button>
                        )}
                      </div>
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
                                <input
                                  type="checkbox"
                                  checked={!!det.surtido}
                                  disabled={actualizandoDetalleId === det.id}
                                  onChange={() => toggleSurtido(det)}
                                  className="h-4 w-4 accent-teal-500"
                                />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {roturasDelEvento.length > 0 && (
                      <div className="mt-3 overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                              <th className="py-1.5 pr-4">Rotura/extravío</th>
                              <th className="py-1.5 pr-4">Cantidad</th>
                              <th className="py-1.5 pr-4">Cargo por daños</th>
                              <th className="py-1.5 pr-4">Registrado por</th>
                            </tr>
                          </thead>
                          <tbody>
                            {roturasDelEvento.map((r) => (
                              <tr key={r.id} className="border-b border-slate-100 last:border-0">
                                <td className="py-1.5 pr-4 text-slate-700">{r.articulo_nombre}</td>
                                <td className="py-1.5 pr-4 text-slate-600">{r.cantidad_rota}</td>
                                <td className="py-1.5 pr-4 font-medium text-red-700">
                                  {formatoMoneda(r.costo_reposicion)}
                                </td>
                                <td className="py-1.5 pr-4 text-slate-600">
                                  {r.registrado_por || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    <RoturaForm
                      lista={lista}
                      onRegistrar={(datos) => registrarRotura(lista, datos)}
                      guardando={guardandoRoturaId === lista.id}
                    />
                  </div>
                );
              })}
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
