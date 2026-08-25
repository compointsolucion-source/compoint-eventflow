"""
Modelos centrales de COMPOINT EventFlow.

Corresponde al "PROMPT MAESTRO 1: Base de Datos Relacional" del Plan Maestro.
Se implementan las 10 tablas solicitadas, más un modelo auxiliar `Insumo`
(los ingredientes/insumos en sí) que es necesario para que `IngredienteReceta`
pueda relacionar Recetas <-> Insumos como pide el punto 6 del prompt.

Todas las entidades de negocio cuelgan de `EmpresaBanquetera` para que el
SaaS sea multi-tenant: cada empresa de banquetes ve únicamente sus propios
datos (clientes, recetas, inventario, eventos, etc.).
"""

import math
from decimal import ROUND_CEILING, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class TiempoMenu(models.TextChoices):
    """Tiempos de menú compartidos por `RecetaMaestra` y
    `RequerimientoEquipoTiempo`, para poder cruzar qué recetas contrató un
    evento con qué equipo de bodega (loza/cristalería/cubertería) requiere
    cada tiempo (Módulo D: Listas de Carga Automatizadas)."""

    ENTRADA = "ENTRADA", "Entrada"
    FUERTE = "FUERTE", "Plato fuerte"
    POSTRE = "POSTRE", "Postre"
    BEBIDA = "BEBIDA", "Bebida"
    BOTANA = "BOTANA", "Botana / Coctel"


# ---------------------------------------------------------------------------
# 1. EmpresaBanquetera
# ---------------------------------------------------------------------------
class EmpresaBanquetera(models.Model):
    """Cuenta principal del SaaS: cada empresa de banquetes que contrata
    COMPOINT EventFlow. Es el "tenant" raíz del que cuelgan clientes,
    recetas, inventario y eventos."""

    nombre_comercial = models.CharField(max_length=150)
    razon_social = models.CharField(max_length=200, blank=True)
    rfc = models.CharField(
        "RFC / identificación fiscal", max_length=20, blank=True
    )
    telefono_contacto = models.CharField(max_length=20, blank=True)
    email_contacto = models.EmailField(blank=True)
    direccion_bodega_central = models.CharField(
        "Dirección de la bodega/comisariato central", max_length=255, blank=True
    )
    activa = models.BooleanField(default=True)
    fecha_alta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Empresa Banquetera"
        verbose_name_plural = "Empresas Banqueteras"
        ordering = ["nombre_comercial"]

    def __str__(self):
        return self.nombre_comercial


# ---------------------------------------------------------------------------
# 2. Cliente
# ---------------------------------------------------------------------------
class Cliente(models.Model):
    """Cliente final de una empresa banquetera. Puede llegar acompañado de
    un Event Planner (tipo PLANNER) o contratar directamente (tipo DIRECTO),
    lo cual determina el flujo del Módulo A (portal colaborativo vs.
    "Modo Asistente")."""

    class TipoCliente(models.TextChoices):
        PLANNER = "PLANNER", "Event Planner"
        DIRECTO = "DIRECTO", "Cliente Directo"

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="clientes"
    )
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    tipo = models.CharField(
        max_length=10, choices=TipoCliente.choices, default=TipoCliente.DIRECTO
    )
    # Cuando tipo == PLANNER, este campo identifica a la agencia/planner
    # que representa al cliente final ante la banquetera.
    nombre_agencia_planner = models.CharField(max_length=150, blank=True)
    notas = models.TextField(blank=True)
    fecha_alta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "telefono"],
                name="unique_cliente_telefono_por_empresa",
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


# ---------------------------------------------------------------------------
# 3. SedeEvento
# ---------------------------------------------------------------------------
class SedeEvento(models.Model):
    """Jardín, salón o hacienda donde se monta el evento. Guarda los datos
    operativos que el "Modo Asistente" necesita recolectar cuando no hay
    Event Planner de por medio (accesos de carga, agua, luz, restricciones)."""

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="sedes"
    )
    nombre = models.CharField("Nombre del jardín/salón", max_length=150)
    direccion = models.CharField(max_length=255)
    notas_acceso_carga = models.TextField(
        "Notas de acceso para carga y descarga", blank=True
    )
    disponibilidad_agua = models.BooleanField(default=True)
    disponibilidad_luz = models.BooleanField(default=True)
    capacidad_maxima_invitados = models.PositiveIntegerField(
        null=True, blank=True
    )
    restricciones_operativas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sede de Evento"
        verbose_name_plural = "Sedes de Evento"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "nombre"], name="unique_sede_nombre_por_empresa"
            )
        ]

    def __str__(self):
        return self.nombre


