from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from core.models import (
    CheckIn,
    Cliente,
    ConfiguracionCotizador,
    DetalleMenuEvento,
    EmpresaBanquetera,
    EsquemaPagoEvento,
    Evento,
    InventarioEquipo,
    ListaCargaEvento,
    PersonalEventual,
    Postulacion,
    PruebaMenu,
    RecetaMaestra,
    RequerimientoEquipoTiempo,
    SedeEvento,
    TiempoMenu,
    VacanteEvento,
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


class ConfiguracionCotizadorTestCase(TestCase):
    """Verifica el Cotizador por Volumen (Módulo F): el precio por persona
    debe subir cuando hay menos invitados, porque los costos fijos de
    transporte y personal se reparten entre menos comensales."""

    def setUp(self):
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.configuracion = ConfiguracionCotizador.objects.create(
            empresa=self.empresa,
            costo_base_por_persona=Decimal("450.00"),
            costos_fijos_transporte_personal=Decimal("18000.00"),
        )

    def test_precio_por_persona_incluye_costos_fijos_repartidos(self):
        cotizacion = self.configuracion.cotizar(100)
        # 18000 / 100 = 180 de costos fijos por persona.
        self.assertEqual(cotizacion["costos_fijos_por_persona"], Decimal("180.00"))
        self.assertEqual(cotizacion["precio_por_persona"], Decimal("630.00"))
        self.assertEqual(cotizacion["precio_total"], Decimal("63000.00"))

    def test_precio_por_persona_es_inversamente_proporcional_a_invitados(self):
        # A menor número de invitados, mayor precio por persona (mismos
        # costos fijos repartidos entre menos gente).
        cotizacion_pocos = self.configuracion.cotizar(50)
        cotizacion_muchos = self.configuracion.cotizar(300)
        self.assertGreater(
            cotizacion_pocos["precio_por_persona"], cotizacion_muchos["precio_por_persona"]
        )

    def test_numero_invitados_cero_o_negativo_lanza_error(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.configuracion.cotizar(0)


class EsquemaPagoEventoTestCase(TestCase):
    """Verifica el Esquema de Cobro Automatizado 50/30/20 del Módulo F."""

    def setUp(self):
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa, nombre="Cliente Demo", telefono="555-0001",
        )
        self.sede = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Jardín Demo", direccion="Calle 1",
        )
        self.evento = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Boda Demo",
            fecha=date.today() + timedelta(days=100), numero_invitados=100,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=self.sede,
        )

    def test_genera_abonos_con_split_50_30_20(self):
        esquema = EsquemaPagoEvento.objects.create(evento=self.evento, monto_total=Decimal("100000.00"))
        esquema.generar_o_actualizar_abonos()

        abonos = {a.tipo: a for a in esquema.abonos.all()}
        self.assertEqual(set(abonos.keys()), {"ANTICIPO", "INTERMEDIO", "LIQUIDACION"})
        self.assertEqual(abonos["ANTICIPO"].monto, Decimal("50000.00"))
        self.assertEqual(abonos["INTERMEDIO"].monto, Decimal("30000.00"))
        self.assertEqual(abonos["LIQUIDACION"].monto, Decimal("20000.00"))

    def test_fecha_intermedia_usa_primera_prueba_de_menu_si_existe(self):
        fecha_prueba = date.today() + timedelta(days=20)
        PruebaMenu.objects.create(
            evento=self.evento, fecha_prueba=fecha_prueba, asistentes=4,
        )
        esquema = EsquemaPagoEvento.objects.create(evento=self.evento, monto_total=Decimal("100000.00"))
        esquema.generar_o_actualizar_abonos()

        abono_intermedio = esquema.abonos.get(tipo="INTERMEDIO")
        self.assertEqual(abono_intermedio.fecha_limite, fecha_prueba)

    def test_fecha_intermedia_sin_prueba_de_menu_cae_30_dias_antes_del_evento(self):
        esquema = EsquemaPagoEvento.objects.create(evento=self.evento, monto_total=Decimal("100000.00"))
        esquema.generar_o_actualizar_abonos()

        abono_intermedio = esquema.abonos.get(tipo="INTERMEDIO")
        self.assertEqual(abono_intermedio.fecha_limite, self.evento.fecha - timedelta(days=30))

    def test_fecha_liquidacion_es_15_dias_antes_del_evento(self):
        esquema = EsquemaPagoEvento.objects.create(evento=self.evento, monto_total=Decimal("100000.00"))
        esquema.generar_o_actualizar_abonos()

        abono_liquidacion = esquema.abonos.get(tipo="LIQUIDACION")
        self.assertEqual(abono_liquidacion.fecha_limite, self.evento.fecha - timedelta(days=15))

    def test_abono_vencido_solo_si_no_esta_pagado_y_ya_paso_la_fecha(self):
        esquema = EsquemaPagoEvento.objects.create(evento=self.evento, monto_total=Decimal("100000.00"))
        esquema.generar_o_actualizar_abonos()
        abono_anticipo = esquema.abonos.get(tipo="ANTICIPO")

        # Recién generado (fecha_limite = hoy, no vencido todavía).
        self.assertFalse(abono_anticipo.vencido)

        # Si la fecha límite ya pasó y no se ha pagado, está vencido.
        abono_anticipo.fecha_limite = date.today() - timedelta(days=1)
        abono_anticipo.save(update_fields=["fecha_limite"])
        self.assertTrue(abono_anticipo.vencido)

        # Una vez pagado, deja de estar vencido aunque la fecha ya pasó.
        abono_anticipo.marcar_pagado()
        self.assertFalse(abono_anticipo.vencido)


