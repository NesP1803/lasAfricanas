"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenRefreshView
from apps.usuarios.serializers import CustomTokenObtainPairView
from .api_router import router
from apps.facturacion.views import (
    ConfiguracionDIANViewSet,
    FacturaElectronicaViewSet,
    RemisionesNumeracionViewSet,
)
from apps.facturacion.views import NotasCreditoViewSet
from apps.facturacion.views import DocumentosSoporteViewSet


configuracion_dian_list = ConfiguracionDIANViewSet.as_view({'get': 'list', 'post': 'create'})
configuracion_dian_rangos = ConfiguracionDIANViewSet.as_view({'get': 'rangos'})
configuracion_dian_rangos_sync = ConfiguracionDIANViewSet.as_view({'post': 'sync_ranges'})
configuracion_dian_rangos_select = ConfiguracionDIANViewSet.as_view({'post': 'select_range'})
configuracion_dian_factus_health = ConfiguracionDIANViewSet.as_view({'get': 'factus_health'})
factura_electronica_xml = FacturaElectronicaViewSet.as_view({'get': 'xml_by_id'})
factura_electronica_pdf = FacturaElectronicaViewSet.as_view({'get': 'pdf_by_id'})
factura_electronica_correo = FacturaElectronicaViewSet.as_view({'post': 'enviar_correo_by_id'})
factura_electronica_sync = FacturaElectronicaViewSet.as_view({'post': 'sincronizar'})
factura_electronica_sync_archivos = FacturaElectronicaViewSet.as_view({'post': 'sincronizar_archivos'})
factura_notas_credito_preview = FacturaElectronicaViewSet.as_view({'post': 'notas_credito_preview'})
factura_notas_credito_parcial = FacturaElectronicaViewSet.as_view({'post': 'notas_credito_parcial'})
factura_notas_credito_total = FacturaElectronicaViewSet.as_view({'post': 'notas_credito_total'})
nota_credito_detail = NotasCreditoViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'})
nota_credito_sync = NotasCreditoViewSet.as_view({'post': 'sincronizar'})
nota_credito_estado_remoto = NotasCreditoViewSet.as_view({'get': 'estado_remoto'})
nota_credito_retry_sync = NotasCreditoViewSet.as_view({'post': 'reintentar_conciliacion'})
nota_credito_pdf = NotasCreditoViewSet.as_view({'get': 'pdf_by_id'})
nota_credito_xml = NotasCreditoViewSet.as_view({'get': 'xml_by_id'})
nota_credito_correo_contenido = NotasCreditoViewSet.as_view({'get': 'correo_contenido'})
nota_credito_enviar_correo = NotasCreditoViewSet.as_view({'post': 'enviar_correo'})
nota_credito_eliminar = NotasCreditoViewSet.as_view({'post': 'eliminar'})
documento_soporte_detail = DocumentosSoporteViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'})
documento_soporte_sync = DocumentosSoporteViewSet.as_view({'post': 'sincronizar'})
documento_soporte_estado_remoto = DocumentosSoporteViewSet.as_view({'get': 'estado_remoto'})
documento_soporte_pdf = DocumentosSoporteViewSet.as_view({'get': 'pdf_by_id'})
documento_soporte_xml = DocumentosSoporteViewSet.as_view({'get': 'xml_by_id'})
documento_soporte_eliminar = DocumentosSoporteViewSet.as_view({'post': 'eliminar'})
remisiones_numeracion = RemisionesNumeracionViewSet.as_view({'get': 'numeracion', 'patch': 'actualizar_numeracion'})
remisiones_historial = RemisionesNumeracionViewSet.as_view({'get': 'historial'})