# ---------------------------------------------------------------------------
# 4. Evento
# ---------------------------------------------------------------------------
class Evento(models.Model):
    """Un evento contratado (o en proceso de cotización). Implementa el
    "Semáforo de Fechas" del Módulo A."""

    class EstadoSemaforo(models.TextChoices):
        PROSPECTO = "PROSPECTO", "🟡 Prospecto"
        APARTADO = "APARTADO", "🟠 Contratado sin anticipo"
        CONFIRMADO = "CONFIRMADO", "🔴 Confirmado"

    class TipoCliente(models.TextChoices):
        PLANNER = "PLANNER", "Con Event Planner"
        DIRECTO = "DIRECTO", "Cliente Directo"

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="eventos"
    )
    nombre_evento = models.CharField(max_length=200)
    fecha = models.DateField()
    numero_invitados = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    estado_semaforo = models.CharField(
        max_length=12,
        choices=EstadoSemaforo.choices,
        default=EstadoSemaforo.PROSPECTO,
    )
    tipo_cliente = models.CharField(max_length=10, choices=TipoCliente.choices)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="eventos"
    )
    sede = models.ForeignKey(
        SedeEvento, on_delete=models.PROTECT, related_name="eventos"
    )

    # --- Campos de apoyo a la lógica de negocio del semáforo ---
    fecha_cotizacion = models.DateTimeField(auto_now_add=True)
    # Prospecto: vence 72 horas después de cotizado (regla del Módulo A).
    fecha_vencimiento_prospecto = models.DateTimeField(null=True, blank=True)
    # Apartado: se reserva inventario por 5 días hábiles en espera de pago.
    fecha_limite_anticipo = models.DateField(null=True, blank=True)
    fecha_registro_anticipo = models.DateTimeField(null=True, blank=True)
    autorizado_proveedor_externo = models.BooleanField(
        "¿Administrador autorizó renta de equipo externo?", default=False
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"
        ordering = ["fecha"]
        indexes = [models.Index(fields=["empresa", "fecha", "estado_semaforo"])]

    def __str__(self):
        return f"{self.nombre_evento} - {self.fecha} ({self.get_estado_semaforo_display()})"

    def clean(self):
        # El planner nunca debe llegar a ver costos/márgenes: se refuerza a
        # nivel de serializer/permisos, pero validamos consistencia de tipo.
        if self.tipo_cliente == self.TipoCliente.PLANNER and not self.cliente_id:
            raise ValidationError("Un evento con Event Planner requiere un cliente asociado.")


# ---------------------------------------------------------------------------
# Insumo (modelo auxiliar requerido por IngredienteReceta, punto 6)
# ---------------------------------------------------------------------------
class Insumo(models.Model):
    """Ingrediente / insumo de bodega usado en las recetas. Aquí vive el
    "Margen de Merma" nativo por ingrediente (Módulo C), por ejemplo la
    pérdida de peso en proteínas al cocinar o limpiar."""

    class UnidadMedida(models.TextChoices):
        GRAMOS = "G", "Gramos"
        KILOGRAMOS = "KG", "Kilogramos"
        MILILITROS = "ML", "Mililitros"
        LITROS = "L", "Litros"
        PIEZA = "PZA", "Pieza"

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="insumos"
    )
    nombre = models.CharField(max_length=150)
    unidad_base = models.CharField(max_length=3, choices=UnidadMedida.choices)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=4)
    # % de merma esperado para este insumo (ej. 0.12 = 12% de pérdida por
    # limpieza/cocción). Se aplica en el algoritmo de explosión de insumos.
    porcentaje_merma = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Ej. 0.12 representa 12% de merma",
    )

    class Meta:
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "nombre"], name="unique_insumo_nombre_por_empresa"
            )
        ]

    def __str__(self):
        return self.nombre


