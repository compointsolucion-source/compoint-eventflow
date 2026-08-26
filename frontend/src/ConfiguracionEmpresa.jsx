import { useEffect, useState } from "react";
import { API_BASE, authFetch } from "./api.js";

/**
 * Pantalla de Configuración de Empresa: permite editar, sin entrar a
 * `/admin/`, los parámetros de `EmpresaBanquetera` que hasta ahora solo se
 * podían cambiar desde el admin de Django — datos de contacto y las reglas
 * automáticas de varios módulos (Semáforo de Fechas, alertas de abonos por
 * correo, y el cobro adicional automático de Pruebas de Menú).
 *
 * El sistema es de una sola empresa por instalación (single-tenant en la
 * práctica, aunque el modelo de datos soporte varias): se toma siempre el
 * primer resultado de `GET /api/empresas/` y se guarda con
 * `PATCH /api/empresas/<id>/`.
 */

const CAMPOS_NUMERICOS = new Set([
  "horas_vencimiento_prospecto",
  "dias_habiles_limite_anticipo",
  "dias_anticipacion_alerta_abono",
  "costo_extra_por_asistente_prueba_menu",
]);

function Campo({ label, ayuda, children }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-medium text-navy-900">{label}</span>
      {children}
      {ayuda && <span className="text-xs text-slate-500">{ayuda}</span>}
    </label>
  );
}

