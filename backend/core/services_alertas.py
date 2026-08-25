"""
Módulo F: alertas automáticas por correo cuando se acerca la fecha límite de
un abono del Esquema de Cobro 50/30/20 (`AbonoEvento`).

Sin pasarela de pago real -por decisión del usuario-: esto NUNCA cobra nada,
solo manda un correo de recordatorio para que el pago se siga gestionando
por fuera (transferencia, terminal, efectivo) y luego se marque a mano con
"Marcar como pagado" (ver `AbonoEvento.marcar_pagado`).

Render (plan gratuito) no ofrece cron/scheduler, así que el envío nunca
depende de que un job en segundo plano "pase" a revisar la fecha: esta
función se dispara:
  1) A mano, con el botón "Enviar alertas pendientes" de Finanzas.jsx
     (`POST /api/abonos/enviar-alertas-pendientes/`, requiere sesión).
  2) De forma opcional y verdaderamente automática, apuntando un servicio
     externo gratuito de cron (ej. cron-job.org) una vez al día a
     `GET /api/cron/alertas-abonos/?clave=<CRON_ALERTAS_SECRET>`.

Cada abono manda como máximo UN correo (`AbonoEvento.alerta_enviada`) para
no bombardear al cliente cada vez que se dispara el chequeo.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import AbonoEvento


def abonos_pendientes_de_alerta(empresa_id=None):
    """Abonos no pagados, no vencidos, dentro de su ventana de alerta
    (`empresa.dias_anticipacion_alerta_abono` días antes de `fecha_limite`)
    y a los que todavía no se les mandó el correo."""
    hoy = timezone.localdate()
    qs = AbonoEvento.objects.select_related(
        "esquema__evento__cliente", "esquema__evento__empresa"
    ).filter(pagado=False, alerta_enviada=False, fecha_limite__gte=hoy)
    if empresa_id:
        qs = qs.filter(esquema__evento__empresa_id=empresa_id)
    # `proximo_a_vencer` ya filtra pagado/vencido otra vez, pero además aplica
    # el umbral de días personalizable por empresa (no se puede expresar
    # directamente como filtro de queryset porque depende de un campo de una
    # relación calculada en Python, no de la base de datos).
    return [abono for abono in qs if abono.proximo_a_vencer]


def _cuerpo_correo(abono) -> str:
    evento = abono.esquema.evento
    return (
        f"Hola {evento.cliente.nombre},\n\n"
        f"Este es un recordatorio de que se acerca la fecha límite de pago de tu "
        f"{abono.get_tipo_display()} del evento \"{evento.nombre_evento}\" "
        f"({evento.fecha.strftime('%d/%m/%Y')}):\n\n"
        f"  Monto: ${abono.monto:,.2f} MXN\n"
        f"  Fecha límite: {abono.fecha_limite.strftime('%d/%m/%Y')}\n\n"
        "Si ya realizaste este pago, por favor ignora este correo y avísanos "
        "para registrarlo en el sistema. Cualquier duda, contáctanos.\n\n"
        f"{evento.empresa.nombre_comercial}"
    )


def enviar_alertas_abonos_por_vencer(empresa_id=None) -> dict:
    """Recorre los abonos pendientes de alerta y les manda un correo de
    recordatorio (al cliente si tiene email capturado, con copia al correo
    de contacto de la banquetera si también lo tiene). Un abono sin NINGÚN
    correo disponible se omite -no se marca como enviado, para que se
    revise el dato faltante y se reintente en el siguiente chequeo-.
    Devuelve un resumen listo para mostrarse en pantalla o en la respuesta
    del endpoint."""
    enviados, omitidos = [], []
    for abono in abonos_pendientes_de_alerta(empresa_id):
        evento = abono.esquema.evento
        destinatarios = []
        if evento.cliente.email:
            destinatarios.append(evento.cliente.email)
        if evento.empresa.email_contacto:
            destinatarios.append(evento.empresa.email_contacto)
        if not destinatarios:
            omitidos.append(abono.id)
            continue

        send_mail(
            subject=f"Recordatorio de pago próximo a vencer — {evento.nombre_evento}",
            message=_cuerpo_correo(abono),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinatarios,
            fail_silently=False,
        )
        abono.alerta_enviada = True
        abono.fecha_alerta_enviada = timezone.now()
        abono.save(update_fields=["alerta_enviada", "fecha_alerta_enviada"])
        enviados.append(abono.id)

    return {"enviados": enviados, "omitidos_sin_correo": omitidos}
