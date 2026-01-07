from django.db import models


class BaseModel(models.Model):
    """
    Modelo base abstracto para todos los modelos del sistema.
    Incluye campos comunes: timestamps y soft delete.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Fecha de creación'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de actualización'
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Activo'
    )

    class Meta:
        abstract = True  # IMPORTANTE: Esto hace que no cree tabla en BD
        ordering = ['-created_at']  # Ordena por más reciente primero

    def soft_delete(self):
        """Elimina el registro de forma lógica (soft delete)"""
        self.is_active = False
        self.save()

    def restore(self):
        """Restaura un registro eliminado lógicamente"""
        self.is_active = True
        self.save()