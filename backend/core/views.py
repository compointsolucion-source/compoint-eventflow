import os
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from food_cost.services import costo_total_evento, explosion_insumos_evento

from .models import (
    Cliente,
    DetalleListaCarga,
    DetalleMenuEvento,
    EmpresaBanquetera,
    Evento,
    IngredienteReceta,
    InventarioEquipo,
    Insumo,
    ListaCargaEvento,
    PruebaMenu,
    RecetaMaestra,
    RegistroRoturas,
    RequerimientoEquipoTiempo,
    SedeEvento,
)
from .serializers import (
    ClienteSerializer,
    DetalleListaCargaSerializer,
    DetalleMenuEventoSerializer,
    EmpresaBanqueteraSerializer,
    EventoPlannerSerializer,
    EventoSerializer,
    IngredienteRecetaSerializer,
    InsumoSerializer,
    InventarioEquipoSerializer,
    ListaCargaEventoSerializer,
    PruebaMenuSerializer,
    RecetaMaestraPlannerSerializer,
    RecetaMaestraSerializer,
    RegistroRoturasSerializer,
    RequerimientoEquipoTiempoSerializer,
    SedeEventoSerializer,
)


@api_view(["GET"])
@permission_classes([AllowAny])
def estado_servidor(request):
    """Endpoint de diagnóstico (sin datos sensibles): permite confirmar desde
    fuera del navegador -y por lo tanto sin que las reglas de CORS lo bloqueen-
    qué configuración quedó realmente activa en el backend desplegado. Útil
    para verificar que una variable de entorno (ej. DJANGO_CORS_ALLOWED_ORIGINS)
    se guardó y que el servicio reinició con el valor nuevo, sin depender de
    capturas de pantalla del panel de Render."""
    engine = settings.DATABASES["default"]["ENGINE"]
    return Response(
        {
            "debug": settings.DEBUG,
            "cors_allowed_origins": settings.CORS_ALLOWED_ORIGINS,
            "allowed_hosts": settings.ALLOWED_HOSTS,
            "base_de_datos": "postgresql" if "postgresql" in engine else "sqlite3",
        }
    )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def inicializar_produccion(request):
    """Endpoint protegido de un solo uso: siembra datos de ejemplo y crea el
    primer superusuario en un despliegue nuevo (ej. Render + Neon) que no
    tiene acceso a una terminal/shell para correr `manage.py seed_demo` o
    `manage.py createsuperuser` manualmente.

    Requiere la variable de entorno INIT_SECRET configurada en el servicio;
    sin ella, el endpoint siempre rechaza la petición. Se llama visitando
    en el navegador:
        /api/inicializar/?clave=<valor de INIT_SECRET>

    Es idempotente: `seed_demo` no hace nada si ya hay una empresa creada, y
    la creación del superusuario se salta si ya existe alguno. Después de
    usarlo una vez, se recomienda borrar INIT_SECRET del panel de Render
    para dejar el endpoint inutilizable."""
    secreto_esperado = os.environ.get("INIT_SECRET")
    if not secreto_esperado or request.query_params.get("clave") != secreto_esperado:
        return Response({"detail": "No autorizado."}, status=403)

    resultado = {}

    salida = StringIO()
    call_command("seed_demo", stdout=salida)
    resultado["seed_demo"] = salida.getvalue().strip()

    User = get_user_model()
    if User.objects.filter(is_superuser=True).exists():
        resultado["superusuario"] = "ya existía un superusuario, no se creó ninguno nuevo."
    elif not os.environ.get("DJANGO_SUPERUSER_PASSWORD"):
        resultado["superusuario"] = (
            "no se creó: falta configurar DJANGO_SUPERUSER_USERNAME, "
            "DJANGO_SUPERUSER_EMAIL y DJANGO_SUPERUSER_PASSWORD en el "
            "servicio antes de llamar a este endpoint."
        )
    else:
        call_command("createsuperuser", interactive=False)
        resultado["superusuario"] = (
            f"creado: {os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')} "
            "(entra a /admin/ con la contraseña que pusiste en DJANGO_SUPERUSER_PASSWORD)."
        )

    return Response(resultado)


