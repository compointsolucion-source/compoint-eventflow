# COMPOINT EventFlow

Software SaaS para la gestión operativa, logística y financiera de empresas
de banquetes (catering), construido a partir del Plan Maestro de Desarrollo.

## Estructura del proyecto

```
compoint-eventflow/
├── backend/          Django + Django REST Framework
│   ├── eventflow/     Configuración del proyecto (settings, urls)
│   ├── core/          Modelos, admin, serializers, viewsets (Prompt Maestro 1)
│   └── food_cost/     Algoritmo de Explosión de Insumos (Módulo C)
└── frontend/          React + Vite + Tailwind CSS (Prompt Maestro 2)
```

## Backend (Django)

```bash
cd backend
python3 -m venv ../venv        # si no existe ya
source ../venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo     # datos de ejemplo (opcional)
python manage.py createsuperuser  # para entrar a /admin/
python manage.py runserver
```

- API REST en `http://localhost:8000/api/` (eventos, clientes, sedes, recetas,
  insumos, inventario, pruebas de menú, registros de roturas).
- Endpoint especial: `GET /api/eventos/<id>/explosion-insumos/` devuelve la
  lista de compras consolidada (Módulo C: escalado por invitados + merma).
- Admin de Django en `http://localhost:8000/admin/`.
- Por defecto usa SQLite. Para PostgreSQL, define `DATABASE_ENGINE=postgres`
  y las variables `POSTGRES_DB/USER/PASSWORD/HOST/PORT`.

Tests del algoritmo de food cost: `python manage.py test food_cost`.

## Frontend (React + Vite + Tailwind)

```bash
cd frontend
npm install
cp .env.example .env   # ajusta VITE_API_BASE_URL si el backend no está en localhost:8000
npm run dev
```

El Dashboard (`src/Dashboard.jsx`) intenta conectarse al backend real; si no
lo encuentra, muestra datos de demostración simulados para que la pantalla
sea siempre operativa visualmente.

## Despliegue en GitHub + Neon + Render

Este proyecto ya viene listo para ese stack (el mismo patrón que un proyecto
Django típico en Render con Postgres de Neon):

1. **GitHub**: sube esta carpeta a un repo nuevo (o a una carpeta dentro de
   uno existente, ajustando `rootDir` en `render.yaml`).
2. **Neon**: crea un proyecto/base de datos y copia su *connection string*
   (`postgresql://usuario:password@ep-xxx.neon.tech/db?sslmode=require`).
3. **Render**: "New > Blueprint", apunta al repo — Render lee `render.yaml`
   (en la raíz del repo) y crea dos servicios:
   - `compoint-eventflow-backend` (Django + Gunicorn + WhiteNoise para
     estáticos). Variables a completar manualmente en el dashboard de Render:
     - `DATABASE_URL`: el connection string de Neon.
     - `DJANGO_CORS_ALLOWED_ORIGINS`: la URL del frontend una vez desplegado.
   - `compoint-eventflow-frontend` (sitio estático con el build de Vite).
     Variable a completar: `VITE_API_BASE_URL` = URL del backend + `/api`.
4. Tras el primer deploy, corre una vez desde la shell de Render (o vía Job):
   `python manage.py createsuperuser` y, si quieres datos de ejemplo,
   `python manage.py seed_demo`.

El `settings.py` ya soporta `DATABASE_URL` (formato Neon/Render estándar vía
`dj-database-url`), detecta el hostname público de Render para
`ALLOWED_HOSTS`/CSRF, y sirve los estáticos del admin con WhiteNoise sin
depender de un servicio aparte.

## Estado de la implementación

Ver el documento **"estado-implementacion.md"** en el proyecto de Claude
(COMPOINT EventFlow) para el detalle de qué se construyó, decisiones de
diseño y próximos pasos sugeridos (Módulos D, E y F).
