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
from rest_framework_simplejwt.views import TokenRefreshView
from apps.usuarios.serializers import CustomTokenObtainPairView
from .api_router import router
from apps.facturacion.views import ConfiguracionDIANViewSet, FacturaElectronicaViewSet


configuracion_dian_list = ConfiguracionDIANViewSet.as_view({'get': 'list', 'post': 'create'})
configuracion_dian_rangos = ConfiguracionDIANViewSet.as_view({'get': 'rangos'})
configuracion_dian_rangos_sync = ConfiguracionDIANViewSet.as_view({'post': 'sync_ranges'})
configuracion_dian_rangos_select = ConfiguracionDIANViewSet.as_view({'post': 'select_range'})
factura_electronica_xml = FacturaElectronicaViewSet.as_view({'get': 'xml_by_id'})
factura_electronica_pdf = FacturaElectronicaViewSet.as_view({'get': 'pdf_by_id'})
factura_electronica_correo = FacturaElectronicaViewSet.as_view({'post': 'enviar_correo_by_id'})
factura_electronica_sync = FacturaElectronicaViewSet.as_view({'post': 'sincronizar'})

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Autenticación JWT personalizada
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # API completa
    path('api/', include(router.urls)),
    path('api/configuracion/dian/', configuracion_dian_list, name='configuracion-dian'),
    path('api/configuracion/dian/rangos/', configuracion_dian_rangos, name='configuracion-dian-rangos'),
    path('api/configuracion/dian/rangos/sync/', configuracion_dian_rangos_sync, name='configuracion-dian-rangos-sync'),
    path('api/configuracion/dian/rangos/select/', configuracion_dian_rangos_select, name='configuracion-dian-rangos-select'),
    path('api/facturacion/facturas-electronicas/<int:pk>/xml/', factura_electronica_xml, name='factura-electronica-xml'),
    path('api/facturacion/facturas-electronicas/<int:pk>/pdf/', factura_electronica_pdf, name='factura-electronica-pdf'),
    path('api/facturacion/facturas-electronicas/<int:pk>/enviar_correo/', factura_electronica_correo, name='factura-electronica-correo'),
    path('api/facturacion/facturas-electronicas/<int:pk>/sincronizar/', factura_electronica_sync, name='factura-electronica-sync'),
    
    # Autenticación de DRF (para browsable API)
    path('api-auth/', include('rest_framework.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
