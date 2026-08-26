from django.contrib import admin

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


@admin.register(EmpresaBanquetera)
class EmpresaBanqueteraAdmin(admin.ModelAdmin):
    # Lista corta y legible (sin scroll horizontal): solo lo que sirve para
    # identificar/ubicar una empresa de un vistazo. Los parámetros de cada
    # módulo (Semáforo, Alertas, Pruebas de Menú) se ven organizados por
    # secciones al entrar al detalle — ver `fieldsets` abajo — y, para el
    # uso del día a día, es más simple editarlos desde la pantalla
    # "Configuración" dentro de la propia app (no requiere entrar aquí).
    list_display = ("nombre_comercial", "email_contacto", "telefono_contacto", "activa")
    search_fields = ("nombre_comercial", "razon_social", "rfc")
    fieldsets = (
        (
            "Datos de la empresa",
            {
                "description": (
                    "Recomendado: para cambios del día a día usa la pantalla "
                    "\"Configuración\" dentro de COMPOINT EventFlow — es más simple "
                    "y no requiere entrar al admin. Este panel queda como respaldo técnico."
                ),
                "fields": (
                    "nombre_comercial",
                    "razon_social",
                    "rfc",
                    "telefono_contacto",
                    "email_contacto",
                    "direccion_bodega_central",
                    "activa",
                ),
            },
        ),
        (
            "Semáforo de Fechas (Módulo A)",
            {
                "description": (
                    "Plazos automáticos para que un Prospecto o un Apartado se "
                    "marquen como vencidos."
                ),
                "fields": ("horas_vencimiento_prospecto", "dias_habiles_limite_anticipo"),
            },
        ),
        (
            "Alertas de abonos por correo (Módulo F)",
            {
                "description": (
                    "Con cuánta anticipación se avisa por correo que un abono está "
                    "por vencer."
                ),
                "fields": ("dias_anticipacion_alerta_abono",),
            },
        ),
        (
            "Pruebas de Menú (Módulo B)",
            {
                "description": (
                    "Costo por cada asistente que exceda el límite de cortesía (4 "
                    "personas). Se cobra automáticamente al agendar la prueba."
                ),
                "fields": ("costo_extra_por_asistente_prueba_menu",),
            },
        ),
    )


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
        "vencido_display",
        "tipo_cliente",
        "numero_invitados",
        "sede",
        "empresa",
    )
    list_filter = ("estado_semaforo", "tipo_cliente", "empresa", "sede")
    search_fields = ("nombre_evento", "cliente__nombre")
    readonly_fields = ("link_planner_copiable", "vencido_display")
    inlines = [DetalleMenuEventoInline, PruebaMenuInline]

    @admin.display(description="Link del Portal del Event Planner (cópialo y mándalo por WhatsApp/correo)")
    def link_planner_copiable(self, obj):
        return obj.link_planner

    @admin.display(description="¿Vencido? (Módulo A)", boolean=True)
    def vencido_display(self, obj):
        return obj.vencido


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


@admin.register(PersonalEventual)
class PersonalEventualAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rol_principal", "telefono", "activo", "empresa")
    list_filter = ("rol_principal", "activo", "empresa")
    search_fields = ("nombre", "telefono", "email")


class PostulacionInline(admin.TabularInline):
    model = Postulacion
    extra = 0
    fields = ("personal", "estado", "postulado_en")
    readonly_fields = ("postulado_en",)


@admin.register(VacanteEvento)
class VacanteEventoAdmin(admin.ModelAdmin):
    list_display = (
        "evento",
        "rol",
        "cantidad_requerida",
        "cantidad_aceptada",
        "cubierta",
        "tarifa_por_turno",
    )
    list_filter = ("rol", "evento")
    inlines = [PostulacionInline]


@admin.register(Postulacion)
class PostulacionAdmin(admin.ModelAdmin):
    list_display = ("personal", "vacante", "estado", "postulado_en")
    list_filter = ("estado",)
    search_fields = ("personal__nombre",)


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("postulacion", "codigo_verificacion", "hora_checkin", "asistio", "confirmado_por")
    readonly_fields = ("codigo_verificacion",)
    actions = ["confirmar_asistencia"]

    @admin.action(description="Confirmar asistencia (check-in) ahora")
    def confirmar_asistencia(self, request, queryset):
        for check_in in queryset:
            check_in.confirmar(confirmado_por=request.user.get_username())


@admin.register(ConfiguracionCotizador)
class ConfiguracionCotizadorAdmin(admin.ModelAdmin):
    list_display = ("empresa", "costo_base_por_persona", "costos_fijos_transporte_personal")


class AbonoEventoInline(admin.TabularInline):
    model = AbonoEvento
    extra = 0
    fields = ("tipo", "porcentaje", "monto", "fecha_limite", "pagado", "fecha_pago")
    readonly_fields = ("porcentaje", "monto")


@admin.register(EsquemaPagoEvento)
class EsquemaPagoEventoAdmin(admin.ModelAdmin):
    list_display = ("evento", "monto_total", "generado_en", "actualizado_en")
    inlines = [AbonoEventoInline]
    actions = ["generar_o_actualizar_abonos"]

    @admin.action(description="Generar/actualizar abonos 50/30/20")
    def generar_o_actualizar_abonos(self, request, queryset):
        for esquema in queryset:
            esquema.generar_o_actualizar_abonos()


@admin.register(AbonoEvento)
class AbonoEventoAdmin(admin.ModelAdmin):
    list_display = (
        "esquema", "tipo", "monto", "fecha_limite", "pagado", "vencido",
        "alerta_enviada",
    )
    list_filter = ("tipo", "pagado", "alerta_enviada")
    actions = ["marcar_como_pagado", "enviar_alertas_de_abonos_por_vencer"]

    @admin.action(description="Marcar como pagado")
    def marcar_como_pagado(self, request, queryset):
        for abono in queryset:
            abono.marcar_pagado()

    @admin.action(
        description=(
            "Enviar alertas de abonos por vencer (Módulo F) — revisa TODOS "
            "los abonos pendientes de la banquetera, no solo los seleccionados"
        )
    )
    def enviar_alertas_de_abonos_por_vencer(self, request, queryset):
        from .services_alertas import enviar_alertas_abonos_por_vencer

        resultado = enviar_alertas_abonos_por_vencer()
        self.message_user(
            request,
            f"Correos enviados: {len(resultado['enviados'])}. "
            f"Omitidos por no tener correo capturado: {len(resultado['omitidos_sin_correo'])}.",
        )