# ---------------------------------------------------------------------------
# 5. RecetaMaestra
# ---------------------------------------------------------------------------
class RecetaMaestra(models.Model):
    """Receta del recetario maestro escalable. Se captura con base en
    `porciones_base` (típicamente 1 o 10) y el algoritmo multiplicador del
    Módulo C escala las cantidades de insumos según la garantía final de
    invitados de cada evento."""

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="recetas"
    )
    nombre = models.CharField(max_length=150)
    tiempo_menu = models.CharField(
        "Tiempo del menú",
        max_length=20,
        choices=TiempoMenu.choices,
        default=TiempoMenu.FUERTE,
    )
    porciones_base = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Número de porciones sobre el que está capturada la receta (ej. 1 o 10).",
    )
    costo_estimado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo estimado de la receta completa para `porciones_base` porciones.",
    )

    class Meta:
        verbose_name = "Receta Maestra"
        verbose_name_plural = "Recetario Maestro"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "nombre"], name="unique_receta_nombre_por_empresa"
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.porciones_base} porciones base)"


# ---------------------------------------------------------------------------
# 6. IngredienteReceta (a través de Recetas <-> Insumos)
# ---------------------------------------------------------------------------
class IngredienteReceta(models.Model):
    """Relación muchos a muchos entre `RecetaMaestra` e `Insumo`, con la
    cantidad y unidad de medida necesarias para `porciones_base` porciones."""

    receta = models.ForeignKey(
        RecetaMaestra, on_delete=models.CASCADE, related_name="ingredientes"
    )
    insumo = models.ForeignKey(
        Insumo, on_delete=models.PROTECT, related_name="usos_en_recetas"
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Cantidad de este insumo necesaria para `porciones_base` porciones de la receta.",
    )
    unidad_medida = models.CharField(
        max_length=3, choices=Insumo.UnidadMedida.choices
    )

    class Meta:
        verbose_name = "Ingrediente de Receta"
        verbose_name_plural = "Ingredientes de Receta"
        constraints = [
            models.UniqueConstraint(
                fields=["receta", "insumo"], name="unique_insumo_por_receta"
            )
        ]

    def __str__(self):
        return f"{self.insumo} x {self.cantidad}{self.unidad_medida} en {self.receta}"


# ---------------------------------------------------------------------------
# 7. DetalleMenuEvento
# ---------------------------------------------------------------------------
class DetalleMenuEvento(models.Model):
    """Los platos (recetas) seleccionados para un evento específico. Es la
    base para la "Explosión de Insumos" y para las listas de carga de loza
    del Módulo D (según el tiempo del menú de cada plato)."""

    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="detalle_menu"
    )
    receta = models.ForeignKey(
        RecetaMaestra, on_delete=models.PROTECT, related_name="usos_en_eventos"
    )
    notas_personalizacion = models.TextField(
        "Notas de personalización para este evento", blank=True
    )

    class Meta:
        verbose_name = "Detalle de Menú de Evento"
        verbose_name_plural = "Detalles de Menú de Evento"
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "receta"], name="unique_receta_por_evento"
            )
        ]

    def __str__(self):
        return f"{self.receta} en {self.evento}"


# ---------------------------------------------------------------------------
# 8. PruebaMenu
# ---------------------------------------------------------------------------
class PruebaMenu(models.Model):
    """Ficha de degustación (Módulo B). Se cruza contra el calendario de
    eventos masivos: no debe caer en viernes/sábado de alta operación."""

    LIMITE_CORTESIA_ASISTENTES = 4

    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="pruebas_menu"
    )
    fecha_prueba = models.DateField()
    asistentes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    platos_a_probar = models.ManyToManyField(
        RecetaMaestra, related_name="pruebas", blank=True
    )
    notas_chef = models.TextField(
        "Historial de modificaciones culinarias del Chef", blank=True
    )
    aprobado = models.BooleanField(default=False)
    cobro_adicional_generado = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        verbose_name = "Prueba de Menú"
        verbose_name_plural = "Pruebas de Menú"
        ordering = ["fecha_prueba"]

    def __str__(self):
        return f"Prueba de menú - {self.evento.nombre_evento} ({self.fecha_prueba})"

    @property
    def excede_limite_cortesia(self) -> bool:
        return self.asistentes > self.LIMITE_CORTESIA_ASISTENTES


