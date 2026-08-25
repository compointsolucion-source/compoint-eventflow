import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "./api.js";
import Recetario from "./Recetario.jsx";
import Bodega from "./Bodega.jsx";

/**
 * Dashboard principal de COMPOINT EventFlow.
 * Implementa el "PROMPT MAESTRO 2" del Plan Maestro: sidebar con logo +
 * slogan, 3 tarjetas KPI, y el componente "Agenda Semáforo". El menú
 * lateral cambia la vista mostrada en el área principal: Recetario y
 * Bodega ya están construidos con datos reales del backend; Personal
 * Eventual y Finanzas todavía no tienen modelos de datos (Módulos E y F
 * del plan maestro), así que muestran un aviso de "en construcción".
 *
 * El componente intenta traer datos reales del backend Django
 * (GET /api/eventos/) y si no está disponible (ej. corriendo solo el
 * frontend, o el backend apagado) cae de forma transparente a datos de
 * demostración simulados con useState, para que la pantalla sea
 * completamente operativa a nivel visual en cualquier escenario.
 */

const EVENTOS_DEMO = [
  {
    id: 1,
    nombre_evento: "Boda Ramírez-González",
    fecha: "2026-09-15",
    numero_invitados: 280,
    estado_semaforo: "CONFIRMADO",
    tipo_cliente: "DIRECTO",
    sede_nombre: "Hacienda Los Encinos",
  },
  {
    id: 2,
    nombre_evento: "XV Años Sofía Martínez",
    fecha: "2026-09-30",
    numero_invitados: 150,
    estado_semaforo: "APARTADO",
    tipo_cliente: "PLANNER",
    sede_nombre: "Jardín Villa Toscana",
  },
  {
    id: 3,
    nombre_evento: "Convención Anual Grupo Delta",
    fecha: "2026-10-20",
    numero_invitados: 120,
    estado_semaforo: "PROSPECTO",
    tipo_cliente: "DIRECTO",
    sede_nombre: "Salón Corporativo Delta Tower",
  },
];

const SEMAFORO_STYLES = {
  PROSPECTO: {
    label: "Prospecto",
    emoji: "🟡",
    badge: "bg-amber-100 text-amber-800 border border-amber-300",
    bar: "bg-amber-400",
  },
  APARTADO: {
    label: "Apartado",
    emoji: "🟠",
    badge: "bg-orange-100 text-orange-800 border border-orange-300",
    bar: "bg-orange-500",
  },
  CONFIRMADO: {
    label: "Confirmado",
    emoji: "🔴",
    badge: "bg-red-100 text-red-800 border border-red-300",
    bar: "bg-red-500",
  },
};

const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: IconGrid },
  { key: "agenda", label: "Agenda de Eventos", icon: IconCalendar },
  { key: "recetario", label: "Recetario / Food Cost", icon: IconChefHat },
  { key: "bodega", label: "Bodega e Inventario", icon: IconBox },
  { key: "staffing", label: "Personal Eventual", icon: IconUsers },
  { key: "finanzas", label: "Finanzas", icon: IconWallet },
];

function IconGrid(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
      <rect x="13" y="13" width="8" height="8" rx="1.5" />
    </svg>
  );
}
function IconCalendar(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 9.5h18M8 3v4M16 3v4" strokeLinecap="round" />
    </svg>
  );
}
function IconChefHat(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <path d="M6 10a4 4 0 1 1 7-2.6A4 4 0 0 1 18 10c1.3.5 2 1.7 2 3 0 1.9-1.6 3-3.5 3H7.5C5.6 16 4 14.9 4 13c0-1.3.7-2.5 2-3Z" />
      <path d="M7 16v4h10v-4" />
    </svg>
  );
}
function IconBox(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <path d="m3 8 9-5 9 5-9 5-9-5Z" />
      <path d="M3 8v8l9 5 9-5V8M12 13v8" />
    </svg>
  );
}
function IconUsers(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <circle cx="17.5" cy="9" r="2.5" />
      <path d="M15 20a5.5 5.5 0 0 1 7-5.2" />
    </svg>
  );
}
function IconWallet(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18" />
      <circle cx="16" cy="14" r="1.4" fill="currentColor" stroke="none" />
    </svg>
  );
}
function IconAlert(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <path d="M12 3 2 20h20L12 3Z" strokeLinejoin="round" />
      <path d="M12 10v4" strokeLinecap="round" />
      <circle cx="12" cy="17" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}
