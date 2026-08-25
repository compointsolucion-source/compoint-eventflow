from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AbonoEventoViewSet,
    CheckInViewSet,
    ClienteViewSet,
    ConfiguracionCotizadorViewSet,
    DetalleListaCargaViewSet,
    DetalleMenuEventoViewSet,
    EmpresaBanqueteraViewSet,
    EsquemaPagoEventoViewSet,
    EventoViewSet,
    IngredienteRecetaViewSet,
    InsumoViewSet,
    InventarioEquipoViewSet,
    ListaCargaEventoViewSet,
    PersonalEventualViewSet,
    PostulacionViewSet,
    PruebaMenuViewSet,
    RecetaMaestraViewSet,
    RegistroRoturasViewSet,
    RequerimientoEquipoTiempoViewSet,
    SedeEventoViewSet,
    VacanteEventoViewSet,
    estado_servidor,
    inicializar_produccion,
)

router = DefaultRouter()
router.register("empresas", EmpresaBanqueteraViewSet)
router.register("clientes", ClienteViewSet)
router.register("sedes", SedeEventoViewSet)
router.register("eventos", EventoViewSet)
router.register("insumos", InsumoViewSet)
router.register("recetas", RecetaMaestraViewSet)
router.register("ingredientes-receta", IngredienteRecetaViewSet)
router.register("detalle-menu-evento", DetalleMenuEventoViewSet)
router.register("pruebas-menu", PruebaMenuViewSet)
router.register("inventario-equipo", InventarioEquipoViewSet)
router.register("registros-roturas", RegistroRoturasViewSet)
router.register("requerimientos-equipo", RequerimientoEquipoTiempoViewSet)
router.register("listas-carga", ListaCargaEventoViewSet)
router.register("detalle-lista-carga", DetalleListaCargaViewSet)
router.register("personal-eventual", PersonalEventualViewSet)
router.register("vacantes", VacanteEventoViewSet)
router.register("postulaciones", PostulacionViewSet)
router.register("checkins", CheckInViewSet)
router.register("configuracion-cotizador", ConfiguracionCotizadorViewSet)
router.register("esquemas-pago", EsquemaPagoEventoViewSet)
router.register("abonos", AbonoEventoViewSet)

urlpatterns = router.urls + [
    path("estado/", estado_servidor, name="estado-servidor"),
    path("inicializar/", inicializar_produccion, name="inicializar-produccion"),
]
