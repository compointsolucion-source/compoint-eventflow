from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ClienteViewSet,
    DetalleMenuEventoViewSet,
    EmpresaBanqueteraViewSet,
    EventoViewSet,
    IngredienteRecetaViewSet,
    InsumoViewSet,
    InventarioEquipoViewSet,
    PruebaMenuViewSet,
    RecetaMaestraViewSet,
    RegistroRoturasViewSet,
    SedeEventoViewSet,
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

urlpatterns = router.urls + [
    path("estado/", estado_servidor, name="estado-servidor"),
    path("inicializar/", inicializar_produccion, name="inicializar-produccion"),
]
