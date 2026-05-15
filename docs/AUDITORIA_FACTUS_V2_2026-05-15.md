# Auditoría rápida: integración Factus API v2 (2026-05-15)

## Alcance revisado
- Cliente HTTP y registro de endpoints versionados.
- Flujos de autenticación y refresh token.
- Endpoints de facturas, notas crédito, documentos soporte, notas de ajuste y rangos.
- Constructor de payload v2 para cambios de campos frente a v1.

## Resultado ejecutivo
**Estado general: parcialmente compatible con v2.**

El repositorio tiene una base sólida para v2 (versionado, endpoints principales y payload builder v2), pero aún hay brechas para afirmar cumplimiento “completo” de la cobertura oficial de la documentación compartida.

## Hallazgos

### ✅ Lo que está correcto para v2
1. **Versión por defecto en v2** (`FACTUS_API_VERSION=v2` por defecto).  
2. **Endpoints clave v2 de facturas** alineados: ver, listar, crear/validar, descargar PDF/XML, enviar correo y contenido de correo.  
3. **Endpoints clave v2 de notas crédito** alineados: crear/validar, listar, ver, descargar PDF/XML, correo y contenido de correo.  
4. **Autenticación OAuth y refresh** implementados en el cliente de Factus.  
5. **Soporte para payload builder v2** y coexistencia con compatibilidad v1 cuando no existe equivalente en v2.

### ⚠️ Brechas detectadas (importantes)
1. **Cobertura de endpoints v2 incompleta en `factus_endpoints.py`**:
   - Faltan rutas v2 para varios recursos que la documentación v2 expone (por ejemplo: algunos endpoints de rangos como cambio de estado, y cobertura explícita de XML AttachedDocument).
   - El sistema usa `FALLBACK_TO_V1` para nombres no definidos en v2, útil para transición, pero riesgoso si se pretende cumplimiento estricto v2.

2. **Dependencia de fallback implícito a v1**:
   - Si un endpoint no está en `DEFAULTS["v2"]`, la resolución cae a v1 automáticamente.
   - Esto evita romper integraciones, pero puede producir llamadas fuera de estándar v2 sin alertar.

3. **Cobertura funcional vs documentación oficial amplia**:
   - La lista oficial incluye áreas completas (recepción de documentos, suscripciones, empresas, tablas y catálogos extendidos, eventos completos, aceptación tácita, rangos avanzados, etc.).
   - El cliente tiene parte de esto, pero no una matriz de cobertura total endpoint-por-endpoint que certifique 100%.

## Recomendaciones prioritarias
1. **Eliminar ambigüedad de fallback** para ambientes que declaren cumplimiento v2 estricto:
   - Agregar modo “strict v2” (error si no existe endpoint v2 explícito).
2. **Completar `DEFAULTS["v2"]`** con todos los endpoints de la documentación oficial aplicables al producto.
3. **Crear matriz de trazabilidad** (doc endpoint ↔ método cliente ↔ servicio/uso ↔ test).
4. **Agregar tests automáticos de endpoints resueltos** por versión para detectar regresiones de rutas.
5. **Validar payloads v2 con fixtures oficiales** para factura estándar, crédito, excluido, redondeo, documento soporte y nota ajuste.

## Conclusión
Con el estado actual, **sí hay integración funcional con v2 en operaciones principales**, pero **no se puede afirmar cumplimiento completo** de toda la superficie de Factus v2 listada en la documentación oficial entregada.
