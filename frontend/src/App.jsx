import { useState } from "react";
import Dashboard from "./Dashboard.jsx";
import Login from "./Login.jsx";
import PlannerView from "./PlannerView.jsx";
import { getToken } from "./api.js";

// El Portal del Event Planner (Módulo A) vive en /planner/<token>/, sin
// necesitar sesión del equipo interno: se detecta por la URL antes que
// nada, incluso si ya hay una sesión guardada en este navegador.
const coincidenciaPlanner = window.location.pathname.match(/^\/planner\/([^/]+)\/?$/);

function App() {
  const [sesionActiva, setSesionActiva] = useState(!!getToken());

  if (coincidenciaPlanner) {
    return <PlannerView token={coincidenciaPlanner[1]} />;
  }

  if (!sesionActiva) {
    return <Login onIngreso={() => setSesionActiva(true)} />;
  }

  return <Dashboard onCerrarSesion={() => setSesionActiva(false)} />;
}

export default App;
