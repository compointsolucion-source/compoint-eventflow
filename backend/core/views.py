from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from food_cost.services import costo_total_evento, explosion_insumos_evento

from .models import (
    Cliente,
    DetalleMenuEvento,
    EmpresaBanquetera,
    Evento,
    IngredienteReceta,
    InventarioEquipo,
    Insumo,
    PruebaMenu,
    RecetaMaestra,
    RegistroRoturas,
    SedeEvento,
)
from .serializers import (
    ClienteSerializer,
    DetalleMenuEventoSerializer,
    EmpresaBanqueteraSerializer,
    EventoPlannerSerializer,
    EventoSerializer,
    IngredienteRecetaSerializer,
    InsumoSerializer,
    InventarioEquipoSerializer,
    PruebaMenuSerializer,
    RecetaMaestraPlannerSerializer,
    RecetaMaestraSerializer,
    RegistroRoturasSerializer,
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
