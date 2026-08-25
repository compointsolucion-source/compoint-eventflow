"""
Serializers de Django REST Framework para el core de COMPOINT EventFlow.

Nota de seguridad (Módulo A): el Event Planner NO debe tener acceso a los
costos de insumos ni a los márgenes de ganancia de la banquetera. Por eso
existen dos variantes de serializer para `RecetaMaestra` / `DetalleMenuEvento`:
la variante completa (uso interno/admin) y la variante "planner" que oculta
`costo_estimado` y cualquier dato financiero. La vista decide cuál usar según
el rol de quien consulta (ver `views.py`).
"""

from rest_framework import serializers

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


class EmpresaBanqueteraSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmpresaBanquetera
        fields = "__all__"


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = "__all__"


class SedeEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SedeEvento
        fields = "__all__"


class InsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = "__all__"


class IngredienteRecetaSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = IngredienteReceta
        fields = ["id", "receta", "insumo", "insumo_nombre", "cantidad", "unidad_medida"]


class RecetaMaestraSerializer(serializers.ModelSerializer):
    """Serializer completo (uso interno): incluye costo_estimado."""

    ingredientes = IngredienteRecetaSerializer(many=True, read_only=True)

    class Meta:
        model = RecetaMaestra
        fields = [
            "id", "empresa", "nombre", "tiempo_menu", "porciones_base",
            "costo_estimado", "ingredientes",
        ]


class RecetaMaestraPlannerSerializer(serializers.ModelSerializer):
    """Serializer restringido para el portal del Event Planner: sin costos."""

    class Meta:
        model = RecetaMaestra
        fields = ["id", "nombre", "tiempo_menu", "porciones_base"]


class DetalleMenuEventoSerializer(serializers.ModelSerializer):
    receta_detalle = RecetaMaestraSerializer(source="receta", read_only=True)

    class Meta:
        model = DetalleMenuEvento
        fields = ["id", "evento", "receta", "receta_detalle", "notas_personalizacion"]


class PruebaMenuSerializer(serializers.ModelSerializer):
    excede_limite_cortesia = serializers.BooleanField(read_only=True)

    class Meta:
        model = PruebaMenu
        fields = "__all__"


class PruebaMenuPlannerSerializer(serializers.ModelSerializer):
    """Variante restringida para el Portal del Event Planner: sin
    `cobro_adicional_generado` (dato financiero)."""

    excede_limite_cortesia = serializers.BooleanField(read_only=True)

    class Meta:
        model = PruebaMenu
        fields = ["id", "fecha_prueba", "asistentes", "notas_chef", "aprobado", "excede_limite_cortesia"]


class InventarioEquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventarioEquipo
        fields = "__all__"


class RegistroRoturasSerializer(serializers.ModelSerializer):
    """Registro de rotura del Módulo D. `costo_reposicion` nunca se captura
    a mano: el modelo lo recalcula solo (cantidad_rota x costo de
    reposición unitario del artículo) al guardar, así que aquí es de solo
    lectura para evitar inconsistencias entre lo que se muestra y lo que
    realmente se guarda."""

    articulo_nombre = serializers.CharField(source="articulo.nombre", read_only=True)
    evento_nombre = serializers.CharField(source="evento.nombre_evento", read_only=True)

    class Meta:
        model = RegistroRoturas
        fields = [
            "id", "evento", "evento_nombre", "articulo", "articulo_nombre",
            "cantidad_rota", "costo_reposicion", "registrado_por",
            "fecha_registro", "pdf_cargo_danos_generado",
        ]
        read_only_fields = ["costo_reposicion", "fecha_registro", "pdf_cargo_danos_generado"]


class RequerimientoEquipoTiempoSerializer(serializers.ModelSerializer):
    articulo_nombre = serializers.CharField(source="articulo.nombre", read_only=True)

    class Meta:
        model = RequerimientoEquipoTiempo
        fields = [
            "id", "empresa", "tiempo_menu", "articulo", "articulo_nombre",
            "cantidad_por_invitado",
        ]


class DetalleListaCargaSerializer(serializers.ModelSerializer):
    """Una línea de la lista de carga (Módulo D): incluye tanto la cantidad
    requerida para atender a los invitados como `cantidad_a_cargar`, que ya
    trae aplicado el Factor +10% de Rotura."""

    articulo_nombre = serializers.CharField(source="articulo.nombre", read_only=True)
    articulo_tipo = serializers.CharField(source="articulo.tipo", read_only=True)
    cantidad_a_cargar = serializers.IntegerField(read_only=True)

    class Meta:
        model = DetalleListaCarga
        fields = [
            "id", "lista_carga", "articulo", "articulo_nombre", "articulo_tipo",
            "cantidad_requerida", "cantidad_a_cargar", "surtido",
        ]


class ListaCargaEventoSerializer(serializers.ModelSerializer):
    evento_nombre = serializers.CharField(source="evento.nombre_evento", read_only=True)
    fecha_evento = serializers.DateField(source="evento.fecha", read_only=True)
    detalles = DetalleListaCargaSerializer(many=True, read_only=True)

    class Meta:
        model = ListaCargaEvento
        fields = [
            "id", "evento", "evento_nombre", "fecha_evento", "generada_en",
            "actualizada_en", "conteo_retorno_completado", "detalles",
        ]


class PersonalEventualSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalEventual
        fields = [
            "id", "empresa", "nombre", "telefono", "email",
            "rol_principal", "activo",
        ]


