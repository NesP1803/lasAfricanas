from rest_framework.permissions import BasePermission


class IsIntercambioAdmin(BasePermission):
    message = 'Solo usuarios administradores pueden usar intercambio de datos.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or (getattr(user, 'tipo_usuario', '').upper() == 'ADMIN')
