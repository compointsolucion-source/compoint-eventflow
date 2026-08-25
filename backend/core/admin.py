from django.contrib import admin

from .models import (
    Cliente,
    DetalleListaCarga,
    DetalleMenuEvento,
    EmpresaBanquetera,
    Evento,
    IngredienteReceta,
    InventarioEquipo,
    Insumo,
    ListaCargaEvento,
    PruebaMenu,
    RecetaMaestra,
    RegistroRoturas,
    RequerimientoEquipoTiempo,
    SedeEvento,
)


@admin.register(EmpresaBanquetera)
class EmpresaBanqueteraAdmin(admin.ModelAdmin):
    list_display = ("nombre_comercial", "email_contacto", "activa", "fecha_alta")
    search_fields = ("nombre_comercial", "razon_social", "rfc")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "telefono", "empresa")
    list_filter = ("tipo", "empresa")
    search_fields = ("nombre", "telefono", "email")


@admin.register(SedeEvento)
class SedeEventoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "capacidad_maxima_invitados")
    list_filter = ("empresa",)


class DetalleMenuEventoInline(admin.TabularInline):
    model = DetalleMenuEvento
    extra = 0


class PruebaMenuInline(admin.TabularInline):
    model = PruebaMenu
    extra = 0
    fields = ("fecha_prueba", "asistentes", "aprobado")


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_evento",
        "fecha",
        "estado_semaforo",
        "tipo_cliente",
        "numero_invitados",
        "sede",
        "empresa",
    )
    list_filter = ("estado_semaforo", "tipo_cliente", "empresa", "sede")
    search_fields = ("nombre_evento", "cliente__nombre")
    inlines = [DetalleMenuEventoInline, PruebaMenuInline]


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad_base", "costo_unitario", "porcentaje_merma", "empresa")
    list_filter = ("empresa", "unidad_base")
    search_fields = ("nombre",)


class IngredienteRecetaInline(admin.TabularInline):
    model = IngredienteReceta
    extra = 1


@admin.register(RecetaMaestra)
class RecetaMaestraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tiempo_menu", "porciones_base", "costo_estimado", "empresa")
    list_filter = ("tiempo_menu", "empresa")
    search_fields = ("nombre",)
    inlines = [IngredienteRecetaInline]


@admin.register(PruebaMenu)
class PruebaMenuAdmin(admin.ModelAdmin):
    list_display = ("evento", "fecha_prueba", "asistentes", "aprobado", "cobro_adicional_generado")
    list_filter = ("aprobado",)


@admin.register(InventarioEquipo)
class InventarioEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo", "stock_disponible", "costo_reposicion_unitario", "empresa")
    list_filter = ("tipo", "empresa")


@admin.register(RegistroRoturas)
class RegistroRoturasAdmin(admin.ModelAdmin):
    list_display = ("evento", "articulo", "cantidad_rota", "costo_reposicion", "fecha_registro")
    list_filter = ("evento",)


@admin.register(RequerimientoEquipoTiempo)
class RequerimientoEquipoTiempoAdmin(admin.ModelAdmin):
    list_display = ("tiempo_menu", "articulo", "cantidad_por_invitado", "empresa")
    list_filter = ("empresa", "tiempo_menu")


class DetalleListaCargaInline(admin.TabularInline):
    model = DetalleListaCarga
    extra = 0
    readonly_fields = ("cantidad_a_cargar",)
    fields = ("articulo", "cantidad_requerida", "cantidad_a_cargar", "surtido")


@admin.register(ListaCargaEvento)
class ListaCargaEventoAdmin(admin.ModelAdmin):
    list_display = ("evento", "generada_en", "conteo_retorno_completado")
    inlines = [DetalleListaCargaInline]
    actions = ["recalcular_detalles"]

    @admin.action(description="Recalcular detalles según menú e invitados actuales")
    def recalcular_detalles(self, request, queryset):
        for lista in queryset:
            lista.generar_o_actualizar_detalles()