def electronic_ranges_deprecated(_request, *args, **kwargs):
    return JsonResponse(
        {
            'detail': (
                'La gestión local de rangos electrónicos fue deshabilitada. '
                'Los documentos electrónicos se administran directamente en Factus.'
            )
        },
        status=410,
    )

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Autenticación JWT personalizada
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # API específica de facturación/configuración (debe ir antes del router para evitar colisiones)
    path('api/configuracion/dian/', configuracion_dian_list, name='configuracion-dian'),
    path('api/configuracion/dian/rangos/', configuracion_dian_rangos, name='configuracion-dian-rangos'),
    path('api/configuracion/dian/rangos/sync/', configuracion_dian_rangos_sync, name='configuracion-dian-rangos-sync'),
    path('api/configuracion/dian/rangos/select/', configuracion_dian_rangos_select, name='configuracion-dian-rangos-select'),
    path('api/configuracion/dian/factus/health/', configuracion_dian_factus_health, name='configuracion-dian-factus-health'),
    path('api/factus/rangos/', configuracion_dian_rangos, name='factus-rangos'),
    path('api/factus/rangos/sincronizar/', configuracion_dian_rangos_sync, name='factus-rangos-sync'),
    path('api/factus/rangos/seleccionar-activo/', configuracion_dian_rangos_select, name='factus-rangos-select'),
    path('api/factus/health/', configuracion_dian_factus_health, name='factus-health'),
    path('api/facturacion/rangos/', electronic_ranges_deprecated, name='facturacion-rangos'),
    path('api/facturacion/rangos/sync/', electronic_ranges_deprecated, name='facturacion-rangos-sync'),
    path('api/facturacion/rangos/software/', electronic_ranges_deprecated, name='facturacion-rangos-software'),
    path('api/facturacion/rangos/autorizados-disponibles/', electronic_ranges_deprecated, name='facturacion-rangos-autorizados-disponibles'),
    path('api/facturacion/rangos/<int:pk>/', electronic_ranges_deprecated, name='facturacion-rangos-detail'),
    path('api/facturacion/rangos/<int:pk>/consecutivo/', electronic_ranges_deprecated, name='facturacion-rangos-consecutivo'),
    path('api/facturacion/rangos/<int:pk>/seleccionar-activo/', electronic_ranges_deprecated, name='facturacion-rangos-select'),
    path('api/facturacion/rangos/<int:pk>/seleccionar/', electronic_ranges_deprecated, name='facturacion-rangos-select-simple'),
    path('api/facturacion/rangos/<int:pk>/activar/', electronic_ranges_deprecated, name='facturacion-rangos-activar'),
    path('api/facturacion/remisiones/numeracion/', remisiones_numeracion, name='facturacion-remisiones-numeracion'),
    path('api/facturacion/remisiones/historial/', remisiones_historial, name='facturacion-remisiones-historial'),
    path('api/facturacion/facturas-electronicas/<int:pk>/xml/', factura_electronica_xml, name='factura-electronica-xml'),
    path('api/facturacion/facturas-electronicas/<int:pk>/pdf/', factura_electronica_pdf, name='factura-electronica-pdf'),
    path('api/facturacion/facturas-electronicas/<int:pk>/enviar_correo/', factura_electronica_correo, name='factura-electronica-correo'),
    path('api/facturas-electronicas/<int:pk>/enviar-correo/', factura_electronica_correo, name='factura-electronica-correo-direct'),
    path('api/facturas-electronicas/<int:pk>/sincronizar-archivos/', factura_electronica_sync_archivos, name='factura-electronica-sync-archivos'),
    path('api/facturacion/facturas-electronicas/<int:pk>/sincronizar/', factura_electronica_sync, name='factura-electronica-sync'),
    path('api/facturacion/facturas/<int:pk>/notas-credito/preview/', factura_notas_credito_preview, name='factura-nota-credito-preview'),
    path('api/facturacion/facturas/<int:pk>/notas-credito/parcial/', factura_notas_credito_parcial, name='factura-nota-credito-parcial'),
    path('api/facturacion/facturas/<int:pk>/notas-credito/total/', factura_notas_credito_total, name='factura-nota-credito-total'),
    path('api/notas-credito/<int:pk>/', nota_credito_detail, name='nota-credito-detail'),
    path('api/notas-credito/<int:pk>/sincronizar/', nota_credito_sync, name='nota-credito-sync'),
    path('api/notas-credito/<int:pk>/estado-remoto/', nota_credito_estado_remoto, name='nota-credito-estado-remoto'),
    path('api/notas-credito/<int:pk>/reintentar-conciliacion/', nota_credito_retry_sync, name='nota-credito-reintentar-conciliacion'),
    path('api/notas-credito/<int:pk>/pdf/', nota_credito_pdf, name='nota-credito-pdf'),
    path('api/notas-credito/<int:pk>/xml/', nota_credito_xml, name='nota-credito-xml'),
    path('api/notas-credito/<int:pk>/correo/contenido/', nota_credito_correo_contenido, name='nota-credito-correo-contenido'),
    path('api/notas-credito/<int:pk>/enviar-correo/', nota_credito_enviar_correo, name='nota-credito-enviar-correo'),
    path('api/notas-credito/<int:pk>/eliminar/', nota_credito_eliminar, name='nota-credito-eliminar'),
    path('api/documentos-soporte/<int:pk>/', documento_soporte_detail, name='documento-soporte-detail'),
    path('api/documentos-soporte/<int:pk>/sincronizar/', documento_soporte_sync, name='documento-soporte-sync'),
    path('api/documentos-soporte/<int:pk>/estado-remoto/', documento_soporte_estado_remoto, name='documento-soporte-estado-remoto'),
    path('api/documentos-soporte/<int:pk>/pdf/', documento_soporte_pdf, name='documento-soporte-pdf'),
    path('api/documentos-soporte/<int:pk>/xml/', documento_soporte_xml, name='documento-soporte-xml'),
    path('api/documentos-soporte/<int:pk>/eliminar/', documento_soporte_eliminar, name='documento-soporte-eliminar'),
    
    # API completa
    path('api/', include(router.urls)),

    # Autenticación de DRF (para browsable API)
    path('api-auth/', include('rest_framework.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
