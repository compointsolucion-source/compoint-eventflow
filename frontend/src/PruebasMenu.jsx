import { useEffect, useMemo, useState } from "react";
import { API_BASE, authFetch } from "./api.js";

/**
 * Vista de Pruebas de Menú (Módulo B): agendar fichas de degustación y
 * revisar las ya programadas. Antes de este módulo, las Pruebas de Menú
 * solo se podían crear desde /admin/ — el bloqueo de fechas y las
 * sugerencias automáticas (`core/services_calendario.py`) ya existían en
 * el backend, pero sin pantalla propia en el frontend.
 *
 * Reglas que ya vienen del backend y esta pantalla solo refleja:
 * - No se puede agendar en un viernes/sábado que la empresa ya tenga
 *   ocupado con un evento confirmado/apartado (día de "alta operación").
 *   Si la fecha no sirve, el backend sugiere las próximas fechas libres.
 * - Si `asistentes` supera el límite de cortesía (4), se marca
 *   "Excede cortesía" — el monto del cobro adicional (`cobro_adicional_generado`)
 *   se sigue capturando a mano aquí (el backend todavía no lo calcula solo).
 */

function formatoFecha(fecha) {
  if (!fecha) return "—";
  return new Date(fecha + "T00:00:00").toLocaleDateString("es-MX", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatoMoneda(valor) {
  const numero = Number(valor);
  if (Number.isNaN(numero)) return valor;
  return numero.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

function hoyISO() {
  const hoy = new Date();
  const offset = hoy.getTimezoneOffset();
  return new Date(hoy.getTime() - offset * 60000).toISOString().slice(0, 10);
}

function AgendarPruebaForm({ eventos, recetas, onAgendar, guardando }) {
  const [eventoId, setEventoId] = useState("");
  const [fecha, setFecha] = useState("");
  const [asistentes, setAsistentes] = useState(4);
  const [platosSeleccionados, setPlatosSeleccionados] = useState([]);
  const [notasChef, setNotasChef] = useState("");
  const [disponibilidad, setDisponibilidad] = useState(null); // {disponible, sugerencias} | null
  const [revisando, setRevisando] = useState(false);
  const [error, setError] = useState("");

  // Revisa disponibilidad de la fecha (Módulo B) apenas se tienen evento +
  // fecha, sin esperar a que el usuario intente guardar — así ve de una vez
  // si ese día ya está ocupado y qué fechas cercanas sí sirven.
  useEffect(() => {
    if (!eventoId || !fecha) {
      setDisponibilidad(null);
      return;
    }
    let cancelado = false;
    setRevisando(true);
    authFetch(
      `${API_BASE}/pruebas-menu/fechas-disponibles/?evento=${eventoId}&fecha=${fecha}`
    )
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((datos) => {
        if (!cancelado) setDisponibilidad(datos);
      })
      .catch(() => {
        if (!cancelado) setDisponibilidad(null);
      })
      .finally(() => {
        if (!cancelado) setRevisando(false);
      });
    return () => {
      cancelado = true;
    };
  }, [eventoId, fecha]);

  function togglePlato(id) {
    setPlatosSeleccionados((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  }

  function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!eventoId || !fecha) {
      setError("Selecciona un evento y una fecha.");
      return;
    }
    onAgendar({
      evento: Number(eventoId),
      fecha_prueba: fecha,
      asistentes: Number(asistentes) || 1,
      platos_a_probar: platosSeleccionados,
      notas_chef: notasChef,
    }).then((resultado) => {
      if (resultado.ok) {
        setEventoId("");
        setFecha("");
        setAsistentes(4);
        setPlatosSeleccionados([]);
        setNotasChef("");
        setDisponibilidad(null);
      } else {
        setError(resultado.mensaje);
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-600">Evento</label>
          <select
            value={eventoId}
            onChange={(e) => setEventoId(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Selecciona un evento…</option>
            {eventos.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {ev.nombre_evento} · {formatoFecha(ev.fecha)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-600">Fecha de la prueba</label>
          <input
            type="date"
            min={hoyISO()}
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-slate-600">
            Asistentes (cortesía hasta 4)
          </label>
          <input
            type="number"
            min="1"
            value={asistentes}
            onChange={(e) => setAsistentes(e.target.value)}
            className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      {revisando && <p className="text-xs text-slate-400">Revisando disponibilidad…</p>}
      {!revisando && disponibilidad?.disponible === true && (
        <p className="rounded-lg border border-teal-500/20 bg-teal-500/10 px-3 py-2 text-xs font-medium text-teal-700">
          ✓ Fecha disponible.
        </p>
      )}
      {!revisando && disponibilidad?.disponible === false && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Ese día ya está ocupado (viernes/sábado de alta operación con otro evento).{" "}
          {disponibilidad.sugerencias?.length ? (
            <>
              Fechas cercanas libres:{" "}
              <strong>
                {disponibilidad.sugerencias.map((f) => formatoFecha(f)).join(", ")}
              </strong>
            </>
          ) : (
            "No se encontraron fechas libres en los próximos 60 días."
          )}
        </p>
      )}

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-600">
          Platos a probar (opcional)
        </label>
        <div className="flex max-h-36 flex-wrap gap-2 overflow-y-auto rounded-lg border border-slate-200 p-2">
          {recetas.map((receta) => (
            <button
              key={receta.id}
              type="button"
              onClick={() => togglePlato(receta.id)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                platosSeleccionados.includes(receta.id)
                  ? "border-teal-500/30 bg-teal-500 text-white"
                  : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {receta.nombre}
            </button>
          ))}
          {!recetas.length && (
            <p className="text-xs italic text-slate-400">Sin recetas capturadas todavía.</p>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-600">
          Notas del Chef (opcional)
        </label>
        <textarea
          value={notasChef}
          onChange={(e) => setNotasChef(e.target.value)}
          rows={2}
          placeholder='Ej. "Salsa de champiñones más espesa, término de la carne 3/4"'
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div>
        <button
          type="submit"
          disabled={guardando}
          className="rounded-lg bg-navy-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {guardando ? "Agendando…" : "Agendar prueba de menú"}
        </button>
      </div>
    </form>
  );
}

function FilaPrueba({ prueba, eventosPorId, recetasPorId, onGuardarCambios, ocupado }) {
  const [notas, setNotas] = useState(prueba.notas_chef ?? "");
  const [cobro, setCobro] = useState(prueba.cobro_adicional_generado ?? "0.00");
  const [editando, setEditando] = useState(false);
  const evento = eventosPorId[prueba.evento];

  function guardar() {
    onGuardarCambios(prueba, { notas_chef: notas, cobro_adicional_generado: cobro }).then(
      (ok) => {
        if (ok) setEditando(false);
      }
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-semibold text-navy-900">
            {evento?.nombre_evento ?? `Evento #${prueba.evento}`}
          </p>
          <p className="text-xs text-slate-500">
            {formatoFecha(prueba.fecha_prueba)} · {prueba.asistentes} asistentes
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {prueba.dia_alta_operacion && (
            <span className="rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              Día de alta operación
            </span>
          )}
          {prueba.excede_limite_cortesia && (
            <span className="rounded-full border border-amber-300 bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
              Excede cortesía
            </span>
          )}
          <button
            type="button"
            disabled={ocupado}
            onClick={() =>
              onGuardarCambios(prueba, { aprobado: !prueba.aprobado }).then(() => {})
            }
            className={`rounded-full px-3 py-1 text-xs font-medium disabled:opacity-40 ${
              prueba.aprobado
                ? "border border-teal-500/20 bg-teal-500/10 text-teal-700"
                : "border border-slate-300 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {prueba.aprobado ? "✓ Aprobada" : "Marcar como aprobada"}
          </button>
        </div>
      </div>

      {prueba.platos_a_probar?.length > 0 && (
        <p className="mb-2 text-xs text-slate-500">
          Platos a probar:{" "}
          {prueba.platos_a_probar
            .map((id) => recetasPorId[id]?.nombre ?? `#${id}`)
            .join(", ")}
        </p>
      )}

      {!editando ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-sm text-slate-600">
            {prueba.notas_chef || <span className="italic text-slate-400">Sin notas del Chef.</span>}
            {Number(prueba.cobro_adicional_generado) > 0 && (
              <span className="ml-2 font-medium text-navy-900">
                · Cobro adicional: {formatoMoneda(prueba.cobro_adicional_generado)}
              </span>
            )}
          </p>
          <button
            type="button"
            onClick={() => setEditando(true)}
            className="shrink-0 text-xs font-medium text-teal-700 hover:underline"
          >
            Editar
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2 rounded-lg bg-slate-50 p-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500">Notas del Chef</label>
            <textarea
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              rows={2}
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500">
              Cobro adicional (si excede cortesía — se captura a mano)
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={cobro}
              onChange={(e) => setCobro(e.target.value)}
              className="w-32 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={ocupado}
              onClick={guardar}
              className="rounded-lg bg-navy-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
            >
              {ocupado ? "Guardando…" : "Guardar"}
            </button>
            <button
              type="button"
              onClick={() => {
                setNotas(prueba.notas_chef ?? "");
                setCobro(prueba.cobro_adicional_generado ?? "0.00");
                setEditando(false);
              }}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PruebasMenu() {
  const [pruebas, setPruebas] = useState([]);
  const [eventos, setEventos] = useState([]);
  const [recetas, setRecetas] = useState([]);
  const [estado, setEstado] = useState("cargando"); // "cargando" | "ok" | "error"
  const [guardandoNueva, setGuardandoNueva] = useState(false);
  const [pruebaOcupadaId, setPruebaOcupadaId] = useState(null);

  useEffect(() => {
    let cancelado = false;
    Promise.all([
      authFetch(`${API_BASE}/pruebas-menu/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      authFetch(`${API_BASE}/eventos/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
      authFetch(`${API_BASE}/recetas/`).then((res) =>
        res.ok ? res.json() : Promise.reject(res.status)
      ),
    ])
      .then(([pm, ev, rec]) => {
        if (cancelado) return;
        const listaPruebas = Array.isArray(pm) ? pm : pm.results;
        const listaEventos = Array.isArray(ev) ? ev : ev.results;
        const listaRecetas = Array.isArray(rec) ? rec : rec.results;
        setPruebas(Array.isArray(listaPruebas) ? listaPruebas : []);
        setEventos(Array.isArray(listaEventos) ? listaEventos : []);
        setRecetas(Array.isArray(listaRecetas) ? listaRecetas : []);
        setEstado("ok");
      })
      .catch(() => {
        if (!cancelado) setEstado("error");
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const eventosPorId = useMemo(
    () => Object.fromEntries(eventos.map((e) => [e.id, e])),
    [eventos]
  );
  const recetasPorId = useMemo(
    () => Object.fromEntries(recetas.map((r) => [r.id, r])),
    [recetas]
  );

  function agendarPrueba(datos) {
    setGuardandoNueva(true);
    return authFetch(`${API_BASE}/pruebas-menu/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    })
      .then(async (res) => {
        if (!res.ok) {
          const cuerpo = await res.json().catch(() => ({}));
          const mensaje =
            cuerpo.fecha_prueba?.[0] ||
            cuerpo.detail ||
            "No se pudo agendar la prueba de menú. Revisa los datos.";
          return { ok: false, mensaje };
        }
        const nueva = await res.json();
        setPruebas((prev) => [...prev, nueva].sort((a, b) => (a.fecha_prueba < b.fecha_prueba ? -1 : 1)));
        return { ok: true };
      })
      .catch(() => ({ ok: false, mensaje: "No se pudo conectar al backend." }))
      .finally(() => setGuardandoNueva(false));
  }

  function guardarCambiosPrueba(prueba, cambios) {
    setPruebaOcupadaId(prueba.id);
    return authFetch(`${API_BASE}/pruebas-menu/${prueba.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cambios),
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((actualizada) => {
        setPruebas((prev) => prev.map((p) => (p.id === actualizada.id ? actualizada : p)));
        return true;
      })
      .catch(() => false)
      .finally(() => setPruebaOcupadaId(null));
  }

  const pruebasOrdenadas = useMemo(
    () => [...pruebas].sort((a, b) => (a.fecha_prueba < b.fecha_prueba ? -1 : 1)),
    [pruebas]
  );

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold text-navy-900">Pruebas de Menú</h1>
        <p className="text-sm text-slate-500">
          Agenda fichas de degustación cruzando el calendario con los eventos de alta
          operación (Módulo B) y da seguimiento a las ya programadas.
        </p>
      </header>

      {estado === "error" && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          No se pudo conectar al backend para traer las pruebas de menú. Verifica tu
          conexión e intenta recargar la página.
        </div>
      )}

      {estado === "cargando" && <p className="text-sm text-slate-500">Cargando…</p>}

      {estado === "ok" && (
        <>
          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-1 text-lg font-semibold text-navy-900">
              Agendar nueva prueba de menú
            </h2>
            <p className="mb-4 text-xs text-slate-500">
              Un viernes o sábado ya ocupado por un evento confirmado o apartado se
              bloquea automáticamente — el sistema te sugiere las fechas libres más
              cercanas.
            </p>
            <AgendarPruebaForm
              eventos={eventos}
              recetas={recetas}
              onAgendar={agendarPrueba}
              guardando={guardandoNueva}
            />
          </section>

          <section className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-navy-900">
              Pruebas de menú programadas
            </h2>
            <div className="flex flex-col gap-4">
              {pruebasOrdenadas.map((prueba) => (
                <FilaPrueba
                  key={prueba.id}
                  prueba={prueba}
                  eventosPorId={eventosPorId}
                  recetasPorId={recetasPorId}
                  onGuardarCambios={guardarCambiosPrueba}
                  ocupado={pruebaOcupadaId === prueba.id}
                />
              ))}
              {!pruebasOrdenadas.length && (
                <p className="text-sm italic text-slate-400">
                  Todavía no hay pruebas de menú agendadas.
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