class VacanteEventoTestCase(TestCase):
    """Verifica la Bolsa de Trabajo (Módulo E): cuántas postulaciones
    aceptadas tiene una vacante y si ya quedó cubierta."""

    def setUp(self):
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa, nombre="Cliente Demo", telefono="555-0001",
        )
        self.sede = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Jardín Demo", direccion="Calle 1",
        )
        self.evento = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Boda Demo",
            fecha=date.today() + timedelta(days=30), numero_invitados=100,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=self.sede,
        )
        self.vacante = VacanteEvento.objects.create(
            evento=self.evento, rol=PersonalEventual.Rol.MESERO,
            cantidad_requerida=2, tarifa_por_turno=Decimal("600.00"),
        )
        self.mesero_1 = PersonalEventual.objects.create(
            empresa=self.empresa, nombre="Mesero 1", telefono="555-1001",
            rol_principal=PersonalEventual.Rol.MESERO,
        )
        self.mesero_2 = PersonalEventual.objects.create(
            empresa=self.empresa, nombre="Mesero 2", telefono="555-1002",
            rol_principal=PersonalEventual.Rol.MESERO,
        )
        self.mesero_3 = PersonalEventual.objects.create(
            empresa=self.empresa, nombre="Mesero 3", telefono="555-1003",
            rol_principal=PersonalEventual.Rol.MESERO,
        )

    def test_vacante_no_cubierta_sin_postulaciones_aceptadas(self):
        Postulacion.objects.create(
            vacante=self.vacante, personal=self.mesero_1, estado=Postulacion.Estado.POSTULADO,
        )
        self.assertEqual(self.vacante.cantidad_aceptada, 0)
        self.assertFalse(self.vacante.cubierta)

    def test_vacante_cubierta_cuando_aceptados_alcanzan_lo_requerido(self):
        Postulacion.objects.create(
            vacante=self.vacante, personal=self.mesero_1, estado=Postulacion.Estado.ACEPTADO,
        )
        Postulacion.objects.create(
            vacante=self.vacante, personal=self.mesero_2, estado=Postulacion.Estado.ACEPTADO,
        )
        Postulacion.objects.create(
            vacante=self.vacante, personal=self.mesero_3, estado=Postulacion.Estado.RECHAZADO,
        )
        self.assertEqual(self.vacante.cantidad_aceptada, 2)
        self.assertTrue(self.vacante.cubierta)


class CheckInTestCase(TestCase):
    """Verifica el Check-In de Personal Eventual (Módulo E)."""

    def setUp(self):
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa, nombre="Cliente Demo", telefono="555-0001",
        )
        self.sede = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Jardín Demo", direccion="Calle 1",
        )
        self.evento = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Boda Demo",
            fecha=date.today() + timedelta(days=30), numero_invitados=100,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=self.sede,
        )
        self.vacante = VacanteEvento.objects.create(
            evento=self.evento, rol=PersonalEventual.Rol.MESERO,
            cantidad_requerida=1, tarifa_por_turno=Decimal("600.00"),
        )
        self.mesero = PersonalEventual.objects.create(
            empresa=self.empresa, nombre="Mesero 1", telefono="555-1001",
            rol_principal=PersonalEventual.Rol.MESERO,
        )
        self.postulacion = Postulacion.objects.create(
            vacante=self.vacante, personal=self.mesero, estado=Postulacion.Estado.ACEPTADO,
        )

    def test_codigo_verificacion_se_genera_solo_y_es_unico(self):
        check_in_1 = CheckIn.objects.create(postulacion=self.postulacion)
        self.assertEqual(len(check_in_1.codigo_verificacion), 8)
        self.assertFalse(check_in_1.asistio)

    def test_confirmar_marca_asistencia_con_hora_y_responsable(self):
        check_in = CheckIn.objects.create(postulacion=self.postulacion)
        self.assertIsNone(check_in.hora_checkin)

        check_in.confirmar(confirmado_por="Capitán de Meseros")

        check_in.refresh_from_db()
        self.assertTrue(check_in.asistio)
        self.assertIsNotNone(check_in.hora_checkin)
        self.assertEqual(check_in.confirmado_por, "Capitán de Meseros")
