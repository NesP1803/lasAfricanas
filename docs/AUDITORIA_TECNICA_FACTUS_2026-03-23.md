# Plan de corrección técnico por archivos (Factus)

Fecha: 2026-03-23

## Backend: archivo -> cambio requerido -> prioridad

1) `backend/config/api_router.py`
- Problema: solo registra `facturacion`; no existen recursos REST explícitos para `/notas-credito` y `/documentos-soporte`.
- Cambio: registrar viewsets nuevos (`NotasCreditoViewSet`, `DocumentosSoporteViewSet`) y mantener temporalmente `facturacion` para compatibilidad.
- Dependencias: creación previa de viewsets/serializers en app `facturacion`.
- Compatibilidad: si se conserva `facturacion`, no rompe; si se elimina sin transición, rompe frontend legado.
- Prioridad: crítica.

2) `backend/apps/facturacion/views.py`
- Problema: `FacturaElectronicaViewSet` concentra acciones y no expone list/create/download de notas/docs con rutas de recurso separadas.
- Cambio: extraer clases nuevas:
  - `NotasCreditoViewSet`: `list`, `create`, `xml`, `pdf`.
  - `DocumentosSoporteViewSet`: `list`, `create`, `xml`, `pdf`, opcional `nota_ajuste`.
  Además, normalizar `estado` en endpoint `facturacion/{numero}/estado`.
- Dependencias: serializers nuevos y posibles servicios de descarga para notas/docs.
- Compatibilidad: cambio de contrato si se altera respuesta existente; recomendada salida dual (`estado` + `estado_dian`) para transición.
- Prioridad: crítica.

3) `backend/apps/facturacion/serializers/__init__.py`
- Problema: serializer de estado no expone campo `estado` esperado por frontend.
- Cambio: agregar `estado = serializers.CharField(source='status', read_only=True)` y mantener `estado_dian` temporalmente.
- Dependencias: ninguna compleja.
- Compatibilidad: retrocompatible si no se elimina `estado_dian`.
- Prioridad: alta.

4) `backend/apps/facturacion/serializers/` (nuevos archivos)
- Problema: no hay serializers dedicados para notas crédito/documentos soporte (listado y creación REST clara).
- Cambio: crear serializers explícitos:
  - `nota_credito_serializer.py`
  - `documento_soporte_serializer.py`
  con shape alineado a frontend objetivo.
- Dependencias: modelos `NotaCreditoElectronica`, `DocumentoSoporteElectronico`, `NotaAjusteDocumentoSoporte`.
- Compatibilidad: no rompe si se agregan como endpoints nuevos.
- Prioridad: alta.

5) `backend/apps/facturacion/services/download_invoice_files.py`
- Problema: solo cubre factura electrónica; no existe helper homologable para archivos de nota/documento.
- Cambio: o extender este archivo para soportar modelos adicionales o crear servicios paralelos:
  - `download_credit_note_files.py`
  - `download_support_document_files.py`
  con persistencia de rutas locales.
- Dependencias: nuevos campos de ruta local en modelos de nota/documento (si se decide persistir local).
- Compatibilidad: no rompe si se añade en paralelo.
- Prioridad: alta.

6) `backend/apps/facturacion/models.py`
- Problema: nota crédito y documento soporte no tienen `xml_local_path/pdf_local_path`; impide reutilizar patrón de descarga local.
- Cambio: agregar campos locales a `NotaCreditoElectronica` y `DocumentoSoporteElectronico` (y opcional `NotaAjusteDocumentoSoporte`) o definir descarga directa por URL remota sin persistencia local.
- Dependencias: migración de esquema.
- Compatibilidad: agregar campos es compatible.
- Prioridad: media-alta.

7) `backend/apps/facturacion/migrations/` (nueva migración)
- Problema: faltan columnas/rastreo local para nuevos endpoints de descarga homogéneos.
- Cambio: migración para campos locales (si aplica) e índices de consulta por `number` en nota/doc si no existen.
- Dependencias: cambios previos de modelos.
- Compatibilidad: compatible hacia adelante.
- Prioridad: alta.

8) `backend/apps/facturacion/tests.py`
- Problema: cobertura limitada para nuevos recursos y no valida contrato frontend esperado (`estado`, binarios).
- Cambio: agregar tests para:
  - `/api/notas-credito/` list/create/xml/pdf
  - `/api/documentos-soporte/` list/create/xml/pdf
  - contrato de `estado`.
- Dependencias: endpoints implementados.
- Compatibilidad: no aplica.
- Prioridad: alta.

9) `backend/config/urls.py` (opcional)
- Problema: endpoint de configuración DIAN fuera de router; riesgo de dispersión contractual.
- Cambio: evaluar unificar en router si se estandariza estrategia de recursos.
- Dependencias: menores.
- Compatibilidad: cuidar path actual.
- Prioridad: media.

## Frontend: archivo -> cambio requerido -> prioridad

