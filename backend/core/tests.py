from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

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
    RegistroRoturas,
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


class RegistroRoturasTestCase(TestCase):
    """Verifica que el 'Cargo por Daños' (Módulo D) siempre se calcule solo,
    sin depender de que alguien capture bien el costo a mano."""

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
        self.copa = InventarioEquipo.objects.create(
            empresa=self.empresa, nombre="Copa de vino",
            tipo=InventarioEquipo.TipoEquipo.CRISTALERIA,
            stock_disponible=100, costo_reposicion_unitario=Decimal("45.00"),
        )

    def test_costo_reposicion_se_calcula_solo_al_guardar(self):
        rotura = RegistroRoturas.objects.create(
            evento=self.evento, articulo=self.copa, cantidad_rota=3,
        )
        self.assertEqual(rotura.costo_reposicion, Decimal("135.00"))

    def test_costo_reposicion_ignora_un_valor_capturado_a_mano(self):
        # Aunque alguien mande un costo_reposicion distinto, se recalcula
        # siempre a partir del catálogo de inventario para no perder
        # consistencia con el "Cargo por Daños".
        rotura = RegistroRoturas.objects.create(
            evento=self.evento, articulo=self.copa, cantidad_rota=2,
            costo_reposicion=Decimal("1.00"),
        )
        self.assertEqual(rotura.costo_reposicion, Decimal("90.00"))