# ---------------------------------------------------------------------------
# 9. InventarioEquipo
# ---------------------------------------------------------------------------
class InventarioEquipo(models.Model):
    """Vajilla, cristalería y cubertería disponible en la bodega central
    (Módulo D)."""

    class TipoEquipo(models.TextChoices):
        VAJILLA = "VAJILLA", "Vajilla / Loza"
        CRISTALERIA = "CRISTALERIA", "Cristalería"
        CUBERTERIA = "CUBERTERIA", "Cubertería"
        MOBILIARIO = "MOBILIARIO", "Mobiliario"
        OTRO = "OTRO", "Otro"

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="inventario_equipo"
    )
    nombre = models.CharField(
        max_length=150, help_text="Ej. Plato hondo entrada, Copa de vino, Tenedor trinche"
    )
    tipo = models.CharField(max_length=15, choices=TipoEquipo.choices)
    stock_disponible = models.PositiveIntegerField(default=0)
    costo_reposicion_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        verbose_name = "Artículo de Inventario"
        verbose_name_plural = "Inventario de Equipo"
        ordering = ["tipo", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "nombre"], name="unique_articulo_nombre_por_empresa"
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.stock_disponible} disp.)"


# ---------------------------------------------------------------------------
# 10. RegistroRoturas
# ---------------------------------------------------------------------------
class RegistroRoturas(models.Model):
    """Registro de artículos rotos o extraviados al conteo de retorno del
    Capitán de Meseros. Genera el "Cargo por Daños" descontado del depósito
    en garantía (Módulo D)."""

    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="registros_rotura"
    )
    articulo = models.ForeignKey(
        InventarioEquipo, on_delete=models.PROTECT, related_name="roturas"
    )
    cantidad_rota = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    costo_reposicion = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo total de reposición para esta rotura (cantidad x costo unitario).",
    )
    registrado_por = models.CharField(
        "Capitán de Meseros que registró el conteo", max_length=150, blank=True
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    pdf_cargo_danos_generado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Registro de Rotura"
        verbose_name_plural = "Registros de Roturas"
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"{self.cantidad_rota}x {self.articulo} - {self.evento}"


# ---------------------------------------------------------------------------
# 11. RequerimientoEquipoTiempo (Listas de Carga Automatizadas, Módulo D)
# ---------------------------------------------------------------------------
class RequerimientoEquipoTiempo(models.Model):
    """Catálogo que define qué artículo de inventario (loza, cristalería,
    cubertería) requiere cada tiempo del menú y cuántas piezas por invitado
    (ej. 1 plato hondo por invitado en ENTRADA, 1 copa de vino por invitado
    en BEBIDA). Con esto el sistema desglosa automáticamente los
    requerimientos de equipo según los tiempos del menú seleccionado en cada
    evento (Módulo D)."""

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="requerimientos_equipo"
    )
    tiempo_menu = models.CharField(max_length=20, choices=TiempoMenu.choices)
    articulo = models.ForeignKey(
        InventarioEquipo, on_delete=models.CASCADE, related_name="requerimientos_por_tiempo"
    )
    cantidad_por_invitado = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Ej. 1 pieza por invitado. Puede ser fraccionario (ej. 0.5 si se comparte).",
    )

    class Meta:
        verbose_name = "Requerimiento de Equipo por Tiempo de Menú"
        verbose_name_plural = "Requerimientos de Equipo por Tiempo de Menú"
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "tiempo_menu", "articulo"],
                name="unique_requerimiento_equipo_por_tiempo",
            )
        ]

    def __str__(self):
        return (
            f"{self.get_tiempo_menu_display()} -> {self.articulo} "
            f"x{self.cantidad_por_invitado}/invitado"
        )