1) `frontend/src/modules/notasCredito/services/notasCreditoApi.ts`
- Problema: consume endpoints inexistentes hoy y payload de creación no alineado al backend actual.
- Cambio: apuntar a contrato final decidido (ideal `/notas-credito/` ya implementado en backend); ajustar DTO de creación para enviar `factura_id` + `motivo` + `items[]` (o contrato definitivo).
- Dependencias: backend expuesto y documentado.
- Compatibilidad: rompe internamente tipos actuales; requiere actualizar formulario.
- Prioridad: crítica.

2) `frontend/src/modules/documentosSoporte/services/documentosSoporteApi.ts`
- Problema: payload y rutas no compatibles con backend actual.
- Cambio: adaptar creación a `proveedor_tipo_documento`, `items[{descripcion,cantidad,precio}]`, y rutas definitivas de list/create/xml/pdf.
- Dependencias: backend final de documentos soporte.
- Compatibilidad: rompe tipos actuales de formulario.
- Prioridad: crítica.

3) `frontend/src/modules/documentosSoporte/components/DocumentoSoporteForm.tsx`
- Problema: envía `tipo_documento_proveedor`, `descripcion`, `valor_unitario` en vez de contrato esperado por backend.
- Cambio: construir `items[]` y renombrar campo de tipo documento a `proveedor_tipo_documento`.
- Dependencias: tipos en `documentosSoporteApi.ts`.
- Compatibilidad: cambia interfaz de submit del componente.
- Prioridad: crítica.

4) `frontend/src/modules/facturacionElectronica/services/facturacionApi.ts`
- Problema: `getEstadoFactura` espera `{estado}`; backend actual devuelve `status/estado_dian`. Descargas esperan blob aunque backend responde JSON path.
- Cambio: ajustar parser de estado para soportar `estado|estado_dian|status`; y adaptar descargas al contrato final (blob real o URL/path).
- Dependencias: normalización backend.
- Compatibilidad: retrocompatible si se implementa lectura flexible.
- Prioridad: alta.

5) `frontend/src/modules/facturacionElectronica/components/FacturasTable.tsx`
- Problema: usa `data.estado` directamente; se rompe si backend no lo envía.
- Cambio: usar campo normalizado desde servicio (`resolveEstado(data)`) y mantener fallback visual.
- Dependencias: `facturacionApi.ts`.
- Compatibilidad: no rompe UI.
- Prioridad: alta.

6) `frontend/src/modules/notasCredito/components/NotaCreditoForm.tsx`
- Problema: estructura de payload no corresponde a la emisión backend (`items_ajustar` string + `valor_ajuste`).
- Cambio: permitir captura estructurada de `items[]` y `factura_id`/selector factura emitida.
- Dependencias: contrato backend notas y tipos API.
- Compatibilidad: rompe contrato interno actual.
- Prioridad: alta.

7) `frontend/src/modules/notasCredito/pages/NotasCreditoPage.tsx` y `components/NotasCreditoTable.tsx`
- Problema: asumen estructura de listado no confirmada por backend final.
- Cambio: alinear columnas y acciones al DTO real de listado (`numero`, `factura`, `estado`, `created_at`, rutas xml/pdf).
- Dependencias: serializer backend de listado.
- Compatibilidad: posible ajuste visual menor.
- Prioridad: media-alta.

8) `frontend/src/modules/documentosSoporte/pages/DocumentosSoportePage.tsx` y `components/DocumentosSoporteTable.tsx`
- Problema: asumen respuesta con `fecha/total/estado_dian` no garantizada por backend actual.
- Cambio: alinear tabla a contrato backend y rutas reales de descarga.
- Dependencias: serializer backend documentos soporte.
- Compatibilidad: posible ajuste visual menor.
- Prioridad: media-alta.

## Orden exacto de ejecución para evitar retrabajo

Fase 1 (Backend contrato)
1. Definir contrato final de recursos (`/facturacion`, `/notas-credito`, `/documentos-soporte`) y shape de respuesta (`estado` canónico).
2. Modificar `serializers/__init__.py` para normalizar estado sin romper compatibilidad.
3. Crear serializers nuevos de notas/documentos.
4. Refactor en `views.py` con viewsets separados y acciones xml/pdf.
5. Registrar rutas nuevas en `config/api_router.py`.

Fase 2 (Backend descargas y persistencia)
6. Decidir estrategia de descarga (blob directo vs path local).
7. Ajustar `models.py` + migración (si habrá rutas locales para nota/doc).
8. Implementar/ajustar servicios de descarga.

Fase 3 (Frontend integración)
9. Ajustar servicios API (`facturacionApi.ts`, `notasCreditoApi.ts`, `documentosSoporteApi.ts`).
10. Ajustar formularios (`DocumentoSoporteForm.tsx`, `NotaCreditoForm.tsx`).
11. Ajustar tablas/páginas (`FacturasTable.tsx`, `NotasCreditoTable.tsx`, `DocumentosSoporteTable.tsx`).

Fase 4 (Validación)
12. Completar pruebas backend (`tests.py`) y smoke e2e manual UI.
13. Retirar compatibilidad temporal antigua cuando ya no haya consumidores.