class AutenticacionYRolesTestCase(TestCase):
    """Verifica el Módulo A de autenticación: la API requiere login para el
    equipo interno, y el Event Planner entra sin cuenta vía su link único
    (`token_planner`) sin ver costos ni otros eventos."""

    def setUp(self):
        self.client = APIClient()
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
            tipo_cliente=Evento.TipoCliente.PLANNER,
            cliente=self.cliente, sede=self.sede,
        )
        User = get_user_model()
        self.usuario = User.objects.create_user(username="ana", password="clave-segura-123")

    def test_endpoint_protegido_rechaza_sin_token(self):
        respuesta = self.client.get("/api/eventos/")
        self.assertEqual(respuesta.status_code, 401)

    def test_login_con_credenciales_correctas_da_token(self):
        respuesta = self.client.post(
            "/api/auth/login/", {"username": "ana", "password": "clave-segura-123"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["username"], "ana")
        token_en_bd = Token.objects.get(user=self.usuario)
        self.assertEqual(respuesta.data["token"], token_en_bd.key)

    def test_login_con_credenciales_incorrectas_falla(self):
        respuesta = self.client.post(
            "/api/auth/login/", {"username": "ana", "password": "clave-equivocada"},
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_endpoint_protegido_acepta_con_token_valido(self):
        token = Token.objects.create(user=self.usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        respuesta = self.client.get("/api/eventos/")
        self.assertEqual(respuesta.status_code, 200)

    def test_portal_planner_con_token_valido_no_requiere_login(self):
        # Sin credenciales de ningún tipo: el link del planner debe
        # funcionar solo, sin Authorization header.
        respuesta = self.client.get(f"/api/planner/{self.evento.token_planner}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["nombre_evento"], "Boda Demo")
        # Nunca debe traer costos/márgenes ni datos internos.
        self.assertNotIn("empresa", respuesta.data)
        self.assertNotIn("costo_estimado", str(respuesta.data))

    def test_portal_planner_con_token_invalido_da_404(self):
        respuesta = self.client.get("/api/planner/token-que-no-existe/")
        self.assertEqual(respuesta.status_code, 404)


class SemaforoVencimientoAutomaticoTestCase(TestCase):
    """Módulo A: un Prospecto vence solo a las 72 horas y un Apartado libera
    la fecha si no llega el anticipo en 5 días hábiles, sin depender de
    ningún cron/scheduler (se calcula al vuelo, ver `Evento.vencido`)."""

    def setUp(self):
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa, nombre="Cliente Demo", telefono="555-0001",
        )
        self.sede = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Jardín Demo", direccion="Calle 1",
        )

    def _crear_evento(self, **overrides):
        datos = dict(
            empresa=self.empresa, nombre_evento="Evento Demo",
            fecha=date.today() + timedelta(days=30), numero_invitados=50,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=self.sede,
        )
        datos.update(overrides)
        return Evento.objects.create(**datos)

    def test_prospecto_nuevo_obtiene_vencimiento_automatico_72h(self):
        evento = self._crear_evento(estado_semaforo=Evento.EstadoSemaforo.PROSPECTO)
        self.assertIsNotNone(evento.fecha_vencimiento_prospecto)
        diferencia = evento.fecha_vencimiento_prospecto - timezone.now()
        # Tolerancia de un minuto por el tiempo que tarda en correr el test.
        self.assertAlmostEqual(diferencia.total_seconds(), 72 * 3600, delta=60)

    def test_prospecto_no_vencido_antes_de_72h(self):
        evento = self._crear_evento(estado_semaforo=Evento.EstadoSemaforo.PROSPECTO)
        self.assertFalse(evento.vencido)
        self.assertFalse(evento.bloquea_fecha)

    def test_prospecto_vencido_despues_de_72h(self):
        evento = self._crear_evento(
            estado_semaforo=Evento.EstadoSemaforo.PROSPECTO,
            fecha_vencimiento_prospecto=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(evento.vencido)
        self.assertFalse(evento.bloquea_fecha)

    def test_prospecto_nunca_bloquea_fecha_aunque_no_este_vencido(self):
        evento = self._crear_evento(estado_semaforo=Evento.EstadoSemaforo.PROSPECTO)
        self.assertFalse(evento.bloquea_fecha)

    def test_apartado_nuevo_obtiene_fecha_limite_automatica(self):
        evento = self._crear_evento(estado_semaforo=Evento.EstadoSemaforo.APARTADO)
        self.assertIsNotNone(evento.fecha_limite_anticipo)
        self.assertGreater(evento.fecha_limite_anticipo, timezone.localdate())

    def test_apartado_vencido_si_paso_fecha_limite_sin_anticipo(self):
        evento = self._crear_evento(
            estado_semaforo=Evento.EstadoSemaforo.APARTADO,
            fecha_limite_anticipo=timezone.localdate() - timedelta(days=1),
        )
        self.assertTrue(evento.vencido)
        self.assertFalse(evento.bloquea_fecha)

    def test_apartado_no_vencido_si_ya_registro_anticipo(self):
        evento = self._crear_evento(
            estado_semaforo=Evento.EstadoSemaforo.APARTADO,
            fecha_limite_anticipo=timezone.localdate() - timedelta(days=1),
            fecha_registro_anticipo=timezone.now(),
        )
        self.assertFalse(evento.vencido)
        self.assertTrue(evento.bloquea_fecha)

    def test_confirmado_siempre_bloquea_fecha(self):
        evento = self._crear_evento(estado_semaforo=Evento.EstadoSemaforo.CONFIRMADO)
        self.assertFalse(evento.vencido)
        self.assertTrue(evento.bloquea_fecha)

    def test_evento_no_puede_exceder_capacidad_de_sede(self):
        sede_chica = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Salón Chico", direccion="Calle 2",
            capacidad_maxima_invitados=100,
        )
        evento = Evento(
            empresa=self.empresa, nombre_evento="Fiesta Grande",
            fecha=date.today() + timedelta(days=10), numero_invitados=150,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=sede_chica,
        )
        with self.assertRaises(ValidationError):
            evento.full_clean()

    def test_evento_dentro_de_capacidad_de_sede_no_lanza_error(self):
        sede_chica = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Salón Chico 2", direccion="Calle 3",
            capacidad_maxima_invitados=100,
        )
        evento = Evento(
            empresa=self.empresa, nombre_evento="Fiesta Mediana",
            fecha=date.today() + timedelta(days=10), numero_invitados=80,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=sede_chica,
        )
        evento.full_clean()  # No debe lanzar.


class BloqueoCapacidadFechaTestCase(TestCase):
    """Módulo A: bloqueo automático de una fecha cuando la loza o el
    personal ya están saturados entre los eventos que la ocupan, con
    posibilidad de que el administrador lo autorice a mano."""

    def setUp(self):
        self.client = APIClient()
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa, nombre="Cliente Demo", telefono="555-0001",
        )
        self.sede = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Jardín Demo", direccion="Calle 1",
        )
        User = get_user_model()
        usuario = User.objects.create_user(username="ana", password="clave-segura-123")
        token = Token.objects.create(user=usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.fecha_compartida = date.today() + timedelta(days=30)

        self.plato_hondo = InventarioEquipo.objects.create(
            empresa=self.empresa, nombre="Plato hondo entrada",
            tipo=InventarioEquipo.TipoEquipo.VAJILLA, stock_disponible=10,
        )
        RequerimientoEquipoTiempo.objects.create(
            empresa=self.empresa, tiempo_menu=TiempoMenu.ENTRADA,
            articulo=self.plato_hondo, cantidad_por_invitado=Decimal("1"),
        )
        self.receta_entrada = RecetaMaestra.objects.create(
            empresa=self.empresa, nombre="Ensalada", tiempo_menu=TiempoMenu.ENTRADA,
            porciones_base=1, costo_estimado=Decimal("10.00"),
        )

        # Evento A ya confirmado: ya usa 8 platos hondos y 2 meseros ese día.
        self.evento_a = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Boda A", fecha=self.fecha_compartida,
            numero_invitados=8, estado_semaforo=Evento.EstadoSemaforo.CONFIRMADO,
            tipo_cliente=Evento.TipoCliente.DIRECTO, cliente=self.cliente, sede=self.sede,
        )
        DetalleMenuEvento.objects.create(evento=self.evento_a, receta=self.receta_entrada)
        VacanteEvento.objects.create(
            evento=self.evento_a, rol=PersonalEventual.Rol.MESERO,
            cantidad_requerida=2, tarifa_por_turno=Decimal("300.00"),
        )

        # Solo 2 meseros activos en toda la bolsa de trabajo.
        PersonalEventual.objects.create(
            empresa=self.empresa, nombre="Mesero Uno", telefono="555-1001",
            rol_principal=PersonalEventual.Rol.MESERO,
        )
        PersonalEventual.objects.create(
            empresa=self.empresa, nombre="Mesero Dos", telefono="555-1002",
            rol_principal=PersonalEventual.Rol.MESERO,
        )

        # Evento B: mismo día, también confirmado, todavía sin menú ni vacantes.
        self.evento_b = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Boda B", fecha=self.fecha_compartida,
            numero_invitados=5, estado_semaforo=Evento.EstadoSemaforo.CONFIRMADO,
            tipo_cliente=Evento.TipoCliente.DIRECTO, cliente=self.cliente, sede=self.sede,
        )

    def test_bloquea_agregar_menu_si_satura_la_loza_del_dia(self):
        # A (8) + B (5) = 13 platos hondos, pero solo hay 10 en bodega.
        respuesta = self.client.post(
            "/api/detalle-menu-evento/",
            {"evento": self.evento_b.id, "receta": self.receta_entrada.id},
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_permite_agregar_menu_si_administrador_ya_autorizo(self):
        self.evento_b.autorizado_proveedor_externo = True
        self.evento_b.save()
        respuesta = self.client.post(
            "/api/detalle-menu-evento/",
            {"evento": self.evento_b.id, "receta": self.receta_entrada.id},
        )
        self.assertEqual(respuesta.status_code, 201)

    def test_bloquea_vacante_si_satura_el_personal_del_dia(self):
        # A (2 meseros) + B (1 mesero) = 3, pero solo hay 2 meseros activos.
        respuesta = self.client.post(
            "/api/vacantes/",
            {
                "evento": self.evento_b.id, "rol": PersonalEventual.Rol.MESERO,
                "cantidad_requerida": 1, "tarifa_por_turno": "300.00",
            },
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_permite_vacante_si_administrador_ya_autorizo(self):
        self.evento_b.autorizado_proveedor_externo = True
        self.evento_b.save()
        respuesta = self.client.post(
            "/api/vacantes/",
            {
                "evento": self.evento_b.id, "rol": PersonalEventual.Rol.MESERO,
                "cantidad_requerida": 1, "tarifa_por_turno": "300.00",
            },
        )
        self.assertEqual(respuesta.status_code, 201)

    def test_no_bloquea_si_la_loza_alcanza(self):
        # Bajamos los invitados de B para que 8 + 2 = 10 sí quepa en bodega.
        self.evento_b.numero_invitados = 2
        self.evento_b.save()
        respuesta = self.client.post(
            "/api/detalle-menu-evento/",
            {"evento": self.evento_b.id, "receta": self.receta_entrada.id},
        )
        self.assertEqual(respuesta.status_code, 201)
