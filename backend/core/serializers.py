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


class InventarioEquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventarioEquipo
        fields = "__all__"


class RegistroRoturasSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroRoturas
        fields = "__all__"


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