class EmpresaBanqueteraViewSet(viewsets.ModelViewSet):
    queryset = EmpresaBanquetera.objects.all()
    serializer_class = EmpresaBanqueteraSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer


class SedeEventoViewSet(viewsets.ModelViewSet):
    queryset = SedeEvento.objects.all()
    serializer_class = SedeEventoSerializer


class InsumoViewSet(viewsets.ModelViewSet):
    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer


class RecetaMaestraViewSet(viewsets.ModelViewSet):
    """Expone el recetario maestro. Un Event Planner autenticado (vista de
    solo-lectura restringida) recibe la variante sin costos; uso interno
    recibe la variante completa. Ver `?vista=planner` para simular el modo
    restringido mientras no exista autenticación por rol."""

    queryset = RecetaMaestra.objects.all()

    def get_serializer_class(self):
        if self.request.query_params.get("vista") == "planner":
            return RecetaMaestraPlannerSerializer
        return RecetaMaestraSerializer


class IngredienteRecetaViewSet(viewsets.ModelViewSet):
    queryset = IngredienteReceta.objects.all()
    serializer_class = IngredienteRecetaSerializer


class DetalleMenuEventoViewSet(viewsets.ModelViewSet):
    queryset = DetalleMenuEvento.objects.all()
    serializer_class = DetalleMenuEventoSerializer


class PruebaMenuViewSet(viewsets.ModelViewSet):
    queryset = PruebaMenu.objects.all()
    serializer_class = PruebaMenuSerializer


class InventarioEquipoViewSet(viewsets.ModelViewSet):
    queryset = InventarioEquipo.objects.all()
    serializer_class = InventarioEquipoSerializer


class RegistroRoturasViewSet(viewsets.ModelViewSet):
    queryset = RegistroRoturas.objects.all()
    serializer_class = RegistroRoturasSerializer


class RequerimientoEquipoTiempoViewSet(viewsets.ModelViewSet):
    queryset = RequerimientoEquipoTiempo.objects.select_related("articulo").all()
    serializer_class = RequerimientoEquipoTiempoSerializer


class ListaCargaEventoViewSet(viewsets.ModelViewSet):
    """Módulo D: listas de carga por evento, con el desglose de equipo ya
    calculado (`cantidad_requerida` y `cantidad_a_cargar` con el +10% de
    rotura aplicado)."""

    queryset = ListaCargaEvento.objects.select_related("evento").prefetch_related(
        "detalles__articulo"
    ).all()
    serializer_class = ListaCargaEventoSerializer


class EventoViewSet(viewsets.ModelViewSet):
    """Expone la Agenda Semáforo. `?vista=planner` simula el portal
    colaborativo restringido (sin costos/márgenes) mientras no exista
    autenticación por rol."""

    queryset = Evento.objects.select_related("cliente", "sede").all()

    def get_serializer_class(self):
        if self.request.query_params.get("vista") == "planner":
            return EventoPlannerSerializer
        return EventoSerializer

    @action(detail=True, methods=["get"], url_path="explosion-insumos")
    def explosion_insumos(self, request, pk=None):
        """Algoritmo de Explosión de Insumos (Módulo C): lista de compras
        consolidada para este evento, escalada por invitados y ajustada por
        merma. No disponible en la vista `planner` (contiene costos)."""
        evento = self.get_object()
        if request.query_params.get("vista") == "planner":
            return Response(
                {"detail": "No autorizado para el portal de Event Planner."},
                status=403,
            )
        lineas = explosion_insumos_evento(evento)
        return Response(
            {
                "evento_id": evento.id,
                "nombre_evento": evento.nombre_evento,
                "numero_invitados": evento.numero_invitados,
                "lineas": [l.to_dict() for l in lineas],
                "costo_total_insumos": str(costo_total_evento(evento)),
            }
        )