class CheckInSerializer(serializers.ModelSerializer):
    asistio = serializers.BooleanField(read_only=True)

    class Meta:
        model = CheckIn
        fields = [
            "id", "postulacion", "codigo_verificacion", "hora_checkin",
            "confirmado_por", "asistio",
        ]
        read_only_fields = ["codigo_verificacion"]


class PostulacionSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(source="personal.nombre", read_only=True)
    personal_telefono = serializers.CharField(source="personal.telefono", read_only=True)
    check_in = CheckInSerializer(read_only=True)

    class Meta:
        model = Postulacion
        fields = [
            "id", "vacante", "personal", "personal_nombre", "personal_telefono",
            "estado", "postulado_en", "check_in",
        ]


class VacanteEventoSerializer(serializers.ModelSerializer):
    """Bolsa de Trabajo (Módulo E): una vacante de un evento, con sus
    postulaciones (y el check-in de cada una, si ya fue aceptada)."""

    evento_nombre = serializers.CharField(source="evento.nombre_evento", read_only=True)
    fecha_evento = serializers.DateField(source="evento.fecha", read_only=True)
    cantidad_aceptada = serializers.IntegerField(read_only=True)
    cubierta = serializers.BooleanField(read_only=True)
    postulaciones = PostulacionSerializer(many=True, read_only=True)

    class Meta:
        model = VacanteEvento
        fields = [
            "id", "evento", "evento_nombre", "fecha_evento", "rol",
            "cantidad_requerida", "cantidad_aceptada", "cubierta",
            "tarifa_por_turno", "notas", "postulaciones",
        ]


class AbonoEventoSerializer(serializers.ModelSerializer):
    vencido = serializers.BooleanField(read_only=True)

    class Meta:
        model = AbonoEvento
        fields = [
            "id", "esquema", "tipo", "porcentaje", "monto", "fecha_limite",
            "pagado", "fecha_pago", "vencido",
        ]


class EsquemaPagoEventoSerializer(serializers.ModelSerializer):
    """Esquema de Cobro Automatizado 50/30/20 del Módulo F, con sus abonos
    ya generados."""

    evento_nombre = serializers.CharField(source="evento.nombre_evento", read_only=True)
    fecha_evento = serializers.DateField(source="evento.fecha", read_only=True)
    abonos = AbonoEventoSerializer(many=True, read_only=True)

    class Meta:
        model = EsquemaPagoEvento
        fields = [
            "id", "evento", "evento_nombre", "fecha_evento", "monto_total",
            "generado_en", "actualizado_en", "abonos",
        ]


class ConfiguracionCotizadorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionCotizador
        fields = [
            "id", "empresa", "costo_base_por_persona",
            "costos_fijos_transporte_personal",
        ]


class EventoSerializer(serializers.ModelSerializer):
    """Serializer completo (uso interno/admin): visible para la banquetera."""

    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    sede_nombre = serializers.CharField(source="sede.nombre", read_only=True)
    estado_semaforo_display = serializers.CharField(
        source="get_estado_semaforo_display", read_only=True
    )

    class Meta:
        model = Evento
        fields = [
            "id", "empresa", "nombre_evento", "fecha", "numero_invitados",
            "estado_semaforo", "estado_semaforo_display", "tipo_cliente",
            "cliente", "cliente_nombre", "sede", "sede_nombre",
            "fecha_cotizacion", "fecha_vencimiento_prospecto",
            "fecha_limite_anticipo", "fecha_registro_anticipo",
            "autorizado_proveedor_externo", "creado_en", "actualizado_en",
        ]


class EventoPlannerSerializer(serializers.ModelSerializer):
    """Serializer restringido para el portal colaborativo del Event Planner:
    sin costos ni márgenes de ganancia (solo cronograma y datos logísticos)."""

    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    sede_nombre = serializers.CharField(source="sede.nombre", read_only=True)

    class Meta:
        model = Evento
        fields = [
            "id", "nombre_evento", "fecha", "numero_invitados",
            "estado_semaforo", "cliente_nombre", "sede_nombre",
        ]


class DetalleMenuEventoPlannerSerializer(serializers.ModelSerializer):
    """Un plato del menú de un evento, para el Portal del Event Planner: solo
    el nombre/tiempo de la receta, sin `costo_estimado`."""

    receta_detalle = RecetaMaestraPlannerSerializer(source="receta", read_only=True)

    class Meta:
        model = DetalleMenuEvento
        fields = ["id", "receta_detalle", "notas_personalizacion"]


class EventoPlannerDetalleSerializer(serializers.ModelSerializer):
    """Payload completo del Portal del Event Planner (Módulo A): cronograma
    de un solo evento, accesible con el link único de `Evento.token_planner`
    sin necesitar cuenta ni contraseña. Nunca incluye costos, márgenes,
    cotización ni datos de otros eventos de la banquetera."""

    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    sede_nombre = serializers.CharField(source="sede.nombre", read_only=True)
    sede_direccion = serializers.CharField(source="sede.direccion", read_only=True)
    estado_semaforo_display = serializers.CharField(
        source="get_estado_semaforo_display", read_only=True
    )
    detalle_menu = DetalleMenuEventoPlannerSerializer(many=True, read_only=True)
    pruebas_menu = PruebaMenuPlannerSerializer(many=True, read_only=True)

    class Meta:
        model = Evento
        fields = [
            "id", "nombre_evento", "fecha", "numero_invitados",
            "estado_semaforo", "estado_semaforo_display",
            "cliente_nombre", "sede_nombre", "sede_direccion",
            "detalle_menu", "pruebas_menu",
        ]
