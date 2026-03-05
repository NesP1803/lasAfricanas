from apps.facturacion_electronica.models import (
    HomologacionMedioPago,
    HomologacionMunicipio,
    HomologacionTributo,
    HomologacionUnidadMedida,
)


def get_municipality_id(codigo_interno: str, default: int = 149) -> int:
    return (
        HomologacionMunicipio.objects.filter(codigo_interno=str(codigo_interno)).values_list('municipality_id', flat=True).first()
        or default
    )


def get_tribute_id(codigo_interno: str, default: int = 1) -> int:
    return (
        HomologacionTributo.objects.filter(codigo_interno=str(codigo_interno)).values_list('tribute_id', flat=True).first()
        or default
    )


def get_unit_measure_id(codigo_interno: str, default: int = 70) -> int:
    return (
        HomologacionUnidadMedida.objects.filter(codigo_interno=str(codigo_interno)).values_list('unit_measure_id', flat=True).first()
        or default
    )


def get_payment_method_code(codigo_interno: str, default: str = '10') -> str:
    return (
        HomologacionMedioPago.objects.filter(codigo_interno=str(codigo_interno)).values_list('payment_method_code', flat=True).first()
        or default
    )
