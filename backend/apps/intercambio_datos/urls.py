from django.urls import path
from .views import (
    ImportacionesAnalyzeView, ImportacionesExecuteView, ImportacionesListView, ImportacionesDetailView,
    ImportacionesErroresView, ImportacionesReporteView,
    PlantillasListView, PlantillasDownloadView,
    ExportProfilesView, ExportGenerateView, ExportDownloadView,
)

urlpatterns = [
    path('importaciones/analizar/', ImportacionesAnalyzeView.as_view()),
    path('importaciones/ejecutar/', ImportacionesExecuteView.as_view()),
    path('importaciones/', ImportacionesListView.as_view()),
    path('importaciones/<int:pk>/', ImportacionesDetailView.as_view()),
    path('importaciones/<int:id>/errores/', ImportacionesErroresView.as_view()),
    path('importaciones/<int:id>/reporte/', ImportacionesReporteView.as_view()),
    path('plantillas/', PlantillasListView.as_view()),
    path('plantillas/<str:codigo>/descargar/', PlantillasDownloadView.as_view()),
    path('exportaciones/perfiles/', ExportProfilesView.as_view()),
    path('exportaciones/generar/', ExportGenerateView.as_view()),
    path('exportaciones/<int:id>/descargar/', ExportDownloadView.as_view()),
]