function IconCheck(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.3 2.3L16 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconFork(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" stroke="currentColor" {...props}>
      <path d="M8 3v6a2 2 0 1 1-4 0V3M6 9v12M14 3v18M18 3c0 4-4 4-4 8" strokeLinecap="round" />
    </svg>
  );
}

function KpiCard({ icon: Icon, label, value, hint, tone = "navy" }) {
  const toneStyles = {
    navy: "bg-navy-900 text-white",
    teal: "bg-teal-500 text-navy-950",
    alert: "bg-white text-navy-900 border-2 border-amber-400",
  };
  return (
    <div className={`rounded-2xl p-5 shadow-sm ${toneStyles[tone]} flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <span
          className={`inline-flex h-10 w-10 items-center justify-center rounded-xl ${
            tone === "navy" ? "bg-white/10" : tone === "teal" ? "bg-navy-950/10" : "bg-amber-50"
          }`}
        >
          <Icon className={`h-5 w-5 ${tone === "alert" ? "text-amber-500" : ""}`} />
        </span>
      </div>
      <div>
        <p className="text-3xl font-semibold tracking-tight">{value}</p>
        <p className={`text-sm ${tone === "navy" ? "text-teal-300" : "opacity-70"}`}>{label}</p>
      </div>
      {hint && <p className="text-xs opacity-70">{hint}</p>}
    </div>
  );
}

function EventoRow({ evento }) {
  const estilo = SEMAFORO_STYLES[evento.estado_semaforo] ?? SEMAFORO_STYLES.PROSPECTO;
  const esPlanner = evento.tipo_cliente === "PLANNER";
  const fecha = new Date(evento.fecha + "T00:00:00");
  const fechaFmt = fecha.toLocaleDateString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  return (
    <li className="flex items-stretch gap-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <span className={`w-1.5 shrink-0 ${estilo.bar}`} aria-hidden="true" />
      <div className="flex flex-1 flex-wrap items-center justify-between gap-3 p-4">
        <div className="min-w-[200px]">
          <p className="font-semibold text-navy-900">{evento.nombre_evento}</p>
          <p className="text-sm text-slate-500">
            {fechaFmt} · {evento.sede_nombre}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${estilo.badge}`}
          >
            {estilo.emoji} {estilo.label}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${
              esPlanner
                ? "bg-navy-900/5 text-navy-900 border border-navy-900/10"
                : "bg-teal-500/10 text-teal-700 border border-teal-500/20"
            }`}
          >
            {esPlanner ? "Con Event Planner" : "Cliente Directo"}
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            {evento.numero_invitados} invitados
          </span>
        </div>
      </div>
    </li>
  );
}

function VistaProximamente({ label }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-white/60 px-6 py-16 text-center">
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-navy-900/5 text-navy-900">
        <IconAlert className="h-6 w-6" />
      </span>
      <h2 className="text-lg font-semibold text-navy-900">{label} — en construcción</h2>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        Este módulo todavía no tiene modelos de datos ni pantalla propia. Cuando quieras,
        pídeme que lo diseñemos y lo construyo igual que Recetario y Bodega.
      </p>
    </div>
  );
}

function VistaResumen({ kpis, eventosOrdenados }) {
  return (
    <>
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-navy-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Vista general de operación de hoy</p>
        </div>
      </header>

      {/* KPIs */}
      <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard
          icon={IconCheck}
          label="Eventos Confirmados"
          value={kpis.confirmados}
          hint="Anticipo registrado, inventario bloqueado"
          tone="navy"
        />
        <KpiCard
          icon={IconFork}
          label="Pruebas de Menú esta Semana"
          value={kpis.pruebasSemana}
          hint="Fichas de degustación agendadas"
          tone="teal"
        />
        <KpiCard
          icon={IconAlert}
          label="Alerta de Inventario (Límite de Rotura)"
          value={kpis.alertaInventario ? "Atención" : "Sin alertas"}
          hint="Factor +10% de rotura sobre loza/cristalería"
          tone="alert"
        />
      </section>

      {/* Agenda Semáforo */}
      <section className="rounded-2xl bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-navy-900">Agenda Semáforo</h2>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span className="flex items-center gap-1">🟡 Prospecto</span>
            <span className="flex items-center gap-1">🟠 Apartado</span>
            <span className="flex items-center gap-1">🔴 Confirmado</span>
          </div>
        </div>
        <ul className="flex flex-col gap-3">
          {eventosOrdenados.map((evento) => (
            <EventoRow key={evento.id} evento={evento} />
          ))}
        </ul>
      </section>
    </>
  );
}

export default function Dashboard() {
  const [eventos, setEventos] = useState(EVENTOS_DEMO);
  const [fuente, setFuente] = useState("demo"); // "demo" | "api-vacio" | "api"
  const [activeNav, setActiveNav] = useState("dashboard");

  useEffect(() => {
    let cancelado = false;
    fetch(`${API_BASE}/eventos/`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => {
        if (cancelado) return;
        const lista = Array.isArray(data) ? data : data.results;
        if (!Array.isArray(lista)) return;
        // La conexión al backend funcionó (sea que haya o no eventos
        // capturados todavía); "demo" solo debe reflejar que el fetch
        // falló, no que la base de datos real esté vacía.
        if (lista.length) {
          setEventos(lista);
          setFuente("api");
        } else {
          setFuente("api-vacio");
        }
      })
      .catch(() => {
        // Backend no disponible: seguimos mostrando los datos de demo.
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const kpis = useMemo(() => {
    const confirmados = eventos.filter((e) => e.estado_semaforo === "CONFIRMADO").length;
    // "Pruebas de Menú esta Semana" no viene en el listado ligero de eventos;
    // se muestra un valor ilustrativo mientras se conecta el endpoint de
    // PruebaMenu al dashboard.
    const pruebasSemana = 3;
    const alertaInventario = eventos.some((e) => e.numero_invitados >= 250);
    return { confirmados, pruebasSemana, alertaInventario };
  }, [eventos]);

  const eventosOrdenados = useMemo(
    () => [...eventos].sort((a, b) => new Date(a.fecha) - new Date(b.fecha)),
    [eventos]
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 lg:flex">
      {/* Sidebar */}
      <aside className="flex shrink-0 flex-col justify-between bg-navy-950 px-5 py-6 text-white lg:w-72">
        <div>
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-teal-400 to-teal-500 font-bold text-navy-950">
              CE
            </span>
            <div>
              <p className="text-lg font-semibold leading-tight">COMPOINT</p>
              <p className="-mt-1 text-lg font-semibold leading-tight text-teal-400">EventFlow</p>
            </div>
          </div>
          <p className="mt-4 text-xs italic leading-relaxed text-slate-400">
            "Sincronía total desde el almacén hasta la mesa del invitado."
          </p>

          <nav className="mt-8 flex flex-col gap-1">
            {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setActiveNav(key)}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  activeNav === key
                    ? "bg-white/10 text-white"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon className="h-4.5 w-4.5 shrink-0" />
                {label}
              </button>
            ))}
          </nav>
        </div>

        <div className="rounded-xl bg-white/5 p-4 text-xs text-slate-400">
          <p className="font-medium text-slate-200">Banquetes Sincronía</p>
          <p className="mt-1">
            Datos:{" "}
            <span
              className={
                fuente === "demo" ? "text-amber-400" : "text-teal-400"
              }
            >
              {fuente === "api"
                ? "conectado al backend"
                : fuente === "api-vacio"
                ? "conectado al backend (sin eventos aún)"
                : "demostración (offline)"}
            </span>
          </p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 px-6 py-8 lg:px-10">
        {(activeNav === "dashboard" || activeNav === "agenda") && (
          <VistaResumen kpis={kpis} eventosOrdenados={eventosOrdenados} />
        )}
        {activeNav === "recetario" && <Recetario />}
        {activeNav === "bodega" && <Bodega />}
        {activeNav === "staffing" && <VistaProximamente label="Personal Eventual" />}
        {activeNav === "finanzas" && <VistaProximamente label="Finanzas" />}
      </main>
    </div>
  );
}
