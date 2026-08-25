"""
Módulo B: bloqueo y sugerencia de fechas para Pruebas de Menú.

Un viernes o sábado es un día de "alta operación" para la banquetera (son
los días típicos de boda/evento, con el chef y la cocina ocupados
ejecutando eventos reales). Si esa fecha específica ya tiene un evento que
la ocupa (`Evento.bloquea_fecha`: un Apartado vigente o un Confirmado —
ver `core/models.py` y `core/services_capacidad.py`), no se debe agendar
ahí una prueba de menú. Entre semana no hay restricción, y un viernes o
sábado sin eventos que lo ocupen tampoco la tiene: la regla es sobre la
carga real de trabajo de ese día, no sobre el día de la semana en sí.

Cuando una fecha propuesta no es válida, se sugieren automáticamente las
próximas fechas cercanas que sí estén libres.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError

from .services_capacidad import eventos_que_bloquean_fecha

DIAS_ALTA_OPERACION = (4, 5)  # weekday(): 0=lunes ... 4=viernes, 5=sábado
NOMBRES_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def fecha_prueba_disponible(empresa_id, fecha) -> bool:
    """True si `fecha` se puede usar para una prueba de menú: cualquier día
    entre semana siempre está disponible; un viernes/sábado solo si esa
    empresa no tiene ya un evento que bloquee esa fecha."""
    if fecha.weekday() not in DIAS_ALTA_OPERACION:
        return True
    return not eventos_que_bloquean_fecha(empresa_id, fecha)


def sugerir_fechas_disponibles(empresa_id, fecha_deseada, cantidad=3, dias_a_revisar=60):
    """Busca hacia adelante, día por día a partir de `fecha_deseada`, las
    próximas `cantidad` fechas disponibles para agendar una prueba de menú."""
    disponibles = []
    fecha = fecha_deseada
    revisadas = 0
    while len(disponibles) < cantidad and revisadas < dias_a_revisar:
        fecha = fecha + timedelta(days=1)
        revisadas += 1
        if fecha_prueba_disponible(empresa_id, fecha):
            disponibles.append(fecha)
    return disponibles


def validar_fecha_prueba_menu(empresa_id, fecha):
    """Lanza `django.core.exceptions.ValidationError` si `fecha` cae en un
    viernes/sábado de alta operación ya ocupado por otro evento, incluyendo
    en el mensaje un par de fechas cercanas que sí están libres."""
    if fecha_prueba_disponible(empresa_id, fecha):
        return

    nombre_dia = NOMBRES_DIA[fecha.weekday()]
    sugerencias = sugerir_fechas_disponibles(empresa_id, fecha)
    sugerencias_texto = (
        ", ".join(f.strftime("%d/%m/%Y") for f in sugerencias)
        if sugerencias
        else "no se encontraron fechas libres en los próximos 60 días"
    )
    raise ValidationError(
        {
            "fecha_prueba": (
                f"El {nombre_dia} {fecha.strftime('%d/%m/%Y')} ya tiene un evento "
                "confirmado o apartado ese día (día de alta operación): la cocina "
                "y el chef están comprometidos. Fechas cercanas disponibles: "
                f"{sugerencias_texto}."
            )
        }
    )
