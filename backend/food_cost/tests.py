from decimal import Decimal

from django.test import TestCase

from core.models import (
    Cliente,
    DetalleMenuEvento,
    EmpresaBanquetera,
    Evento,
    IngredienteReceta,
    Insumo,
    RecetaMaestra,
    SedeEvento,
)
from food_cost.services import (
    MermaInvalidaError,
    calcular_factor_escala,
    costo_total_evento,
    explosion_insumos_evento,
)


class ExplosionInsumosTestCase(TestCase):
    """Verifica el algoritmo de escalado de recetas + merma + consolidación
    descrito en el Módulo C del plan maestro."""

    def setUp(self):
        self.empresa = EmpresaBanquetera.objects.create(nombre_comercial="Banquetes Demo")
        self.cliente = Cliente.objects.create(
            empresa=self.empresa, nombre="Cliente Demo", telefono="555-0001",
            tipo=Cliente.TipoCliente.DIRECTO,
        )
        self.sede = SedeEvento.objects.create(
            empresa=self.empresa, nombre="Jardín Demo", direccion="Calle 1",
        )

        # Insumo con 12% de merma (ej. proteína que pierde peso al cocinar).
        self.res_de_cerdo = Insumo.objects.create(
            empresa=self.empresa,
            nombre="Res al horno",
            unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
            costo_unitario=Decimal("180.00"),
            porcentaje_merma=Decimal("0.12"),
        )
        # Insumo sin merma.
        self.arroz = Insumo.objects.create(
            empresa=self.empresa,
            nombre="Arroz",
            unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
            costo_unitario=Decimal("25.00"),
            porcentaje_merma=Decimal("0.00"),
        )

        # Receta base a 10 porciones.
        self.receta_fuerte = RecetaMaestra.objects.create(
            empresa=self.empresa, nombre="Res al horno con arroz",
            tiempo_menu="FUERTE", porciones_base=10, costo_estimado=Decimal("2000.00"),
        )
        IngredienteReceta.objects.create(
            receta=self.receta_fuerte, insumo=self.res_de_cerdo,
            cantidad=Decimal("1.5"), unidad_medida=Insumo.UnidadMedida.KILOGRAMOS,
        )
        IngredienteReceta.objects.create(
            receta=self.receta_fuerte, insumo=self.arroz,
            cantidad=Decimal("1.0"), unidad_medida=Insumo.UnidadMedida.KILOGRAMOS,
        )

        # Segunda receta que también usa arroz, para probar consolidación.
        self.receta_guarnicion = RecetaMaestra.objects.create(
            empresa=self.empresa, nombre="Arroz a la mexicana extra",
            tiempo_menu="FUERTE", porciones_base=10, costo_estimado=Decimal("100.00"),
        )
        IngredienteReceta.objects.create(
            receta=self.receta_guarnicion, insumo=self.arroz,
            cantidad=Decimal("0.5"), unidad_medida=Insumo.UnidadMedida.KILOGRAMOS,
        )

    def _crear_evento(self, numero_invitados, recetas):
        evento = Evento.objects.create(
            empresa=self.empresa, nombre_evento="Boda Demo",
            fecha="2026-12-01", numero_invitados=numero_invitados,
            estado_semaforo=Evento.EstadoSemaforo.PROSPECTO,
            tipo_cliente=Evento.TipoCliente.DIRECTO,
            cliente=self.cliente, sede=self.sede,
        )
        for receta in recetas:
            DetalleMenuEvento.objects.create(evento=evento, receta=receta)
        return evento

    def test_factor_escala_100_a_350(self):
        # Receta base a 10 porciones, evento con garantía de 350 invitados.
        factor = calcular_factor_escala(porciones_base=10, numero_invitados=350)
        self.assertEqual(factor, Decimal("35"))

    def test_escala_recetas_de_100_a_350_invitados(self):
        evento_100 = self._crear_evento(100, [self.receta_fuerte])
        evento_350 = self._crear_evento(350, [self.receta_fuerte])

        lineas_100 = {l.nombre: l for l in explosion_insumos_evento(evento_100)}
        lineas_350 = {l.nombre: l for l in explosion_insumos_evento(evento_350)}

        # 100 invitados / 10 porciones base = factor 10 -> 1.5kg x 10 = 15kg netos.
        self.assertEqual(lineas_100["Res al horno"].cantidad_neta, Decimal("15.0000"))
        # 350 invitados / 10 = factor 35 -> 1.5kg x 35 = 52.5kg netos.
        self.assertEqual(lineas_350["Res al horno"].cantidad_neta, Decimal("52.5000"))

    def test_merma_incrementa_cantidad_a_comprar(self):
        evento = self._crear_evento(100, [self.receta_fuerte])
        lineas = {l.nombre: l for l in explosion_insumos_evento(evento)}

        res = lineas["Res al horno"]
        # cantidad_neta=15kg, merma=12% -> comprar 15 / 0.88 = 17.0455kg
        self.assertEqual(res.cantidad_neta, Decimal("15.0000"))
        self.assertEqual(res.cantidad_a_comprar, Decimal("17.0455"))
        self.assertGreater(res.cantidad_a_comprar, res.cantidad_neta)

        arroz = lineas["Arroz"]
        # Sin merma: cantidad_a_comprar == cantidad_neta.
        self.assertEqual(arroz.cantidad_a_comprar, arroz.cantidad_neta)

    def test_consolidacion_entre_recetas_que_comparten_insumo(self):
        evento = self._crear_evento(100, [self.receta_fuerte, self.receta_guarnicion])
        lineas = {l.nombre: l for l in explosion_insumos_evento(evento)}

        # Arroz: 1.0kg x factor10 (receta_fuerte) + 0.5kg x factor10 (guarnicion) = 15kg netos.
        arroz = lineas["Arroz"]
        self.assertEqual(arroz.cantidad_neta, Decimal("15.0000"))
        self.assertCountEqual(
            arroz.recetas_origen, ["Res al horno con arroz", "Arroz a la mexicana extra"]
        )

    def test_costo_total_evento(self):
        evento = self._crear_evento(100, [self.receta_fuerte])
        total = costo_total_evento(evento)
        # Res: 17.0455kg x $180 = 3068.19 ; Arroz: 10kg x $25 = 250.00
        self.assertEqual(total, Decimal("3318.19"))

    def test_merma_100_por_ciento_lanza_error(self):
        insumo_invalido = Insumo.objects.create(
            empresa=self.empresa, nombre="Insumo con merma total",
            unidad_base=Insumo.UnidadMedida.KILOGRAMOS,
            costo_unitario=Decimal("10.00"), porcentaje_merma=Decimal("1.00"),
        )
        receta = RecetaMaestra.objects.create(
            empresa=self.empresa, nombre="Receta imposible",
            tiempo_menu="FUERTE", porciones_base=1, costo_estimado=Decimal("1.00"),
        )
        IngredienteReceta.objects.create(
            receta=receta, insumo=insumo_invalido,
            cantidad=Decimal("1.0"), unidad_medida=Insumo.UnidadMedida.KILOGRAMOS,
        )
        evento = self._crear_evento(10, [receta])
        with self.assertRaises(MermaInvalidaError):
            explosion_insumos_evento(evento)
