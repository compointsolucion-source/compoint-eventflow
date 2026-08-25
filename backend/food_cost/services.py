"""
Algoritmo de Explosión de Insumos (Módulo C - Ingeniería de Menús / Food Cost).

Este módulo implementa, en código real, la lógica que el "PROMPT MAESTRO 3"
del Plan Maestro dejaba pendiente (el prompt llegó vacío en el documento
original). Se construyó directamente a partir de las reglas de negocio ya
descritas en la sección "Módulo C" del plan:

1. Recetario Maestro Escalable:
   Las recetas se capturan para `porciones_base` porciones (1 o 10). Cuando
   cambia la garantía de invitados de un evento, se aplica un factor de
   escala = numero_invitados / porciones_base a cada ingrediente.

2. Explosión de Insumos:
   Se recorren TODAS las recetas seleccionadas en el menú de un evento
   (`DetalleMenuEvento`), se escalan sus ingredientes y se consolidan por
   insumo (sumando cantidades de distintas recetas que compartan un mismo
   insumo) para producir una única lista de compras para adquisiciones.

3. Margen de Merma:
   Cada `Insumo` tiene un `porcentaje_merma` nativo (ej. 0.12 = 12% de
   pérdida de peso por cocción/limpieza). La cantidad "neta" que pide la
   receta no es la que hay que comprar: hay que comprar más para que,
   después de la merma, sobreviva la cantidad neta requerida. Por eso:

       cantidad_a_comprar = cantidad_neta / (1 - porcentaje_merma)

   Con porcentaje_merma = 0 la cantidad a comprar es igual a la neta.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError

# Precisión de salida para cantidades y costos (4 y 2 decimales respectivamente).
_CANTIDAD_Q = Decimal("0.0001")
_COSTO_Q = Decimal("0.01")


class MermaInvalidaError(ValidationError):
    """Se lanza cuando un insumo tiene porcentaje_merma >= 1 (100%), lo cual
    haría que la cantidad a comprar fuera infinita/indefinida."""


@dataclass
class LineaInsumoConsolidada:
    """Una línea de la lista de compras consolidada para un evento."""

    insumo_id: int
    nombre: str
    unidad_medida: str
    cantidad_neta: Decimal  # lo que las recetas piden, ya escalado por invitados
    porcentaje_merma: Decimal
    cantidad_a_comprar: Decimal  # cantidad_neta ajustada por merma
    costo_unitario: Decimal
    costo_total: Decimal
    recetas_origen: list = field(default_factory=list)  # nombres de recetas que lo usan

    def to_dict(self) -> dict:
        return {
            "insumo_id": self.insumo_id,
            "nombre": self.nombre,
            "unidad_medida": self.unidad_medida,
            "cantidad_neta": str(self.cantidad_neta),
            "porcentaje_merma": str(self.porcentaje_merma),
            "cantidad_a_comprar": str(self.cantidad_a_comprar),
            "costo_unitario": str(self.costo_unitario),
            "costo_total": str(self.costo_total),
            "recetas_origen": self.recetas_origen,
        }


def calcular_factor_escala(porciones_base: int, numero_invitados: int) -> Decimal:
    """Factor multiplicador para escalar una receta de `porciones_base`
    porciones a `numero_invitados` comensales.

    Ej. receta base a 10 porciones, evento con garantía de 350 invitados
    -> factor = 35 (se multiplica cada ingrediente x35).
    """
    if porciones_base <= 0:
        raise ValidationError("porciones_base debe ser mayor a cero.")
    if numero_invitados <= 0:
        raise ValidationError("numero_invitados debe ser mayor a cero.")
    return Decimal(numero_invitados) / Decimal(porciones_base)


def _cantidad_a_comprar(cantidad_neta: Decimal, porcentaje_merma: Decimal) -> Decimal:
    """Aplica el margen de merma nativo del insumo a una cantidad neta.

    porcentaje_merma=0.12 -> hay que comprar cantidad_neta / 0.88 para que,
    tras perder 12% en cocción/limpieza, quede exactamente cantidad_neta.
    """
    if porcentaje_merma >= 1:
        raise MermaInvalidaError(
            "El porcentaje de merma no puede ser mayor o igual a 100%."
        )
    factor_merma = Decimal("1") - porcentaje_merma
    return cantidad_neta / factor_merma


def escalar_ingredientes_receta(receta, numero_invitados: int):
    """Devuelve una lista de tuplas (insumo, cantidad_escalada, unidad) para
    una `RecetaMaestra` dada, escalada a `numero_invitados` comensales.
    """
    factor = calcular_factor_escala(receta.porciones_base, numero_invitados)
    resultado = []
    for ingrediente in receta.ingredientes.select_related("insumo").all():
        cantidad_escalada = (ingrediente.cantidad * factor).quantize(
            _CANTIDAD_Q, rounding=ROUND_HALF_UP
        )
        resultado.append((ingrediente.insumo, cantidad_escalada, ingrediente.unidad_medida))
    return resultado


def explosion_insumos_evento(evento) -> list[LineaInsumoConsolidada]:
    """Genera la lista de compras consolidada para un `Evento`:

    - Recorre cada receta seleccionada en `evento.detalle_menu`.
    - Escala sus ingredientes según `evento.numero_invitados`.
    - Consolida (suma) cantidades del mismo insumo entre distintas recetas.
    - Aplica el margen de merma nativo de cada insumo.
    - Calcula el costo total de compra por insumo.

    Devuelve una lista ordenada alfabéticamente por nombre de insumo.
    """
    consolidado: dict[int, LineaInsumoConsolidada] = {}

    detalles = evento.detalle_menu.select_related("receta").all()
    for detalle in detalles:
        receta = detalle.receta
        for insumo, cantidad_escalada, unidad in escalar_ingredientes_receta(
            receta, evento.numero_invitados
        ):
            if insumo.id not in consolidado:
                consolidado[insumo.id] = LineaInsumoConsolidada(
                    insumo_id=insumo.id,
                    nombre=insumo.nombre,
                    unidad_medida=unidad,
                    cantidad_neta=Decimal("0"),
                    porcentaje_merma=insumo.porcentaje_merma,
                    cantidad_a_comprar=Decimal("0"),
                    costo_unitario=insumo.costo_unitario,
                    costo_total=Decimal("0"),
                    recetas_origen=[],
                )
            linea = consolidado[insumo.id]
            linea.cantidad_neta += cantidad_escalada
            if receta.nombre not in linea.recetas_origen:
                linea.recetas_origen.append(receta.nombre)

    lineas = []
    for linea in consolidado.values():
        linea.cantidad_neta = linea.cantidad_neta.quantize(
            _CANTIDAD_Q, rounding=ROUND_HALF_UP
        )
        linea.cantidad_a_comprar = _cantidad_a_comprar(
            linea.cantidad_neta, linea.porcentaje_merma
        ).quantize(_CANTIDAD_Q, rounding=ROUND_HALF_UP)
        linea.costo_total = (linea.cantidad_a_comprar * linea.costo_unitario).quantize(
            _COSTO_Q, rounding=ROUND_HALF_UP
        )
        lineas.append(linea)

    lineas.sort(key=lambda l: l.nombre)
    return lineas


def costo_total_evento(evento) -> Decimal:
    """Costo total de insumos (food cost puro) para un evento, sumando el
    costo de compra de toda la lista consolidada. Insumo base para el
    Cotizador por Volumen del Módulo F."""
    lineas = explosion_insumos_evento(evento)
    total = sum((l.costo_total for l in lineas), Decimal("0"))
    return total.quantize(_COSTO_Q, rounding=ROUND_HALF_UP)


def cotizar_evento(evento) -> dict:
    """Cotizador por Volumen (Módulo F): calcula el precio por persona y el
    precio total del evento repartiendo los costos fijos de transporte y
    personal base entre el número de invitados — a menor volumen, mayor
    precio unitario para absorber esos costos fijos entre menos comensales.

    Delega el cálculo en `ConfiguracionCotizador.cotizar()` (una fila de
    configuración por empresa); lanza `ValidationError` si la empresa
    todavía no la tiene configurada."""
    configuracion = getattr(evento.empresa, "configuracion_cotizador", None)
    if configuracion is None:
        raise ValidationError(
            "La empresa no tiene configurado el Cotizador por Volumen "
            "(falta crear su ConfiguracionCotizador)."
        )
    return configuracion.cotizar(evento.numero_invitados)
