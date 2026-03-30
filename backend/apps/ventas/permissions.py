from __future__ import annotations


def is_admin_user(user) -> bool:
    return bool(
        user
        and (
            user.is_superuser
            or user.is_staff
            or getattr(user, 'tipo_usuario', None) == 'ADMIN'
        )
    )


def has_caja_access(user) -> bool:
    return bool(
        is_admin_user(user)
        or getattr(user, 'es_cajero', False)
        or user.has_perm('ventas.caja_facturar')
    )
