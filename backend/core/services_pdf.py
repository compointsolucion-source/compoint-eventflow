"""
Módulo D: generación del PDF de "Cargo por Daños".

A partir de los `RegistroRoturas` capturados en el Control de Retorno de
Bodega (ver `Bodega.jsx` / `RegistroRoturasViewSet`), arma un documento
formal que se le entrega al cliente o al Event Planner para justificar el
descuento del depósito en garantía. El monto de cada línea ya viene
calculado y protegido desde `RegistroRoturas.save()` (cantidad_rota x
costo_reposicion_unitario del artículo) — este módulo solo se encarga de
darle formato de documento, nunca recalcula ni permite capturar montos.
"""

from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#0f172a")
TEAL = colors.HexColor("#14b8a6")
SLATE = colors.HexColor("#64748b")


def _formato_moneda(valor) -> str:
    numero = Decimal(valor)
    return f"${numero:,.2f} MXN"


def generar_pdf_cargo_danos(evento) -> bytes:
    """Arma el PDF de "Cargo por Daños" de `evento` a partir de sus
    `registros_rotura`. Lanza `ValidationError` si el evento no tiene
    ninguna rotura registrada (no tiene caso generar un documento vacío)."""
    registros = list(
        evento.registros_rotura.select_related("articulo").order_by("-fecha_registro")
    )
    if not registros:
        raise ValidationError(
            "Este evento no tiene roturas o extravíos registrados: no hay nada que cobrar."
        )

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=f"Cargo por Daños - {evento.nombre_evento}",
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloCompoint", parent=estilos["Heading1"], textColor=NAVY, fontSize=20, spaceAfter=2,
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloCompoint", parent=estilos["Normal"], textColor=TEAL, fontSize=12,
        spaceAfter=14, fontName="Helvetica-Bold",
    )
    estilo_etiqueta = ParagraphStyle(
        "EtiquetaCompoint", parent=estilos["Normal"], textColor=SLATE, fontSize=9,
    )
    estilo_valor = ParagraphStyle(
        "ValorCompoint", parent=estilos["Normal"], textColor=NAVY, fontSize=11, spaceAfter=6,
    )
    estilo_nota = ParagraphStyle(
        "NotaCompoint", parent=estilos["Normal"], textColor=SLATE, fontSize=8, spaceBefore=14,
    )

    empresa = evento.empresa
    elementos = [
        Paragraph(empresa.nombre_comercial or "COMPOINT EventFlow", estilo_titulo),
        Paragraph("Cargo por Daños — Control de Retorno de Bodega", estilo_subtitulo),
        Paragraph("Evento", estilo_etiqueta),
        Paragraph(evento.nombre_evento, estilo_valor),
        Paragraph("Fecha del evento", estilo_etiqueta),
        Paragraph(evento.fecha.strftime("%d/%m/%Y"), estilo_valor),
        Paragraph("Cliente", estilo_etiqueta),
        Paragraph(evento.cliente.nombre, estilo_valor),
        Paragraph("Sede", estilo_etiqueta),
        Paragraph(evento.sede.nombre, estilo_valor),
        Spacer(1, 8),
    ]

    # Las celdas se arman con Paragraph (no strings sueltos) para que el
    # texto largo -como "Registrado por"- haga salto de línea en vez de
    # desbordarse encima de la columna vecina.
    IZQUIERDA, CENTRO, DERECHA = 0, 1, 2

    def _estilo_celda(alineacion, encabezado=False, total=False):
        return ParagraphStyle(
            f"Celda_{alineacion}_{encabezado}_{total}",
            parent=estilos["Normal"],
            fontSize=9,
            leading=11,
            alignment=alineacion,
            textColor=colors.white if encabezado else NAVY,
            fontName="Helvetica-Bold" if (encabezado or total) else "Helvetica",
        )

    est_articulo = _estilo_celda(IZQUIERDA)
    est_cantidad = _estilo_celda(CENTRO)
    est_costo = _estilo_celda(DERECHA)
    est_registrado_por = _estilo_celda(IZQUIERDA)
    est_encabezado_izq = _estilo_celda(IZQUIERDA, encabezado=True)
    est_encabezado_centro = _estilo_celda(CENTRO, encabezado=True)
    est_encabezado_derecha = _estilo_celda(DERECHA, encabezado=True)
    est_total_label = _estilo_celda(DERECHA, total=True)
    est_total_monto = _estilo_celda(DERECHA, total=True)

    filas = [
        [
            Paragraph("Artículo", est_encabezado_izq),
            Paragraph("Cantidad", est_encabezado_centro),
            Paragraph("Costo de reposición", est_encabezado_derecha),
            Paragraph("Registrado por", est_encabezado_izq),
        ]
    ]
    total = Decimal("0.00")
    for registro in registros:
        filas.append(
            [
                Paragraph(registro.articulo.nombre, est_articulo),
                Paragraph(str(registro.cantidad_rota), est_cantidad),
                Paragraph(_formato_moneda(registro.costo_reposicion), est_costo),
                Paragraph(registro.registrado_por or "—", est_registrado_por),
            ]
        )
        total += registro.costo_reposicion
    filas.append(
        [
            "",
            "",
            Paragraph("Total a descontar del depósito", est_total_label),
            Paragraph(_formato_moneda(total), est_total_monto),
        ]
    )

    tabla = Table(filas, colWidths=[52 * mm, 20 * mm, 48 * mm, 40 * mm])
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
                ("LINEABOVE", (0, -1), (-1, -1), 1, NAVY),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    elementos.append(tabla)

    elementos.append(
        Paragraph(
            "Este documento respalda el descuento aplicado sobre el depósito en garantía "
            "por artículos rotos o extraviados durante el evento, según el conteo de retorno "
            "realizado por el Capitán de Meseros. El costo de reposición de cada artículo se "
            "calcula automáticamente a partir del catálogo de inventario de la banquetera.",
            estilo_nota,
        )
    )
    elementos.append(
        Paragraph(
            f"Generado el {timezone.localtime().strftime('%d/%m/%Y %H:%M')} hrs.",
            estilo_nota,
        )
    )

    documento.build(elementos)
    return buffer.getvalue()
