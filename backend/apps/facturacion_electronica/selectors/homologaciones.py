from apps.facturacion_electronica.catalogos.models import (
    DocumentoIdentificacionFactus,
    MetodoPagoFactus,
    MunicipioFactus,
    TributoFactus,
    UnidadMedidaFactus,
)


def get_municipality_id(codigo: str, default: int = 149) -> int:
    return (
        MunicipioFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
        or default
    )


def get_tribute_id(codigo: str, default: int = 1) -> int:
    return (
        TributoFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
        or default
    )


def get_unit_measure_id(codigo: str, default: int = 70) -> int:
    return (
        UnidadMedidaFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
        or default
    )


def get_payment_method_code(codigo: str, default: str = '10') -> str:
    return (
        MetodoPagoFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('codigo', flat=True)
        .first()
        or default
    )


def get_identification_document_id(codigo: str, default: int = 3) -> int:
    return (
        DocumentoIdentificacionFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
        or default
    )
