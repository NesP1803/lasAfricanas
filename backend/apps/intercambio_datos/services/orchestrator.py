import hashlib
from django.db import transaction

from apps.intercambio_datos.models import ImportSheetAnalysis, ImportRowResult
from apps.intercambio_datos.services.analyzers.sheet_classifier import classify_sheet
from apps.intercambio_datos.services.mappers.field_mapper import map_fields
from apps.intercambio_datos.services.parsers.csv_parser import parse_csv
from apps.intercambio_datos.services.parsers.excel_parser import parse_excel
from apps.intercambio_datos.services.parsers.ods_parser import parse_ods
from apps.intercambio_datos.services.importers import (
    clientes_importer,
    productos_importer,
    ventas_importer,
    detalles_importer,
    motos_importer,
    mecanicos_importer,
)

ENTITY_FIELDS = {
    'clientes': ['numero_documento', 'nombre', 'telefono', 'email', 'direccion', 'ciudad'],
    'productos': ['codigo', 'nombre', 'categoria', 'proveedor', 'precio_costo', 'precio_venta', 'impuesto'],
    'ventas': ['numero_comprobante', 'cliente_documento', 'subtotal', 'iva', 'total', 'medio_pago'],
    'detalles_venta': ['venta_numero', 'producto_codigo', 'cantidad', 'precio_unitario', 'iva_porcentaje'],
    'motos': ['placa', 'marca', 'modelo', 'cliente_documento'],
    'mecanicos': ['nombre', 'telefono', 'email'],
}


def parse_file(path, extension):
    if extension == '.csv':
        return parse_csv(path)
    if extension in {'.xlsx', '.xlsm', '.xls'}:
        return parse_excel(path, extension)
    if extension == '.ods':
        return parse_ods(path)
    raise ValueError('Formato no soportado')


def checksum_bytes(content):
    return hashlib.sha256(content).hexdigest()


def analyze_file(import_file):
    sheets = parse_file(import_file.archivo.path, import_file.extension)
    created = []
    for sheet in sheets:
        entity, confidence, _ = classify_sheet(sheet['sheet_name'], sheet['headers'])
        mapping = map_fields(sheet['headers'], ENTITY_FIELDS.get(entity, [])) if entity != 'ambigua' else {}
        analysis = ImportSheetAnalysis.objects.create(
            file=import_file,
            sheet_name=sheet['sheet_name'],
            entidad_detectada=entity,
            confianza=confidence,
            estado='ANALIZADA',
            mapping=mapping,
            resumen={'rows': len(sheet['rows']), 'headers': sheet['headers'], 'raw_rows': sheet['rows']},
        )
        created.append(analysis)
    return created


def _import_entity(entity, row, user, precio_fuente):
    if entity == 'clientes':
        return clientes_importer.import_row(row)
    if entity == 'productos':
        return productos_importer.import_row(row, precio_fuente=precio_fuente)
    if entity == 'ventas':
        return ventas_importer.import_row(row, fallback_user=user)
    if entity == 'detalles_venta':
        return detalles_importer.import_row(row)
    if entity == 'motos':
        return motos_importer.import_row(row)
    if entity == 'mecanicos':
        return mecanicos_importer.import_row(row)
    return 'OMITIDA', None, f'entidad no implementada: {entity}'


def execute_job(job):
    results = {'INSERTADA': 0, 'ACTUALIZADA': 0, 'OMITIDA': 0, 'AMBIGUA': 0, 'ERROR': 0, 'WARNING': 0}
    with transaction.atomic():
        for file in job.files.all():
            for sheet in file.sheets.all():
                entity = sheet.entidad_detectada
                rows = sheet.resumen.get('raw_rows', [])
                if entity == 'ambigua':
                    for idx, _ in enumerate(rows, start=2):
                        ImportRowResult.objects.create(job=job, file=file, sheet=sheet, row_number=idx, action='AMBIGUA', message='Hoja ambigua')
                        results['AMBIGUA'] += 1
                    continue
                for idx, row in enumerate(rows, start=2):
                    action, obj, message = _import_entity(entity, row, job.usuario, job.perfil.precio_fuente)
                    ImportRowResult.objects.create(
                        job=job,
                        file=file,
                        sheet=sheet,
                        row_number=idx,
                        action=action if action in results else 'WARNING',
                        natural_key=str(getattr(obj, 'pk', '') or row.get('codigo') or row.get('numero_documento') or ''),
                        message=message,
                        payload=row,
                    )
                    results[action if action in results else 'WARNING'] += 1
    return results
