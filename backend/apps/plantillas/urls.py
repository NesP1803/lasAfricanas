from django.urls import path

from .views import DocumentPdfView, DocumentReceiptView, TemplatePreviewView

urlpatterns = [
    path('templates/preview/', TemplatePreviewView.as_view(), name='template-preview'),
    path(
        'documents/<str:doc_type>/<int:document_id>/pdf/',
        DocumentPdfView.as_view(),
        name='document-pdf',
    ),
    path(
        'documents/<str:doc_type>/<int:document_id>/receipt/',
        DocumentReceiptView.as_view(),
        name='document-receipt',
    ),
]
