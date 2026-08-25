from decimal import Decimal

from django.test import TestCase

from core.models import (
    Cliente,
    DetalleMenuEvento,
    EmpresaBanquetera,
    Evento,
    InventarioEquipo,
    ListaCargaEvento,
    RecetaMaestra,
    RequerimientoEquipoTiempo,
    SedeEvento,
    TiempoMenu,
)


class ListaCargaFactorRoturaTestCase(TestCase):
    """Verifica el Módulo D: desglose de listas de carga por tiempo de menú
    y el Factor +10% de Rotura sobre el equipo que sale de la bodega."""

    def setUp(self):
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa, nombre="Cliente Demo", telefono="555-0001",
        )
        self.sede = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Jardín Demo", direccion="Calle 1",
        )

        self.plato_hondo = InventarioEquipo.objects.create(
            empresa=self.empresa, nombre="Plato hondo entrada",
            tipo=InventarioEquipo.TipoEquipo.VAJILLA, stock_disponible=1000,
        )
        self.plato_plano = InventarioEquipo.objects.create(
            empresa=self.empresa, nombre="Plato plano fuerte",
            tipo=InventarioEquipo.TipoEquipo.VAJILLA, stock_disponible=1000,
        )
        self.copa_vino = InventarioEquipo.objects.create(
            empresa=self.empresa, nombre="Copa de vino",
            tipo=InventarioEquipo.TipoEquipo.CRISTALERIA, stock_disponible=1000,
        )

        RequerimientoEquipoTiempo.objects.create(
            empresa=self.empresa, tiempo_menu=TiempoMenu.ENTRADA,
            articulo=self.plato_hondo, cantidad_por_invitado=Decimal("1"),
        )
        RequerimientoEquipoTiempo.objects.create(
            empresa=self.empresa, tiempo_menu=TiempoMenu.FUERTE,
            articulo=self.plato_plano, cantidad_por_invitado=Decimal("1"),
        )
        RequerimientoEquipoTiempo.objects.create(
            empresa=self.empresa, tiempo_menu=TiempoMenu.FUERTE,
            articulo=self.copa_vino, cantidad_por_invitado=Decimal("2"),
        )

        self.receta_entrada = RecetaMaestra.objects.create(
            empresa=self.empresa, nombre="Ensalada", tiempo_menu=TiempoMenu.ENTRADA,
            porciones_base=1, costo_estimado=Decimal("10.00"),
        )
        self.receta_fuerte = RecetaMaestra.objects.create(
            empresa=self.empresa, nombre="Filete", tiempo_menu=TiempoMenu.FUERTE,
            porciones_base=1, costo_estimado=Decimal("50.00"),
        )

        self.evento = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Boda Demo", fecha="2026-12-01",
            numero_invitados=100, tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=self.sede,
        )
        DetalleMenuEvento.objects.create(evento=self.evento, receta=self.receta_entrada)
        DetalleMenuEvento.objects.create(evento=self.evento, receta=self.receta_fuerte)

    def test_genera_una_linea_por_articulo_requerido(self):
        lista = ListaCargaEvento.objects.create(evento=self.evento)
        lista.generar_o_actualizar_detalles()

        detalles = {d.articulo.nombre: d for d in lista.detalles.all()}
        self.assertEqual(set(detalles.keys()), {"Plato hondo entrada", "Plato plano fuerte", "Copa de vino"})

    def test_cantidad_requerida_es_invitados_x_cantidad_por_invitado(self):
        lista = ListaCargaEvento.objects.create(evento=self.evento)
        lista.generar_o_actualizar_detalles()

        detalles = {d.articulo.nombre: d for d in lista.detalles.all()}
        # 100 invitados x 1 plato hondo/invitado = 100
        self.assertEqual(detalles["Plato hondo entrada"].cantidad_requerida, 100)
        # 100 invitados x 2 copas/invitado = 200
        self.assertEqual(detalles["Copa de vino"].cantidad_requerida, 200)

    def test_factor_10_por_ciento_de_rotura_redondea_hacia_arriba(self):
        lista = ListaCargaEvento.objects.create(evento=self.evento)
        lista.generar_o_actualizar_detalles()

        plato_hondo_detalle = lista.detalles.get(articulo=self.plato_hondo)
        # 100 requeridas + 10% = 110 (exacto)
        self.assertEqual(plato_hondo_detalle.cantidad_a_cargar, 110)

        copa_detalle = lista.detalles.get(articulo=self.copa_vino)
        # 200 requeridas + 10% = 220 (exacto)
        self.assertEqual(copa_detalle.cantidad_a_cargar, 220)

    def test_recalcular_quita_lineas_de_tiempos_ya_no_contratados(self):
        lista = ListaCargaEvento.objects.create(evento=self.evento)
        lista.generar_o_actualizar_detalles()
        self.assertEqual(lista.detalles.count(), 3)

        # El cliente quita el plato fuerte del menú: ya no debería requerir
        # plato plano ni copas de vino.
        DetalleMenuEvento.objects.filter(evento=self.evento, receta=self.receta_fuerte).delete()
        lista.generar_o_actualizar_detalles()

        detalles = {d.articulo.nombre for d in lista.detalles.all()}
        self.assertEqual(detalles, {"Plato hondo entrada"})

    def test_redondeo_hacia_arriba_con_cantidades_no_exactas(self):
        # 3 invitados x 1/invitado = 3 requeridas; +10% = 3.3 -> redondea a 4
        # para nunca quedar corto en el evento.
        plato_postre = InventarioEquipo.objects.create(
            empresa=self.empresa, nombre="Plato de postre",
            tipo=InventarioEquipo.TipoEquipo.VAJILLA, stock_disponible=1000,
        )
        RequerimientoEquipoTiempo.objects.create(
            empresa=self.empresa, tiempo_menu=TiempoMenu.POSTRE,
            articulo=plato_postre, cantidad_por_invitado=Decimal("1"),
        )
        receta_postre = RecetaMaestra.objects.create(
            empresa=self.empresa, nombre="Pastel", tiempo_menu=TiempoMenu.POSTRE,
            porciones_base=1, costo_estimado=Decimal("5.00"),
        )
        evento_chico = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Cena íntima", fecha="2026-12-05",
            numero_invitados=3, tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=self.sede,
        )
        DetalleMenuEvento.objects.create(evento=evento_chico, receta=receta_postre)

        lista = ListaCargaEvento.objects.create(evento=evento_chico)
        lista.generar_o_actualizar_detalles()
        detalle = lista.detalles.get(articulo__nombre="Plato de postre")
        self.assertEqual(detalle.cantidad_requerida, 3)
        self.assertEqual(detalle.cantidad_a_cargar, 4)
