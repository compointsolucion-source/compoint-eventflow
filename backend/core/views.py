import os
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import HttpResponse
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


@api_view(["GET"])
@permission_classes([AllowAny])
def cron_alertas_abonos(request):
    """Endpoint OPCIONAL para automatizar de verdad, todos los días, el
    envío de correos de abonos por vencer (Módulo F) sin que nadie tenga
    que entrar a Finanzas y presionar el botón. Render (plan gratuito) no
    trae cron/scheduler propio, así que si se quiere 100% automático hay
    que apuntar un servicio externo GRATUITO de cron (ej. cron-job.org) una
    vez al día a esta URL con la clave correcta:

        /api/cron/alertas-abonos/?clave=<valor de CRON_ALERTAS_SECRET>

    Es completamente opcional: sin configurar CRON_ALERTAS_SECRET ni el
    cron externo, el botón manual "Enviar alertas pendientes" de Finanzas
    sigue funcionando exactamente igual."""
    secreto_esperado = os.environ.get("CRON_ALERTAS_SECRET")
    if not secreto_esperado or request.query_params.get("clave") != secreto_esperado:
        return Response({"detail": "No autorizado."}, status=403)

    from .services_alertas import enviar_alertas_abonos_por_vencer

    return Response(enviar_alertas_abonos_por_vencer())


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

    @action(detail=False, methods=["get"], url_path="fechas-disponibles")
    def fechas_disponibles(self, request):
        """Módulo B: antes de agendar una prueba de menú, dice si
        `?fecha=YYYY-MM-DD` está disponible para `?evento=<id>` y, si no,
        sugiere las próximas fechas libres."""
        from .services_calendario import fecha_prueba_disponible, sugerir_fechas_disponibles

        evento_id = request.query_params.get("evento")
        fecha_str = request.query_params.get("fecha")
        if not evento_id or not fecha_str:
            return Response(
                {"detail": "Faltan los parámetros ?evento=<id>&fecha=YYYY-MM-DD."}, status=400
            )
        evento = get_object_or_404(Evento, pk=evento_id)
        try:
            fecha = date.fromisoformat(fecha_str)
        except ValueError:
            return Response({"detail": "La fecha debe tener formato YYYY-MM-DD."}, status=400)

        disponible = fecha_prueba_disponible(evento.empresa_id, fecha)
        return Response(
            {
                "fecha": fecha,
                "disponible": disponible,
                "sugerencias": (
                    []
                    if disponible
                    else sugerir_fechas_disponibles(evento.empresa_id, fecha)
                ),
            }
        )


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

    @action(detail=False, methods=["post"], url_path="enviar-alertas-pendientes")
    def enviar_alertas_pendientes(self, request):
        """Botón manual "Enviar alertas pendientes" de Finanzas.jsx (Módulo
        F): dispara el envío de correos para los abonos que están dentro de
        su ventana de alerta. Requiere sesión de staff, igual que el resto
        de la API (ver también `cron_alertas_abonos` para automatizarlo)."""
        from .services_alertas import enviar_alertas_abonos_por_vencer

        return Response(enviar_alertas_abonos_por_vencer())


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

    @action(detail=True, methods=["get"], url_path="cargo-danos-pdf")
    def cargo_danos_pdf(self, request, pk=None):
        """Módulo D: genera el PDF de "Cargo por Daños" a partir de los
        `RegistroRoturas` del evento y marca `pdf_cargo_danos_generado` en
        cada uno. No disponible en la vista `planner` (contiene costos)."""
        from .services_pdf import generar_pdf_cargo_danos

        evento = self.get_object()
        if request.query_params.get("vista") == "planner":
            return Response(
                {"detail": "No autorizado para el portal de Event Planner."},
                status=403,
            )
        try:
            contenido_pdf = generar_pdf_cargo_danos(evento)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=400)

        evento.registros_rotura.update(pdf_cargo_danos_generado=True)

        respuesta = HttpResponse(contenido_pdf, content_type="application/pdf")
        nombre_archivo = f"cargo-danos-{evento.nombre_evento.replace(' ', '-')}.pdf"
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
        return respuesta

    @action(detail=False, methods=["get"], url_path="disponibilidad-fecha")
    def disponibilidad_fecha(self, request):
        """Módulo A: resumen de capacidad para una fecha (`?fecha=YYYY-MM-DD`)
        antes de cotizar un evento nuevo — cuántos eventos ya bloquean esa
        fecha, y cuánta loza/personal ya está comprometida vs. lo disponible."""
        from .models import (
            InventarioEquipo,
            PersonalEventual,
            _calcular_cantidades_equipo,
        )
        from .services_capacidad import eventos_que_bloquean_fecha

        fecha = request.query_params.get("fecha")
        if not fecha:
            return Response({"detail": "Falta el parámetro ?fecha=YYYY-MM-DD."}, status=400)

        eventos_dia = Evento.objects.filter(fecha=fecha).select_related("cliente", "sede")
        empresa_id = eventos_dia.first().empresa_id if eventos_dia.exists() else None
        bloquean = eventos_que_bloquean_fecha(empresa_id, fecha) if empresa_id else []
        ids_bloquean = {e.id for e in bloquean}

        total_equipo = {}
        for evento in bloquean:
            for articulo_id, cantidad in _calcular_cantidades_equipo(evento).items():
                total_equipo[articulo_id] = total_equipo.get(articulo_id, 0) + cantidad
        loza = [
            {
                "articulo": articulo.nombre,
                "requerido": total_equipo.get(articulo.id, 0),
                "disponible": articulo.stock_disponible,
                "saturado": total_equipo.get(articulo.id, 0) > articulo.stock_disponible,
            }
            for articulo in InventarioEquipo.objects.filter(id__in=total_equipo.keys())
        ]

        total_personal = {}
        for evento in bloquean:
            for vacante in evento.vacantes.all():
                total_personal[vacante.rol] = total_personal.get(vacante.rol, 0) + vacante.cantidad_requerida
        personal = [
            {
                "rol": rol,
                "requerido": requerido,
                "disponible": PersonalEventual.objects.filter(
                    empresa_id=empresa_id, rol_principal=rol, activo=True
                ).count(),
            }
            for rol, requerido in total_personal.items()
        ]
        for linea in personal:
            linea["saturado"] = linea["requerido"] > linea["disponible"]

        return Response(
            {
                "fecha": fecha,
                "eventos": [
                    {
                        "id": e.id,
                        "nombre_evento": e.nombre_evento,
                        "estado_semaforo": e.estado_semaforo,
                        "numero_invitados": e.numero_invitados,
                        "vencido": e.vencido,
                        "bloquea_fecha": e.id in ids_bloquean,
                    }
                    for e in eventos_dia
                ],
                "loza": loza,
                "personal": personal,
            }
        )