# ---------------------------------------------------------------------------
# 12. ListaCargaEvento / DetalleListaCarga (Factor +10% de Rotura, Módulo D)
# ---------------------------------------------------------------------------
class ListaCargaEvento(models.Model):
    """Lista de carga automatizada de un evento: desglosa la vajilla,
    cristalería y cubertería requerida según los tiempos del menú
    contratado (cruzando `DetalleMenuEvento` con `RequerimientoEquipoTiempo`)
    y aplica el **Factor +10% de Rotura** a todo el equipo que sale de la
    bodega principal, para prevenir accidentes durante el flete, montaje o
    ejecución del evento (Módulo D)."""

    FACTOR_ROTURA = Decimal("0.10")

    evento = models.OneToOneField(
        Evento, on_delete=models.CASCADE, related_name="lista_carga"
    )
    generada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    conteo_retorno_completado = models.BooleanField(
        "¿El Capitán de Meseros ya hizo el conteo de retorno?", default=False
    )

    class Meta:
        verbose_name = "Lista de Carga de Evento"
        verbose_name_plural = "Listas de Carga de Evento"

    def __str__(self):
        return f"Lista de carga - {self.evento.nombre_evento}"

    def generar_o_actualizar_detalles(self):
        """Recalcula las líneas de la lista de carga a partir de los tiempos
        de menú realmente contratados en el evento y el catálogo
        `RequerimientoEquipoTiempo` de la empresa. Se puede volver a llamar
        cada vez que cambie el menú o el número de invitados del evento
        (ej. al confirmarse la garantía final)."""
        tiempos_contratados = set(
            self.evento.detalle_menu.values_list("receta__tiempo_menu", flat=True)
        )
        requerimientos = RequerimientoEquipoTiempo.objects.filter(
            empresa=self.evento.empresa, tiempo_menu__in=tiempos_contratados
        ).select_related("articulo")

        # Un mismo artículo puede servir a más de un tiempo del menú (ej. el
        # "Plato plano" se usa tanto en ENTRADA como en FUERTE), así que se
        # consolidan las cantidades por artículo antes de guardar.
        cantidades_por_articulo = {}
        for req in requerimientos:
            acumulado = cantidades_por_articulo.setdefault(req.articulo_id, Decimal("0"))
            cantidades_por_articulo[req.articulo_id] = acumulado + (
                req.cantidad_por_invitado * self.evento.numero_invitados
            )

        articulos_vigentes = set(cantidades_por_articulo.keys())
        # Quita líneas de artículos que ya no correspondan (ej. se eliminó un
        # tiempo del menú) para que la lista siempre refleje el menú actual.
        self.detalles.exclude(articulo_id__in=articulos_vigentes).delete()

        for articulo_id, cantidad_requerida in cantidades_por_articulo.items():
            cantidad_entera = int(
                cantidad_requerida.to_integral_value(rounding=ROUND_CEILING)
            )
            DetalleListaCarga.objects.update_or_create(
                lista_carga=self,
                articulo_id=articulo_id,
                defaults={"cantidad_requerida": cantidad_entera},
            )


class DetalleListaCarga(models.Model):
    """Una línea de la lista de carga: cuántas piezas de un artículo hacen
    falta para atender a los invitados (`cantidad_requerida`) y cuántas
    realmente salen de la bodega ya con el Factor +10% de rotura aplicado
    (`cantidad_a_cargar`)."""

    lista_carga = models.ForeignKey(
        ListaCargaEvento, on_delete=models.CASCADE, related_name="detalles"
    )
    articulo = models.ForeignKey(
        InventarioEquipo, on_delete=models.PROTECT, related_name="detalles_lista_carga"
    )
    cantidad_requerida = models.PositiveIntegerField(
        help_text="Piezas necesarias para atender a los invitados, sin margen de seguridad."
    )
    surtido = models.BooleanField("¿Ya se cargó al camión?", default=False)

    class Meta:
        verbose_name = "Detalle de Lista de Carga"
        verbose_name_plural = "Detalles de Lista de Carga"
        ordering = ["articulo__tipo", "articulo__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["lista_carga", "articulo"], name="unique_articulo_por_lista_carga"
            )
        ]

    @property
    def cantidad_a_cargar(self) -> int:
        """Cantidad real que sale de la bodega: `cantidad_requerida` + el
        Factor +10% de Rotura del Módulo D, redondeado siempre hacia arriba
        para no quedar corto en el evento."""
        factor = 1 + ListaCargaEvento.FACTOR_ROTURA
        return math.ceil(self.cantidad_requerida * factor)

    def __str__(self):
        return (
            f"{self.articulo} - requeridas {self.cantidad_requerida} / "
            f"a cargar {self.cantidad_a_cargar} (+10% rotura)"
        )
