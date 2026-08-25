import os
from io import StringIO

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from food_cost.services import costo_total_evento, cotizar_evento, explosion_insumos_evento

from .models import (
    AbonoEvento,
    CheckIn,
    Cliente,
    ConfiguracionCotizador,
    DetalleListaCarga,
    DetalleMenuEvento,
    EmpresaBanquetera,
    EsquemaPagoEvento,
    Evento,
    IngredienteReceta,
    InventarioEquipo,
    Insumo,
    ListaCargaEvento,
    PersonalEventual,
    Postulacion,
    PruebaMenu,
    RecetaMaestra,
    RegistroRoturas,
    RequerimientoEquipoTiempo,
    SedeEvento,
    VacanteEvento,
)
from .serializers import (
    AbonoEventoSerializer,
    CheckInSerializer,
    ClienteSerializer,
    ConfiguracionCotizadorSerializer,
    DetalleListaCargaSerializer,
    DetalleMenuEventoSerializer,
    EmpresaBanqueteraSerializer,
    EsquemaPagoEventoSerializer,
    EventoPlannerDetalleSerializer,
    EventoPlannerSerializer,
    EventoSerializer,
    IngredienteRecetaSerializer,
    InsumoSerializer,
    InventarioEquipoSerializer,
    ListaCargaEventoSerializer,
    PersonalEventualSerializer,
    PostulacionSerializer,
    PruebaMenuSerializer,
    RecetaMaestraPlannerSerializer,
    RecetaMaestraSerializer,
    RegistroRoturasSerializer,
    RequerimientoEquipoTiempoSerializer,
    SedeEventoSerializer,
    VacanteEventoSerializer,
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


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """Login del equipo interno de la banquetera (Módulo A: autenticación y
    roles). Recibe usuario y contraseña, regresa un token que el frontend
    guarda y manda en cada petición como `Authorization: Token <token>`.

    No hay registro público: las cuentas del equipo se crean desde
    `/admin/` (sección Usuarios) o con `manage.py createsuperuser`. El
    Event Planner NO usa este login — entra por su link único de
    `PlannerEventoView`, sin cuenta ni contraseña."""
    username = request.data.get("username", "")
    password = request.data.get("password", "")
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return Response({"detail": "Usuario o contraseña incorrectos."}, status=401)
    token, _creado = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "username": user.username})


class PlannerEventoView(APIView):
    """Portal del Event Planner (Módulo A): acceso de solo lectura a UN
    evento mediante su link único (`Evento.token_planner`), sin necesitar
    cuenta ni contraseña del equipo interno. El serializer usado
    (`EventoPlannerDetalleSerializer`) nunca incluye costos, márgenes,
    cotización ni datos de otros eventos de la banquetera."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        evento = get_object_or_404(Evento, token_planner=token)
        return Response(EventoPlannerDetalleSerializer(evento).data)


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
    rotura aplicado). Soporta PATCH para que, desde Bodega, el Capitán de
    Meseros marque `conteo_retorno_completado` al terminar el evento."""

    queryset = ListaCargaEvento.objects.select_related("evento").prefetch_related(
        "detalles__articulo"
    ).all()
    serializer_class = ListaCargaEventoSerializer


class DetalleListaCargaViewSet(viewsets.ModelViewSet):
    """Una línea de una lista de carga. Se usa desde Bodega solo para marcar
    `surtido` (ya se cargó al camión) con un PATCH; las líneas en sí se
    generan automáticamente desde `ListaCargaEvento.generar_o_actualizar_detalles`,
    no se crean a mano."""

    queryset = DetalleListaCarga.objects.select_related(
        "lista_carga__evento", "articulo"
    ).all()
    serializer_class = DetalleListaCargaSerializer


class PersonalEventualViewSet(viewsets.ModelViewSet):
    """Módulo E: personal eventual registrado (meseros, bartenders,
    garroteros, capitanes) disponible para postularse a vacantes."""

    queryset = PersonalEventual.objects.all()
    serializer_class = PersonalEventualSerializer


class VacanteEventoViewSet(viewsets.ModelViewSet):
    """Bolsa de Trabajo (Módulo E): vacantes por evento, con sus
    postulaciones y el check-in de cada una ya incluidos."""

    queryset = VacanteEvento.objects.select_related("evento").prefetch_related(
        "postulaciones__personal", "postulaciones__check_in"
    ).all()
    serializer_class = VacanteEventoSerializer


class PostulacionViewSet(viewsets.ModelViewSet):
    queryset = Postulacion.objects.select_related("personal", "vacante", "check_in").all()
    serializer_class = PostulacionSerializer

    @action(detail=True, methods=["post"], url_path="confirmar-checkin")
    def confirmar_checkin(self, request, pk=None):
        """Confirma la asistencia del trabajador (equivalente al Capitán de
        Meseros escaneando su código/QR el día del evento)."""
        postulacion = self.get_object()
        check_in, _creado = CheckIn.objects.get_or_create(postulacion=postulacion)
        check_in.confirmar(confirmado_por=request.data.get("confirmado_por", ""))
        return Response(CheckInSerializer(check_in).data)


class CheckInViewSet(viewsets.ModelViewSet):
    queryset = CheckIn.objects.select_related("postulacion__personal").all()
    serializer_class = CheckInSerializer


class ConfiguracionCotizadorViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionCotizador.objects.all()
    serializer_class = ConfiguracionCotizadorSerializer


class EsquemaPagoEventoViewSet(viewsets.ModelViewSet):
    """Módulo F: esquema de cobro 50/30/20 por evento, con sus abonos ya
    calculados (montos y fechas límite)."""

    queryset = EsquemaPagoEvento.objects.select_related("evento").prefetch_related(
        "abonos"
    ).all()
    serializer_class = EsquemaPagoEventoSerializer


class AbonoEventoViewSet(viewsets.ModelViewSet):
    queryset = AbonoEvento.objects.select_related("esquema__evento").all()
    serializer_class = AbonoEventoSerializer

    @action(detail=True, methods=["post"], url_path="marcar-pagado")
    def marcar_pagado(self, request, pk=None):
        abono = self.get_object()
        abono.marcar_pagado()
        return Response(AbonoEventoSerializer(abono).data)


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

    @action(detail=True, methods=["get"], url_path="cotizacion")
    def cotizacion(self, request, pk=None):
        """Cotizador por Volumen (Módulo F): precio por persona y total del
        evento, repartiendo los costos fijos entre el número de invitados.
        No disponible en la vista `planner` (contiene costos/márgenes)."""
        evento = self.get_object()
        if request.query_params.get("vista") == "planner":
            return Response(
                {"detail": "No autorizado para el portal de Event Planner."},
                status=403,
            )
        try:
            return Response(cotizar_evento(evento))
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=400)
