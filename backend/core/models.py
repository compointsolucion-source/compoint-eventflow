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
import secrets
import uuid
from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def _generar_token_planner() -> str:
    """Token largo e impredecible que hace de 'contraseña' del link único
    del Portal del Event Planner (Módulo A): quien tenga el link ve el
    cronograma de ESE evento sin necesitar cuenta ni contraseña, y sin ver
    costos, márgenes ni otros eventos de la banquetera."""
    return secrets.token_urlsafe(24)


def _sumar_dias_habiles(fecha_inicio, dias_habiles):
    """Suma `dias_habiles` (de lunes a viernes, sin considerar días
    festivos) a `fecha_inicio`. Se usa para calcular la fecha límite del
    anticipo de un Apartado (Módulo A: 5 días hábiles)."""
    fecha = fecha_inicio
    agregados = 0
    while agregados < dias_habiles:
        fecha += timedelta(days=1)
        if fecha.weekday() < 5:  # 0=lunes ... 4=viernes
            agregados += 1
    return fecha


def _redondear_arriba(cantidad_decimal) -> int:
    """Redondea siempre hacia arriba (nunca se quiere quedar corto de loza
    ni de personal en un evento real)."""
    return int(Decimal(cantidad_decimal).to_integral_value(rounding=ROUND_CEILING))


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
        "¿Administrador ya autorizó cubrir por fuera el faltante de equipo o "
        "personal de este día? (renta externa / staff extra)",
        default=False,
        help_text=(
            "Actívalo si ya resolviste por fuera (renta externa, personal "
            "extra) que este día esté saturado de loza o personal en el "
            "sistema. Con esto el bloqueo automático de capacidad del "
            "Módulo A deja pasar este evento aunque el inventario interno "
            "no alcance."
        ),
    )

    # Portal colaborativo del Event Planner (Módulo A): acceso sin cuenta ni
    # contraseña vía link único (ver `_generar_token_planner` y
    # `PlannerEventoView` en views.py).
    token_planner = models.CharField(
        max_length=64, unique=True, default=_generar_token_planner, editable=False
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

    @property
    def link_planner(self) -> str:
        """Link único (sin cuenta ni contraseña) para compartirle a un Event
        Planner externo, ej. por WhatsApp o correo. Ver `token_planner`."""
        from django.conf import settings

        return f"{settings.FRONTEND_URL}/planner/{self.token_planner}/"

    # --- Reglas automáticas del Semáforo de Fechas (Módulo A) ---------------
    # No hay un cron/scheduler en el plan gratuito de Render, así que el
    # vencimiento NUNCA depende de que un job externo "pase" a revisarlo:
    # se calcula al vuelo cada vez que se consulta, comparando la fecha/hora
    # actual contra los campos guardados. Un evento vencido no se borra ni
    # se modifica solo -sigue visible para que el staff lo reactive a mano-,
    # simplemente deja de contar para bloquear esa fecha.

    @property
    def prospecto_vencido(self) -> bool:
        """True si este Prospecto ya pasó las 72 horas sin avanzar a
        Apartado/Confirmado."""
        return (
            self.estado_semaforo == self.EstadoSemaforo.PROSPECTO
            and self.fecha_vencimiento_prospecto is not None
            and timezone.now() > self.fecha_vencimiento_prospecto
        )

    @property
    def anticipo_vencido(self) -> bool:
        """True si este Apartado ya pasó su fecha límite de anticipo (5 días
        hábiles) sin que se registrara el pago."""
        return (
            self.estado_semaforo == self.EstadoSemaforo.APARTADO
            and self.fecha_registro_anticipo is None
            and self.fecha_limite_anticipo is not None
            and timezone.localdate() > self.fecha_limite_anticipo
        )

    @property
    def vencido(self) -> bool:
        """True si el evento venció automáticamente (Prospecto o Apartado) y
        por lo tanto ya no debe bloquear su fecha para otros eventos."""
        return self.prospecto_vencido or self.anticipo_vencido

    @property
    def bloquea_fecha(self) -> bool:
        """True si este evento debe contar para el bloqueo de capacidad de
        loza/personal de su fecha (Módulo A). Un Confirmado siempre bloquea;
        un Apartado bloquea mientras no haya vencido su plazo de anticipo.
        Un Prospecto nunca bloquea por sí solo: es solo una cotización."""
        if self.vencido:
            return False
        return self.estado_semaforo in (
            self.EstadoSemaforo.APARTADO,
            self.EstadoSemaforo.CONFIRMADO,
        )

    def save(self, *args, **kwargs):
        # Al cotizar un Prospecto, se le da automáticamente su plazo de 72
        # horas (si no se capturó a mano). Al pasar a Apartado, se le da
        # automáticamente su plazo de 5 días hábiles para el anticipo.
        if (
            self.estado_semaforo == self.EstadoSemaforo.PROSPECTO
            and self.fecha_vencimiento_prospecto is None
        ):
            self.fecha_vencimiento_prospecto = timezone.now() + timedelta(hours=72)
        if (
            self.estado_semaforo == self.EstadoSemaforo.APARTADO
            and self.fecha_limite_anticipo is None
        ):
            self.fecha_limite_anticipo = _sumar_dias_habiles(timezone.localdate(), 5)
        super().save(*args, **kwargs)

    def clean(self):
        # El planner nunca debe llegar a ver costos/márgenes: se refuerza a
        # nivel de serializer/permisos, pero validamos consistencia de tipo.
        if self.tipo_cliente == self.TipoCliente.PLANNER and not self.cliente_id:
            raise ValidationError("Un evento con Event Planner requiere un cliente asociado.")
        # Bloqueo por capacidad de invitados de la sede (Módulo A).
        if (
            self.sede_id
            and self.numero_invitados
            and self.sede.capacidad_maxima_invitados
            and self.numero_invitados > self.sede.capacidad_maxima_invitados
        ):
            raise ValidationError(
                {
                    "numero_invitados": (
                        f"La sede '{self.sede.nombre}' tiene una capacidad máxima de "
                        f"{self.sede.capacidad_maxima_invitados} invitados."
                    )
                }
            )


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
        help_text="Costo total de reposición para esta rotura (cantidad x costo unitario). Se calcula solo.",
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

    def save(self, *args, **kwargs):
        # El costo de reposición nunca se captura a mano: siempre es
        # cantidad rota x costo de reposición unitario del artículo, para
        # que el "Cargo por Daños" del conteo de retorno (Módulo D) sea
        # consistente con el catálogo de inventario.
        self.costo_reposicion = (
            Decimal(self.cantidad_rota) * self.articulo.costo_reposicion_unitario
        ).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

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


def _calcular_cantidades_equipo(evento, tiempo_menu_extra=None):
    """Devuelve {articulo_id: cantidad_requerida_entera} cruzando los
    tiempos de menú realmente contratados por `evento` con el catálogo
    `RequerimientoEquipoTiempo` de su empresa. No depende de que ya exista
    una `ListaCargaEvento` guardada: la usa tanto `generar_o_actualizar_detalles`
    (Módulo D) como el bloqueo de capacidad por fecha (Módulo A).

    `tiempo_menu_extra` permite previsualizar el efecto de agregar un tiempo
    de menú que todavía NO se ha guardado (por ejemplo, para validar ANTES
    de guardar un nuevo `DetalleMenuEvento`)."""
    tiempos_contratados = set(
        evento.detalle_menu.values_list("receta__tiempo_menu", flat=True)
    )
    if tiempo_menu_extra:
        tiempos_contratados.add(tiempo_menu_extra)
    if not tiempos_contratados:
        return {}

    requerimientos = RequerimientoEquipoTiempo.objects.filter(
        empresa_id=evento.empresa_id, tiempo_menu__in=tiempos_contratados
    )

    # Un mismo artículo puede servir a más de un tiempo del menú (ej. el
    # "Plato plano" se usa tanto en ENTRADA como en FUERTE), así que se
    # consolidan las cantidades por artículo antes de redondear.
    cantidades_por_articulo = {}
    for req in requerimientos:
        acumulado = cantidades_por_articulo.setdefault(req.articulo_id, Decimal("0"))
        cantidades_por_articulo[req.articulo_id] = acumulado + (
            req.cantidad_por_invitado * evento.numero_invitados
        )
    return {
        articulo_id: _redondear_arriba(cantidad)
        for articulo_id, cantidad in cantidades_por_articulo.items()
    }


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
        `RequerimientoEquipoTiempo` de la empresa (ver `_calcular_cantidades_equipo`).
        Se puede volver a llamar cada vez que cambie el menú o el número de
        invitados del evento (ej. al confirmarse la garantía final)."""
        cantidades_por_articulo = _calcular_cantidades_equipo(self.evento)

        articulos_vigentes = set(cantidades_por_articulo.keys())
        # Quita líneas de artículos que ya no correspondan (ej. se eliminó un
        # tiempo del menú) para que la lista siempre refleje el menú actual.
        self.detalles.exclude(articulo_id__in=articulos_vigentes).delete()

        for articulo_id, cantidad_entera in cantidades_por_articulo.items():
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


# ---------------------------------------------------------------------------
# Módulo E: Staffing y Personal Eventual
# ---------------------------------------------------------------------------
class PersonalEventual(models.Model):
    """Mesero, bartender, garrotero o capitán que se postula de forma
    autónoma a vacantes de eventos desde la Bolsa de Trabajo (Módulo E)."""

    class Rol(models.TextChoices):
        MESERO = "MESERO", "Mesero"
        BARTENDER = "BARTENDER", "Bartender"
        GARROTERO = "GARROTERO", "Garrotero"
        CAPITAN = "CAPITAN", "Capitán de Meseros"
        OTRO = "OTRO", "Otro"

    empresa = models.ForeignKey(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="personal_eventual"
    )
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    rol_principal = models.CharField(max_length=15, choices=Rol.choices)
    activo = models.BooleanField(
        "¿Disponible para postularse a vacantes?", default=True
    )

    class Meta:
        verbose_name = "Personal Eventual"
        verbose_name_plural = "Personal Eventual"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_rol_principal_display()})"


class VacanteEvento(models.Model):
    """Una vacante de personal para un evento específico: cuántas personas
    de un rol dado hacen falta y a qué tarifa por turno (Bolsa de Trabajo,
    Módulo E). El personal eventual se postula de forma autónoma."""

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="vacantes")
    rol = models.CharField(max_length=15, choices=PersonalEventual.Rol.choices)
    cantidad_requerida = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    tarifa_por_turno = models.DecimalField(max_digits=8, decimal_places=2)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Vacante de Evento"
        verbose_name_plural = "Vacantes de Evento"
        ordering = ["evento__fecha"]
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "rol"], name="unique_rol_por_vacante_evento"
            )
        ]

    @property
    def cantidad_aceptada(self) -> int:
        return self.postulaciones.filter(estado=Postulacion.Estado.ACEPTADO).count()

    @property
    def cubierta(self) -> bool:
        return self.cantidad_aceptada >= self.cantidad_requerida

    def __str__(self):
        return f"{self.get_rol_display()} x{self.cantidad_requerida} - {self.evento.nombre_evento}"


class Postulacion(models.Model):
    """Postulación autónoma de un trabajador eventual a una vacante (Bolsa
    de Trabajo, Módulo E). Al aceptarse, se crea su `CheckIn` para el día
    del evento."""

    class Estado(models.TextChoices):
        POSTULADO = "POSTULADO", "Postulado"
        ACEPTADO = "ACEPTADO", "Aceptado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    vacante = models.ForeignKey(
        VacanteEvento, on_delete=models.CASCADE, related_name="postulaciones"
    )
    personal = models.ForeignKey(
        PersonalEventual, on_delete=models.CASCADE, related_name="postulaciones"
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.POSTULADO)
    postulado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Postulación"
        verbose_name_plural = "Postulaciones"
        ordering = ["-postulado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["vacante", "personal"], name="unique_postulacion_por_vacante"
            )
        ]

    def __str__(self):
        return f"{self.personal.nombre} -> {self.vacante} ({self.get_estado_display()})"


def _generar_codigo_checkin() -> str:
    """Código corto único que hace las veces de contenido de un código QR
    (Check-In del Módulo E) en esta implementación web: el Capitán de
    Meseros lo confirma al llegar el trabajador, sin depender de hardware
    biométrico ni de GPS real."""
    return uuid.uuid4().hex[:8].upper()


class CheckIn(models.Model):
    """Registro de asistencia del personal eventual al evento (Módulo E:
    Check-In Biométrico o Geolocalizado). En esta implementación web se usa
    un código de verificación único por postulación en vez de biometría/GPS
    real, que el Capitán de Meseros confirma al llegar el trabajador."""

    postulacion = models.OneToOneField(
        Postulacion, on_delete=models.CASCADE, related_name="check_in"
    )
    codigo_verificacion = models.CharField(
        max_length=8, unique=True, default=_generar_codigo_checkin, editable=False
    )
    hora_checkin = models.DateTimeField(null=True, blank=True)
    confirmado_por = models.CharField(
        "Nombre de quien confirmó (ej. Capitán de Meseros)", max_length=150, blank=True
    )

    class Meta:
        verbose_name = "Check-In de Personal"
        verbose_name_plural = "Check-Ins de Personal"

    @property
    def asistio(self) -> bool:
        return self.hora_checkin is not None

    def confirmar(self, confirmado_por: str = ""):
        self.hora_checkin = timezone.now()
        if confirmado_por:
            self.confirmado_por = confirmado_por
        self.save(update_fields=["hora_checkin", "confirmado_por"])

    def __str__(self):
        estado = "presente" if self.asistio else "pendiente"
        return f"Check-in {self.postulacion.personal.nombre} ({estado})"


# ---------------------------------------------------------------------------
# Módulo F: Finanzas — Cotizador por Volumen y Esquema de Cobro 50/30/20
# ---------------------------------------------------------------------------
class ConfiguracionCotizador(models.Model):
    """Parámetros del Cotizador por Volumen (Módulo F) por empresa: el
    precio por persona sube cuando bajan los invitados, para absorber entre
    menos comensales los costos fijos de transporte y personal base."""

    empresa = models.OneToOneField(
        EmpresaBanquetera, on_delete=models.CASCADE, related_name="configuracion_cotizador"
    )
    costo_base_por_persona = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Costo variable de alimentos/servicio por invitado.",
    )
    costos_fijos_transporte_personal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Costos fijos del evento (transporte, personal base) a repartir entre los invitados.",
    )

    class Meta:
        verbose_name = "Configuración del Cotizador"
        verbose_name_plural = "Configuración del Cotizador"

    def cotizar(self, numero_invitados: int) -> dict:
        """Precio por persona INVERSAMENTE proporcional al volumen: entre
        menos invitados, más costos fijos le tocan a cada uno."""
        if numero_invitados <= 0:
            raise ValidationError("El número de invitados debe ser mayor a cero.")
        costos_fijos_por_persona = self.costos_fijos_transporte_personal / Decimal(
            numero_invitados
        )
        precio_por_persona = self.costo_base_por_persona + costos_fijos_por_persona
        precio_total = precio_por_persona * numero_invitados
        return {
            "numero_invitados": numero_invitados,
            "costo_base_por_persona": self.costo_base_por_persona,
            "costos_fijos_por_persona": costos_fijos_por_persona.quantize(Decimal("0.01")),
            "precio_por_persona": precio_por_persona.quantize(Decimal("0.01")),
            "precio_total": precio_total.quantize(Decimal("0.01")),
        }

    def __str__(self):
        return f"Cotizador de {self.empresa}"


class EsquemaPagoEvento(models.Model):
    """Esquema de Cobro Automatizado del Módulo F: reparte el monto total
    del evento en 3 abonos (50/30/20) con sus fechas límite, según la
    estructura tradicional de la industria de banquetes."""

    PORCENTAJE_ANTICIPO = Decimal("0.50")
    PORCENTAJE_INTERMEDIO = Decimal("0.30")
    PORCENTAJE_LIQUIDACION = Decimal("0.20")
    DIAS_LIQUIDACION_ANTES_DEL_EVENTO = 15

    evento = models.OneToOneField(Evento, on_delete=models.CASCADE, related_name="esquema_pago")
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    generado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Esquema de Pago de Evento"
        verbose_name_plural = "Esquemas de Pago de Evento"

    def generar_o_actualizar_abonos(self):
        """(Re)crea los 3 abonos del esquema 50/30/20 con sus montos y
        fechas límite:
        - Anticipo (50%): al apartar la fecha / firmar contrato (hoy).
        - Intermedio (30%): en la fecha de la prueba de menú (o, si no hay
          prueba capturada aún, 30 días antes del evento).
        - Liquidación (20%): obligatoria 15 días antes del evento.
        """
        hoy = timezone.localdate()

        primera_prueba = self.evento.pruebas_menu.order_by("fecha_prueba").first()
        fecha_intermedia = (
            primera_prueba.fecha_prueba
            if primera_prueba
            else self.evento.fecha - timedelta(days=30)
        )
        fecha_liquidacion = self.evento.fecha - timedelta(
            days=self.DIAS_LIQUIDACION_ANTES_DEL_EVENTO
        )

        definicion = [
            (AbonoEvento.TipoAbono.ANTICIPO, self.PORCENTAJE_ANTICIPO, hoy),
            (AbonoEvento.TipoAbono.INTERMEDIO, self.PORCENTAJE_INTERMEDIO, fecha_intermedia),
            (AbonoEvento.TipoAbono.LIQUIDACION, self.PORCENTAJE_LIQUIDACION, fecha_liquidacion),
        ]
        for tipo, porcentaje, fecha_limite in definicion:
            monto = (self.monto_total * porcentaje).quantize(Decimal("0.01"))
            AbonoEvento.objects.update_or_create(
                esquema=self,
                tipo=tipo,
                defaults={
                    "porcentaje": porcentaje * 100,
                    "monto": monto,
                    "fecha_limite": fecha_limite,
                },
            )

    def __str__(self):
        return f"Esquema de pago - {self.evento.nombre_evento} (${self.monto_total})"


class AbonoEvento(models.Model):
    """Un abono (anticipo, pago intermedio o liquidación) del esquema de
    cobro 50/30/20 del Módulo F."""

    class TipoAbono(models.TextChoices):
        ANTICIPO = "ANTICIPO", "Anticipo (50%) — apartado y firma de contrato"
        INTERMEDIO = "INTERMEDIO", "Pago intermedio (30%) — fecha de prueba de menú"
        LIQUIDACION = "LIQUIDACION", "Liquidación (20%) — 15 días antes del evento"

    esquema = models.ForeignKey(
        EsquemaPagoEvento, on_delete=models.CASCADE, related_name="abonos"
    )
    tipo = models.CharField(max_length=15, choices=TipoAbono.choices)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_limite = models.DateField()
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Abono de Evento"
        verbose_name_plural = "Abonos de Evento"
        ordering = ["fecha_limite"]
        constraints = [
            models.UniqueConstraint(
                fields=["esquema", "tipo"], name="unique_tipo_abono_por_esquema"
            )
        ]

    @property
    def vencido(self) -> bool:
        return not self.pagado and self.fecha_limite < timezone.localdate()

    def marcar_pagado(self):
        self.pagado = True
        self.fecha_pago = timezone.localdate()
        self.save(update_fields=["pagado", "fecha_pago"])

    def __str__(self):
        estado = "pagado" if self.pagado else "pendiente"
        return f"{self.get_tipo_display()} - ${self.monto} ({estado})"
