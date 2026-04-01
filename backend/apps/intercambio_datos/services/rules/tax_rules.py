from decimal import Decimal

EXENTO_WORDS = {'exento', 'exenta', 'excluido', 'excluida'}


def parse_tax_value(value):
    text = str(value or '').strip().lower().replace('%', '')
    if not text:
        return None, ['valor impuesto vacío']
    if text in EXENTO_WORDS:
        return {'iva_porcentaje': Decimal('0.00'), 'iva_exento': True}, []
    try:
        number = Decimal(text)
        if number == 0:
            return {'iva_porcentaje': Decimal('0.00'), 'iva_exento': False}, []
        if number == 19:
            return {'iva_porcentaje': Decimal('19.00'), 'iva_exento': False}, []
        return {'iva_porcentaje': number, 'iva_exento': False}, ['impuesto no estándar, revisar']
    except Exception:
        return None, [f'impuesto inválido: {value}']
