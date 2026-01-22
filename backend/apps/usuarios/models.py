from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models import BaseModel


class Usuario(AbstractUser):
    """
    Usuario extendido del sistema.
    Extiende el modelo de usuario de Django con campos adicionales.
    """
    TIPO_USUARIO = [
        ('ADMIN', 'Administrador'),
        ('VENDEDOR', 'Vendedor'),
        ('MECANICO', 'Mecánico'),
        ('BODEGUERO', 'Bodeguero'),
    ]

    SEDE_CHOICES = [
        ('GAIRA', 'Gaira - Santa Marta'),
    ]

    tipo_usuario = models.CharField(
        max_length=20,
        choices=TIPO_USUARIO,
        default='VENDEDOR',
        verbose_name='Tipo de usuario'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono'
    )
    sede = models.CharField(
        max_length=50,
        choices=SEDE_CHOICES,
        blank=True,
        verbose_name='Sede'
    )
    modulos_permitidos = models.JSONField(
        null=True,
        blank=True,
        default=None,
        verbose_name='Módulos permitidos',
        help_text='Configuración de acceso a módulos y secciones del sistema'
    )
    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_tipo_usuario_display()})"
    
    @property
    def nombre_completo(self):
        """Retorna el nombre completo del usuario"""
        return self.get_full_name() or self.username


class PerfilVendedor(BaseModel):
    """
    Perfil extendido para vendedores.
    Define permisos específicos sobre descuentos y operaciones.
    """
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name='perfil_vendedor',
        verbose_name='Usuario'
    )
    
    # Permisos de descuentos
    descuento_maximo = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        verbose_name='Descuento máximo sin aprobación (%)',
        help_text='Porcentaje máximo de descuento que puede aplicar sin autorización'
    )
    
    # Permisos operacionales
    puede_eliminar_ventas = models.BooleanField(
        default=False,
        verbose_name='Puede eliminar ventas'
    )
    puede_ver_costo = models.BooleanField(
        default=False,
        verbose_name='Puede ver precio de costo'
    )
    puede_modificar_precios = models.BooleanField(
        default=False,
        verbose_name='Puede modificar precios'
    )
    
    # Comisiones
    comision_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Comisión (%)',
        help_text='Porcentaje de comisión sobre ventas'
    )
    
    # Metas
    meta_mensual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Meta mensual de ventas'
    )
    
    class Meta:
        db_table = 'perfiles_vendedor'
        verbose_name = 'Perfil de Vendedor'
        verbose_name_plural = 'Perfiles de Vendedor'
    
    def __str__(self):
        return f"Perfil de {self.usuario.username}"
    
    def puede_aplicar_descuento(self, descuento_porcentaje):
        """
        Verifica si el vendedor puede aplicar un descuento específico.
        
        Args:
            descuento_porcentaje (Decimal): Porcentaje de descuento a verificar
            
        Returns:
            tuple: (puede_aplicar: bool, requiere_aprobacion: bool)
        """
        if descuento_porcentaje <= self.descuento_maximo:
            return (True, False)  # Puede aplicarlo sin aprobación
        else:
            return (False, True)  # Requiere aprobación del gerente
