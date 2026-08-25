"""
Comando de management para poblar la base de datos con datos de ejemplo
realistas, útiles para probar el sistema y el dashboard sin capturar todo
manualmente.

Uso:
    python manage.py seed_demo
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    Cliente,
    DetalleMenuEvento,
    EmpresaBanquetera,
    Evento,
    IngredienteReceta,
    InventarioEquipo,
    Insumo,
    ListaCargaEvento,
    PruebaMenu,
    RecetaMaestra,
    RequerimientoEquipoTiempo,
    SedeEvento,
    TiempoMenu,
)


class Command(BaseCommand):
    help = "Crea datos de demostración para COMPOINT EventFlow."

    def handle(self, *args, **options):
        if EmpresaBanquetera.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Ya existen datos. Borra la base (o usa una nueva) si quieres re-sembrar."
                )
            )
            return

        empresa = EmpresaBanquetera.objects.create(
            nombre_comercial="Banquetes Sincronía",
            razon_social="Banquetes Sincronía S.A. de C.V.",
            email_contacto="operaciones@banquetessincronia.mx",
            telefono_contacto="55-1234-5678",
            direccion_bodega_central="Av. Industria 450, CDMX",
        )

        # --- Clientes ---
        cliente_planner = Cliente.objects.create(
            empresa=empresa, nombre="Ana Torres", telefono="55-1111-2222",
            email="ana@eventosdeluxe.mx", tipo=Cliente.TipoCliente.PLANNER,
            nombre_agencia_planner="Eventos Deluxe",
        )
        cliente_directo = Cliente.objects.create(
            empresa=empresa, nombre="Familia Ramírez", telefono="55-3333-4444",
            email="ramirez.boda@gmail.com", tipo=Cliente.TipoCliente.DIRECTO,
        )
        cliente_prospecto = Cliente.objects.create(
            empresa=empresa, nombre="Grupo Corporativo Delta", telefono="55-5555-6666",
            tipo=Cliente.TipoCliente.DIRECTO,
        )

        # --- Sedes ---
        sede_hacienda = SedeEvento.objects.create(
            empresa=empresa, nombre="Hacienda Los Encinos",
            direccion="Km 12 Carretera Federal, Edo. Méx.",
            notas_acceso_carga="Entrada de camiones por la parte trasera, altura máx. 3.5m",
            capacidad_maxima_invitados=400,
        )
        sede_jardin = SedeEvento.objects.create(
            empresa=empresa, nombre="Jardín Villa Toscana",
            direccion="Blvd. del Sol 210, CDMX",
            capacidad_maxima_invitados=250,
        )
        sede_salon = SedeEvento.objects.create(
            empresa=empresa, nombre="Salón Corporativo Delta Tower",
            direccion="Reforma 500, Piso 20, CDMX",
            capacidad_maxima_invitados=150,
        )

        # --- Insumos (con distintos % de merma) ---
        insumos = {
            "res": Insumo.objects.create(
                empresa=empresa, nombre="Filete de res", unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
                costo_unitario=Decimal("220.00"), porcentaje_merma=Decimal("0.15"),
            ),
            "pollo": Insumo.objects.create(
                empresa=empresa, nombre="Pechuga de pollo", unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
                costo_unitario=Decimal("95.00"), porcentaje_merma=Decimal("0.10"),
            ),
            "salmon": Insumo.objects.create(
                empresa=empresa, nombre="Salmón fresco", unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
                costo_unitario=Decimal("280.00"), porcentaje_merma=Decimal("0.08"),
            ),
            "champinon": Insumo.objects.create(
                empresa=empresa, nombre="Champiñón", unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
                costo_unitario=Decimal("60.00"), porcentaje_merma=Decimal("0.05"),
            ),
            "papa": Insumo.objects.create(
                empresa=empresa, nombre="Papa cambray", unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
                costo_unitario=Decimal("18.00"), porcentaje_merma=Decimal("0.05"),
            ),
            "vino_tinto": Insumo.objects.create(
                empresa=empresa, nombre="Vino tinto (copeo)", unidad_base=Insumo.UnidadMedida.LITROS,
                costo_unitario=Decimal("150.00"), porcentaje_merma=Decimal("0.00"),
            ),
            "chocolate": Insumo.objects.create(
                empresa=empresa, nombre="Chocolate 70%", unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
                costo_unitario=Decimal("210.00"), porcentaje_merma=Decimal("0.02"),
            ),
        }

        # --- Recetas (base 10 porciones) ---
        receta_filete = RecetaMaestra.objects.create(
            empresa=empresa, nombre="Filete al vino tinto con papas cambray",
            tiempo_menu="FUERTE", porciones_base=10, costo_estimado=Decimal("2500.00"),
        )
        IngredienteReceta.objects.create(receta=receta_filete, insumo=insumos["res"], cantidad=Decimal("1.8"), unidad_medida="KG")
        IngredienteReceta.objects.create(receta=receta_filete, insumo=insumos["vino_tinto"], cantidad=Decimal("0.5"), unidad_medida="L")
        IngredienteReceta.objects.create(receta=receta_filete, insumo=insumos["papa"], cantidad=Decimal("2.0"), unidad_medida="KG")

        receta_pollo = RecetaMaestra.objects.create(
            empresa=empresa, nombre="Pechuga rellena de champiñón",
            tiempo_menu="FUERTE", porciones_base=10, costo_estimado=Decimal("1400.00"),
        )
        IngredienteReceta.objects.create(receta=receta_pollo, insumo=insumos["pollo"], cantidad=Decimal("2.2"), unidad_medida="KG")
        IngredienteReceta.objects.create(receta=receta_pollo, insumo=insumos["champinon"], cantidad=Decimal("0.8"), unidad_medida="KG")

        receta_salmon = RecetaMaestra.objects.create(
            empresa=empresa, nombre="Salmón en costra de hierbas",
            tiempo_menu="FUERTE", porciones_base=10, costo_estimado=Decimal("3000.00"),
        )
        IngredienteReceta.objects.create(receta=receta_salmon, insumo=insumos["salmon"], cantidad=Decimal("2.0"), unidad_medida="KG")

        receta_postre = RecetaMaestra.objects.create(
            empresa=empresa, nombre="Volcán de chocolate",
            tiempo_menu="POSTRE", porciones_base=10, costo_estimado=Decimal("450.00"),
        )
        IngredienteReceta.objects.create(receta=receta_postre, insumo=insumos["chocolate"], cantidad=Decimal("1.0"), unidad_medida="KG")

        # --- Eventos (semáforo) ---
        hoy = date.today()

        evento_confirmado = Evento.objects.create(
            empresa=empresa, nombre_evento="Boda Ramírez-González",
            fecha=hoy + timedelta(days=25), numero_invitados=280,
            estado_semaforo=Evento.EstadoSemaforo.CONFIRMADO,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=cliente_directo, sede=sede_hacienda,
        )
        DetalleMenuEvento.objects.create(evento=evento_confirmado, receta=receta_filete)
        DetalleMenuEvento.objects.create(evento=evento_confirmado, receta=receta_postre)
        PruebaMenu.objects.create(
            evento=evento_confirmado, fecha_prueba=hoy + timedelta(days=5),
            asistentes=4, notas_chef="Término de la carne 3/4, salsa de vino más reducida.",
            aprobado=True,
        )

        evento_apartado = Evento.objects.create(
            empresa=empresa, nombre_evento="XV Años Sofía Martínez",
            fecha=hoy + timedelta(days=40), numero_invitados=150,
            estado_semaforo=Evento.EstadoSemaforo.APARTADO,
            tipo_cliente=Evento.TipoCliente.PLANNER,
            cliente=cliente_planner, sede=sede_jardin,
            fecha_limite_anticipo=hoy + timedelta(days=7),
        )
        DetalleMenuEvento.objects.create(evento=evento_apartado, receta=receta_pollo)
        DetalleMenuEvento.objects.create(evento=evento_apartado, receta=receta_postre)

        evento_prospecto = Evento.objects.create(
            empresa=empresa, nombre_evento="Convención Anual Grupo Delta",
            fecha=hoy + timedelta(days=60), numero_invitados=120,
            estado_semaforo=Evento.EstadoSemaforo.PROSPECTO,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=cliente_prospecto, sede=sede_salon,
            fecha_vencimiento_prospecto=timezone.now() + timedelta(hours=72),
        )
        DetalleMenuEvento.objects.create(evento=evento_prospecto, receta=receta_salmon)

        # --- Inventario de equipo ---
        plato_hondo = InventarioEquipo.objects.create(
            empresa=empresa, nombre="Plato hondo entrada", tipo=InventarioEquipo.TipoEquipo.VAJILLA,
            stock_disponible=450, costo_reposicion_unitario=Decimal("85.00"),
        )
        plato_plano = InventarioEquipo.objects.create(
            empresa=empresa, nombre="Plato plano fuerte", tipo=InventarioEquipo.TipoEquipo.VAJILLA,
            stock_disponible=450, costo_reposicion_unitario=Decimal("95.00"),
        )
        plato_postre = InventarioEquipo.objects.create(
            empresa=empresa, nombre="Plato de postre", tipo=InventarioEquipo.TipoEquipo.VAJILLA,
            stock_disponible=450, costo_reposicion_unitario=Decimal("65.00"),
        )
        copa_vino = InventarioEquipo.objects.create(
            empresa=empresa, nombre="Copa de vino", tipo=InventarioEquipo.TipoEquipo.CRISTALERIA,
            stock_disponible=380, costo_reposicion_unitario=Decimal("45.00"),
        )
        InventarioEquipo.objects.create(
            empresa=empresa, nombre="Tenedor trinche", tipo=InventarioEquipo.TipoEquipo.CUBERTERIA,
            stock_disponible=500, costo_reposicion_unitario=Decimal("25.00"),
        )

        # --- Requerimientos de equipo por tiempo de menú (Módulo D) ---
        RequerimientoEquipoTiempo.objects.create(
            empresa=empresa, tiempo_menu=TiempoMenu.FUERTE,
            articulo=plato_plano, cantidad_por_invitado=Decimal("1"),
        )
        RequerimientoEquipoTiempo.objects.create(
            empresa=empresa, tiempo_menu=TiempoMenu.FUERTE,
            articulo=copa_vino, cantidad_por_invitado=Decimal("2"),
        )
        RequerimientoEquipoTiempo.objects.create(
            empresa=empresa, tiempo_menu=TiempoMenu.POSTRE,
            articulo=plato_postre, cantidad_por_invitado=Decimal("1"),
        )

        # --- Lista de carga automatizada de ejemplo (evento confirmado) ---
        lista_carga = ListaCargaEvento.objects.create(evento=evento_confirmado)
        lista_carga.generar_o_actualizar_detalles()

        self.stdout.write(self.style.SUCCESS(
            f"Datos de demostración creados: {Evento.objects.count()} eventos, "
            f"{RecetaMaestra.objects.count()} recetas, {Insumo.objects.count()} insumos, "
            f"lista de carga con {lista_carga.detalles.count()} artículos "
            f"(+{ListaCargaEvento.FACTOR_ROTURA * 100:.0f}% de rotura aplicado)."
        ))
