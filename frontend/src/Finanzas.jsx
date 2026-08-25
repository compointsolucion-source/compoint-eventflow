import { useEffect, useState } from "react";
import { API_BASE, authFetch } from "./api.js";

/**
 * Vista de Finanzas (Módulo F): Cotizador por Volumen y Esquema de Cobro
 * Automatizado 50/30/20. Muestra:
 * 1) el Cotizador por Volumen: la configuración de costos (base por persona
 *    + costos fijos de transporte/personal) y el precio ya calculado por el
 *    backend para cada evento — a menor número de invitados, mayor precio
 *    por persona, porque los costos fijos se reparten entre menos gente.
 * 2) el Esquema de Cobro 50/30/20 por evento: anticipo, pago intermedio
 *    (fecha de prueba de menú) y liquidación (15 días antes del evento),
 *    con el estado de cada abono (pagado / vencido / pendiente).
 *
 * Es interactiva: cada abono pendiente/vencido tiene un botón "Marcar como
 * pagado" (el cobro en sí se sigue haciendo por fuera del sistema —
 * transferencia, terminal, efectivo — esto solo registra que ya se pagó).
 */

function formatoMoneda(valor) {
  const numero = Number(valor);
  if (Number.isNaN(numero)) return valor;
  return numero.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

function formatoFecha(fecha) {
  if (!fecha) return "—";
  return new Date(fecha + "T00:00:00").toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

const TIPO_ABONO_LABELS = {
  ANTICIPO: "Anticipo (50%)",
  INTERMEDIO: "Intermedio (30%)",
  LIQUIDACION: "Liquidación (20%)",
};

function EstadoAbonoBadge({ abono }) {
  if (abono.pagado) {
    return (
      <span className="rounded-full border border-teal-500/20 bg-teal-500/10 px-3 py-1 text-xs font-medium text-teal-700">
        Pagado {abono.fecha_pago ? `· ${formatoFecha(abono.fecha_pago)}` : ""}
      </span>
    );
  }
  if (abono.vencido) {
    return (
      <span className="rounded-full border border-red-300 bg-red-100 px-3 py-1 text-xs font-medium text-red-700">
        Vencido
      </span>
    );
  }
  if (abono.proximo_a_vencer) {
    return (
      <span className="rounded-full border border-orange-300 bg-orange-100 px-3 py-1 text-xs font-medium text-orange-800">
        Por vencer {abono.alerta_enviada ? "· correo enviado" : ""}
      </span>
    );
  }
  return (
    <span className="rounded-full border border-amber-300 bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
      Pendiente
    </span>
  );
}

function FilaAbono({ abono, onMarcarPagado, ocupado }) {
  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="py-1.5 pr-4 text-slate-700">
        {TIPO_ABONO_LABELS[abono.tipo] ?? abono.tipo}
      </td>
      <td className="py-1.5 pr-4 font-medium text-navy-900">
        {formatoMoneda(abono.monto)}
      </td>
      <td className="py-1.5 pr-4 text-slate-600">{formatoFecha(abono.fecha_limite)}</td>
      <td className="py-1.5 pr-4">
        <EstadoAbonoBadge abono={abono} />
      </td>
      <td className="py-1.5 pr-4">
        {!abono.pagado && (
          <button
            type="button"
            disabled={ocupado}
            onClick={() => onMarcarPagado(abono)}
            className="rounded-lg bg-navy-900 px-2.5 py-1 text-xs font-medium text-white disabled:opacity-40"
          >
            {ocupado ? "Guardando…" : "Marcar como pagado"}
          </button>
        )}
      </td>
    </tr>
  );
}

export default function Finanzas() {
  const [configuracion, setConfiguracion] = useState(null);
  const [esquemas, setEsquemas] = useState([]);
  const [eventos, setEventos] = useState([]);
  const [cotizaciones, setCotizaciones] = useState({}); // evento_id -> cotización | null
  const [estado, setEstado] = useState("cargando"); // "cargando" | "ok" | "error"
  const [abonoOcupado, setAbonoOcupado] = useState(null);
  const [enviandoAlertas, setEnviandoAlertas] = useState(false);
  const [resultadoAlertas, setResultadoAlertas] = useState(null);

  useEffect(() => {
    let cancelado = false;
    Promise.all([
      authFetch(`${API_BASE}/configuracion-cotizador/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      authFetch(`${API_BASE}/esquemas-pago/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      authFetch(`${API_BASE}/eventos/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
    ])
      .then(([config, esq, ev]) => {
        if (cancelado) return;
        const listaConfig = Array.isArray(config) ? config : config.results;
        const listaEsquemas = Array.isArray(esq) ? esq : esq.results;
        const listaEventos = Array.isArray(ev) ? ev : ev.results;
        setConfiguracion(
          Array.isArray(listaConfig) && listaConfig.length ? listaConfig[0] : null
        );
        setEsquemas(Array.isArray(listaEsquemas) ? listaEsquemas : []);
        setEventos(Array.isArray(listaEventos) ? listaEventos : []);
        setEstado("ok");
      })
      .catch(() => {
        if (!cancelado) setEstado("error");
      });
    return () => {
      cancelado = true;
    };
  }, []);

  // Una vez que tenemos la lista de eventos, pedimos la cotización ya
  // calculada por el backend (precio por persona y total) para cada uno.
  useEffect(() => {
    if (!eventos.length) return;
    let cancelado = false;
    Promise.all(
      eventos.map((ev) =>
        authFetch(`${API_BASE}/eventos/${ev.id}/cotizacion/`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => [ev.id, data])
          .catch(() => [ev.id, null])
      )
    ).then((pares) => {
      if (cancelado) return;
      setCotizaciones(Object.fromEntries(pares));
    });
    return () => {
      cancelado = true;
    };
  }, [eventos]);

  function marcarAbonoPagado(abono) {
    setAbonoOcupado(abono.id);
    authFetch(`${API_BASE}/abonos/${abono.id}/marcar-pagado/`, { method: "POST" })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((actualizado) => {
        setEsquemas((prev) =>
          prev.map((esq) => ({
            ...esq,
            abonos: esq.abonos?.map((a) => (a.id === actualizado.id ? actualizado : a)),
          }))
        );
      })
      .catch(() => {})
      .finally(() => setAbonoOcupado(null));
  }

  function enviarAlertasPendientes() {
    setEnviandoAlertas(true);
    setResultadoAlertas(null);
    authFetch(`${API_BASE}/abonos/enviar-alertas-pendientes/`, { method: "POST" })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((resumen) => {
        setResultadoAlertas(resumen);
        // Refresca los esquemas para reflejar los abonos que ya marcaron
        // alerta_enviada (así el badge "Por vencer · correo enviado" se
        // actualiza sin tener que recargar la página).
        return authFetch(`${API_BASE}/esquemas-pago/`).then((res) =>
          res.ok ? res.json() : Promise.reject(res.status)
        );
      })
      .then((esq) => {
        const listaEsquemas = Array.isArray(esq) ? esq : esq.results;
        setEsquemas(Array.isArray(listaEsquemas) ? listaEsquemas : []);
      })
      .catch(() => setResultadoAlertas({ error: true }))
      .finally(() => setEnviandoAlertas(false));
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold text-navy-900">Finanzas</h1>
        <p className="text-sm text-slate-500">
          Cotizador por Volumen y Esquema de Cobro Automatizado 50/30/20 por evento.
        </p>
      </header>

      {estado === "error" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          No se pudo conectar al backend para traer los datos financieros. Verifica tu
          conexión e intenta recargar la página.
        </div>
      )}

      {estado === "cargando" && <p className="text-sm text-slate-500">Cargando…</p>}

      {estado === "ok" && (
        <>
          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-1 text-lg font-semibold text-navy-900">
              Cotizador por Volumen
            </h2>
            <p className="mb-4 text-xs text-slate-500">
              A menor número de invitados, mayor precio por persona: los costos fijos de
              transporte y personal se reparten entre menos comensales.
            </p>

            {configuracion ? (
              <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    Costo base por persona
                  </p>
                  <p className="mt-1 text-xl font-semibold text-navy-900">
                    {formatoMoneda(configuracion.costo_base_por_persona)}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-xs uppercase tracking-wide text-slate-500">
                    Costos fijos de transporte y personal
                  </p>
                  <p className="mt-1 text-xl font-semibold text-navy-900">
                    {formatoMoneda(configuracion.costos_fijos_transporte_personal)}
                  </p>
                </div>
              </div>
            ) : (
              <p className="mb-5 text-sm italic text-slate-400">
                Todavía no se ha configurado el Cotizador para esta empresa (falta crear
                su ConfiguracionCotizador desde /admin/).
              </p>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-4">Evento</th>
                    <th className="py-2 pr-4">Invitados</th>
                    <th className="py-2 pr-4">Precio por persona</th>
                    <th className="py-2 pr-4">Precio total</th>
                  </tr>
                </thead>
                <tbody>
                  {eventos.map((ev) => {
                    const cot = cotizaciones[ev.id];
                    return (
                      <tr key={ev.id} className="border-b border-slate-100 last:border-0">
                        <td className="py-2 pr-4 font-medium text-navy-900">
                          {ev.nombre_evento}
                        </td>
                        <td className="py-2 pr-4 text-slate-600">{ev.numero_invitados}</td>
                        <td className="py-2 pr-4 text-slate-600">
                          {cot ? formatoMoneda(cot.precio_por_persona) : "—"}
                        </td>
                        <td className="py-2 pr-4 font-medium text-navy-900">
                          {cot ? formatoMoneda(cot.precio_total) : "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {!eventos.length && (
                    <tr>
                      <td colSpan={4} className="py-3 italic text-slate-400">
                        Sin eventos capturados todavía.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <div className="mb-1 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-navy-900">
                  Esquema de Cobro 50/30/20
                </h2>
                <p className="mb-1 text-xs text-slate-500">
                  Anticipo al apartar, pago intermedio en la fecha de prueba de menú, y
                  liquidación 15 días antes del evento.
                </p>
              </div>
              <button
                type="button"
                disabled={enviandoAlertas}
                onClick={enviarAlertasPendientes}
                className="whitespace-nowrap rounded-lg border border-navy-900 px-3 py-1.5 text-xs font-medium text-navy-900 disabled:opacity-40"
              >
                {enviandoAlertas ? "Enviando…" : "Enviar alertas pendientes"}
              </button>
            </div>
            {resultadoAlertas && (
              <p className="mb-3 text-xs text-slate-500">
                {resultadoAlertas.error
                  ? "No se pudieron enviar las alertas. Intenta de nuevo."
                  : `Correos enviados: ${resultadoAlertas.enviados?.length ?? 0}. ` +
                    `Omitidos por no tener correo capturado: ` +
                    `${resultadoAlertas.omitidos_sin_correo?.length ?? 0}.`}
              </p>
            )}
            <p className="mb-4 text-xs text-slate-400">
              Recordatorio por correo cuando falta poco para la fecha límite de un
              abono (no cobra nada: el pago se sigue registrando por fuera con
              "Marcar como pagado").
            </p>
            <div className="flex flex-col gap-5">
              {esquemas.map((esq) => (
                <div key={esq.id} className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold text-navy-900">{esq.evento_nombre}</p>
                      <p className="text-xs text-slate-500">
                        {formatoFecha(esq.fecha_evento)}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                      Monto total: {formatoMoneda(esq.monto_total)}
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                          <th className="py-1.5 pr-4">Abono</th>
                          <th className="py-1.5 pr-4">Monto</th>
                          <th className="py-1.5 pr-4">Fecha límite</th>
                          <th className="py-1.5 pr-4">Estado</th>
                          <th className="py-1.5 pr-4">Acciones</th>
                        </tr>
                      </thead>
                      <tbody>
                        {esq.abonos?.map((abono) => (
                          <FilaAbono
                            key={abono.id}
                            abono={abono}
                            ocupado={abonoOcupado === abono.id}
                            onMarcarPagado={marcarAbonoPagado}
                          />
                        ))}
                        {!esq.abonos?.length && (
                          <tr>
                            <td colSpan={5} className="py-2 italic text-slate-400">
                              Sin abonos generados todavía.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
              {!esquemas.length && (
                <p className="text-sm italic text-slate-400">
                  Todavía no hay esquemas de cobro generados. Se crean por evento desde
                  /admin/ con la acción "Generar/actualizar abonos 50/30/20".
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
