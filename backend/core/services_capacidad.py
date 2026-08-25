"""
Módulo A: bloqueo automático de fechas por capacidad de loza/personal.

Este módulo NO depende de un cron/scheduler externo (el plan gratuito de
Render no lo ofrece): el vencimiento de Prospectos/Apartados se calcula al
vuelo en `Evento.vencido`/`Evento.bloquea_fecha` (ver `core/models.py`)
comparando la fecha/hora actual contra los campos guardados, y las
validaciones de este módulo se calculan al vuelo cada vez que se intenta
guardar un evento, un ítem de menú o una vacante: se suma la demanda de
TODOS los eventos de esa fecha que sigan "bloqueando" esa fecha (un
Apartado vigente o un Confirmado; un Prospecto nunca bloquea por sí solo,
y un Apartado/Confirmado ya vencido tampoco).

Si el administrador ya resolvió el faltante por fuera (renta de equipo
externo, personal extra), puede marcar `Evento.autorizado_proveedor_externo`
para que estas validaciones dejen pasar ese evento.
"""

from django.core.exceptions import ValidationError


def eventos_que_bloquean_fecha(empresa_id, fecha, excluir_evento_id=None):
    """Eventos de `empresa_id` en `fecha` que cuentan para el bloqueo de
    capacidad (ver `Evento.bloquea_fecha`), excluyendo opcionalmente uno."""
    from .models import Evento

    qs = Evento.objects.filter(empresa_id=empresa_id, fecha=fecha)
    if excluir_evento_id:
        qs = qs.exclude(pk=excluir_evento_id)
    return [evento for evento in qs if evento.bloquea_fecha]


def validar_capacidad_equipo(evento, tiempo_menu_extra=None):
    """Valida que el equipo (loza/cristalería/cubertería/mobiliario) que
    harían falta ese día -sumando este evento más todos los que ya bloquean
    esa fecha- no rebase el stock disponible en bodega central.

    `tiempo_menu_extra` permite validar ANTES de guardar un nuevo
    `DetalleMenuEvento` (se previsualiza su efecto sin haberlo guardado).

    Lanza `django.core.exceptions.ValidationError` si algún artículo queda
    saturado y el evento no tiene autorizada la renta externa."""
    from .models import InventarioEquipo, _calcular_cantidades_equipo

    if evento.autorizado_proveedor_externo:
        return
    # Un Prospecto (o un Apartado/Confirmado ya vencido) no bloquea por sí
    # solo: no tiene caso validar capacidad para algo que no la reserva.
    if not evento.vencido and evento.estado_semaforo not in (
        evento.EstadoSemaforo.APARTADO,
        evento.EstadoSemaforo.CONFIRMADO,
    ):
        return
    if evento.vencido:
        return

    total_por_articulo = dict(_calcular_cantidades_equipo(evento, tiempo_menu_extra))
    for otro in eventos_que_bloquean_fecha(
        evento.empresa_id, evento.fecha, excluir_evento_id=evento.pk
    ):
        for articulo_id, cantidad in _calcular_cantidades_equipo(otro).items():
            total_por_articulo[articulo_id] = total_por_articulo.get(articulo_id, 0) + cantidad

    if not total_por_articulo:
        return

    articulos = InventarioEquipo.objects.filter(id__in=total_por_articulo.keys())
    saturados = []
    for articulo in articulos:
        requerido = total_por_articulo.get(articulo.id, 0)
        if requerido > articulo.stock_disponible:
            saturados.append(
                f"{articulo.nombre} (se necesitan {requerido}, hay "
                f"{articulo.stock_disponible} en bodega)"
            )
    if saturados:
        raise ValidationError(
            f"El {evento.fecha.strftime('%d/%m/%Y')} ya está saturado de "
            "inventario entre los eventos de esa fecha: " + "; ".join(saturados) +
            ". Marca 'autorizado renta de equipo externo' en el evento si ya "
            "lo resolviste por fuera."
        )


def validar_capacidad_personal(evento, rol_extra=None, cantidad_extra=0, excluir_vacante_id=None):
    """Valida que el personal requerido ese día -sumando este evento más
    todos los que ya bloquean esa fecha, por rol- no rebase el total de
    personal activo de ese rol en la bolsa de trabajo.

    `rol_extra`/`cantidad_extra` permiten validar ANTES de guardar una
    `VacanteEvento` nueva o modificada; `excluir_vacante_id` evita contar
    dos veces la vacante que se está editando.

    Lanza `django.core.exceptions.ValidationError` si algún rol queda
    saturado y el evento no tiene autorizada la cobertura externa."""
    from .models import PersonalEventual

    if evento.autorizado_proveedor_externo:
        return
    if not evento.vencido and evento.estado_semaforo not in (
        evento.EstadoSemaforo.APARTADO,
        evento.EstadoSemaforo.CONFIRMADO,
    ):
        return
    if evento.vencido:
        return

    requerido_por_rol = {}
    for vacante in evento.vacantes.exclude(pk=excluir_vacante_id) if excluir_vacante_id else evento.vacantes.all():
        requerido_por_rol[vacante.rol] = requerido_por_rol.get(vacante.rol, 0) + vacante.cantidad_requerida
    if rol_extra:
        requerido_por_rol[rol_extra] = requerido_por_rol.get(rol_extra, 0) + cantidad_extra

    for otro in eventos_que_bloquean_fecha(
        evento.empresa_id, evento.fecha, excluir_evento_id=evento.pk
    ):
        for vacante in otro.vacantes.all():
            requerido_por_rol[vacante.rol] = requerido_por_rol.get(vacante.rol, 0) + vacante.cantidad_requerida

    if not requerido_por_rol:
        return

    saturados = []
    for rol, requerido in requerido_por_rol.items():
        disponible = PersonalEventual.objects.filter(
            empresa_id=evento.empresa_id, rol_principal=rol, activo=True
        ).count()
        if requerido > disponible:
            saturados.append(
                f"{rol} (se necesitan {requerido}, hay {disponible} activos en la bolsa de trabajo)"
            )
    if saturados:
        raise ValidationError(
            f"El {evento.fecha.strftime('%d/%m/%Y')} ya está saturado de "
            "personal entre los eventos de esa fecha: " + "; ".join(saturados) +
            ". Marca 'autorizado renta de equipo externo' en el evento si ya "
            "conseguiste personal extra por fuera."
        )
