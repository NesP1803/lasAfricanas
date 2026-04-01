from apps.intercambio_datos.services.analyzers.header_matcher import normalize_header


def map_fields(headers, entity_fields):
    mapping = {}
    by_norm = {normalize_header(h): h for h in headers}
    for field in entity_fields:
        if field in by_norm:
            mapping[by_norm[field]] = field
    return mapping