export default function ConfiguracionEmpresa() {
  const [empresa, setEmpresa] = useState(null);
  const [form, setForm] = useState(null);
  const [estado, setEstado] = useState("cargando"); // cargando | ok | sin-empresa | error
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState(null); // { tipo: "ok" | "error", texto }

  useEffect(() => {
    authFetch(`${API_BASE}/empresas/`)
      .then((res) => {
        if (!res.ok) throw new Error("error");
        return res.json();
      })
      .then((datos) => {
        const lista = Array.isArray(datos) ? datos : datos.results ?? [];
        if (!lista.length) {
          setEstado("sin-empresa");
          return;
        }
        setEmpresa(lista[0]);
        setForm(lista[0]);
        setEstado("ok");
      })
      .catch(() => setEstado("error"));
  }, []);

  function actualizarCampo(campo, valor) {
    setForm((anterior) => ({ ...anterior, [campo]: valor }));
  }

  function guardar(evento) {
    evento.preventDefault();
    setGuardando(true);
    setMensaje(null);
    const cuerpo = { ...form };
    // Los campos numéricos vienen del <input> como string; el backend los
    // valida igual, pero los mandamos limpios por claridad.
    CAMPOS_NUMERICOS.forEach((campo) => {
      if (cuerpo[campo] !== undefined && cuerpo[campo] !== "") {
        cuerpo[campo] = String(cuerpo[campo]);
      }
    });
    authFetch(`${API_BASE}/empresas/${empresa.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    })
      .then((res) => {
        if (!res.ok) return res.json().then((cuerpoError) => Promise.reject(cuerpoError));
        return res.json();
      })
      .then((actualizada) => {
        setEmpresa(actualizada);
        setForm(actualizada);
        setMensaje({ tipo: "ok", texto: "Cambios guardados correctamente." });
      })
      .catch((cuerpoError) => {
        const primerError = Object.values(cuerpoError || {})[0];
        const texto = Array.isArray(primerError) ? primerError[0] : "No se pudo guardar. Revisa los datos.";
        setMensaje({ tipo: "error", texto });
      })
      .finally(() => setGuardando(false));
  }

  if (estado === "cargando") {
    return <p className="p-6 text-sm text-slate-500">Cargando configuración…</p>;
  }

  if (estado === "sin-empresa") {
    return (
      <div className="max-w-xl rounded-2xl bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-600">
          Todavía no hay una empresa creada. Usa el endpoint de inicialización o crea la
          empresa desde <code className="rounded bg-slate-100 px-1">/admin/</code> antes de
          configurar estos parámetros.
        </p>
      </div>
    );
  }

  if (estado === "error") {
    return (
      <div className="max-w-xl rounded-2xl bg-white p-6 shadow-sm">
        <p className="text-sm text-red-600">
          No se pudo cargar la configuración de la empresa. Intenta recargar la página.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={guardar} className="flex max-w-3xl flex-col gap-6 pb-10">
      <div>
        <h1 className="text-2xl font-semibold text-navy-900">Configuración de Empresa</h1>
        <p className="mt-1 text-sm text-slate-500">
          Ajusta los datos de contacto y las reglas automáticas de COMPOINT EventFlow.
        </p>
      </div>

      <section className="rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-navy-900">Datos de la empresa</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Campo label="Nombre comercial">
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.nombre_comercial ?? ""}
              onChange={(e) => actualizarCampo("nombre_comercial", e.target.value)}
              required
            />
          </Campo>
          <Campo label="Razón social">
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.razon_social ?? ""}
              onChange={(e) => actualizarCampo("razon_social", e.target.value)}
            />
          </Campo>
          <Campo label="RFC / identificación fiscal">
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.rfc ?? ""}
              onChange={(e) => actualizarCampo("rfc", e.target.value)}
            />
          </Campo>
          <Campo label="Teléfono de contacto">
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.telefono_contacto ?? ""}
              onChange={(e) => actualizarCampo("telefono_contacto", e.target.value)}
            />
          </Campo>
          <Campo label="Correo de contacto" ayuda="Recibe copia de las alertas de abonos por vencer.">
            <input
              type="email"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.email_contacto ?? ""}
              onChange={(e) => actualizarCampo("email_contacto", e.target.value)}
            />
          </Campo>
          <Campo label="Dirección de la bodega central">
            <input
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.direccion_bodega_central ?? ""}
              onChange={(e) => actualizarCampo("direccion_bodega_central", e.target.value)}
            />
          </Campo>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-navy-900">Semáforo de Fechas (Módulo A)</h2>
        <p className="mb-4 text-sm text-slate-500">
          Plazos automáticos para que un Prospecto o un Apartado se marquen como vencidos.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Campo
            label="Horas para que venza un Prospecto"
            ayuda="Ej. 72 = si en 72 horas no pasa a Apartado o Confirmado, se marca Vencido."
          >
            <input
              type="number"
              min="1"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.horas_vencimiento_prospecto ?? ""}
              onChange={(e) => actualizarCampo("horas_vencimiento_prospecto", e.target.value)}
              required
            />
          </Campo>
          <Campo
            label="Días hábiles para recibir el anticipo de un Apartado"
            ayuda="Ej. 5 = si no llega el anticipo en 5 días hábiles, se libera la fecha."
          >
            <input
              type="number"
              min="1"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.dias_habiles_limite_anticipo ?? ""}
              onChange={(e) => actualizarCampo("dias_habiles_limite_anticipo", e.target.value)}
              required
            />
          </Campo>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-navy-900">Alertas de abonos por correo (Módulo F)</h2>
        <p className="mb-4 text-sm text-slate-500">
          Con cuánta anticipación se avisa por correo que un abono está por vencer.
        </p>
        <Campo
          label="Días de anticipación"
          ayuda="Ej. 3 = se manda el correo cuando falten 3 días o menos para la fecha límite del abono."
        >
          <input
            type="number"
            min="1"
            className="w-40 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={form.dias_anticipacion_alerta_abono ?? ""}
            onChange={(e) => actualizarCampo("dias_anticipacion_alerta_abono", e.target.value)}
            required
          />
        </Campo>
      </section>

      <section className="rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-navy-900">Pruebas de Menú (Módulo B)</h2>
        <p className="mb-4 text-sm text-slate-500">
          Costo por cada asistente que exceda el límite de cortesía (4 personas) en una prueba
          de menú. Se cobra automáticamente al agendar la prueba.
        </p>
        <Campo
          label="Costo por asistente excedente"
          ayuda="Ej. 150.00 = con 6 asistentes (2 de más) se genera un cobro automático de $300.00. Déjalo en 0 para no cobrar nada automático."
        >
          <div className="flex w-48 items-center gap-2">
            <span className="text-sm text-slate-500">$</span>
            <input
              type="number"
              min="0"
              step="0.01"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.costo_extra_por_asistente_prueba_menu ?? ""}
              onChange={(e) => actualizarCampo("costo_extra_por_asistente_prueba_menu", e.target.value)}
              required
            />
          </div>
        </Campo>
      </section>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={guardando}
          className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:opacity-60"
        >
          {guardando ? "Guardando…" : "Guardar cambios"}
        </button>
        {mensaje && (
          <span
            className={`text-sm font-medium ${
              mensaje.tipo === "ok" ? "text-teal-700" : "text-red-600"
            }`}
          >
            {mensaje.texto}
          </span>
        )}
      </div>
    </form>
  );
}
