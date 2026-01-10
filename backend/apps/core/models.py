from django.db import models
from django.conf import settings


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


class ConfiguracionEmpresa(models.Model):
    """
    Configuración general de la empresa.
    Solo debe existir un registro.
    """
    TIPO_IDENTIFICACION_CHOICES = [
        ('NIT', 'NÚMERO DE IDENTIFICACIÓN TRIBUTARIA (NIT)'),
        ('CC', 'CÉDULA DE CIUDADANÍA'),
        ('CE', 'CÉDULA DE EXTRANJERÍA'),
    ]

    TIPO_PERSONA_CHOICES = [
        ('NATURAL', 'Persona natural'),
        ('JURIDICA', 'Persona jurídica'),
    ]

    REGIMEN_CHOICES = [
        ('COMUN', 'RÉGIMEN COMÚN'),
        ('SIMPLIFICADO', 'RÉGIMEN SIMPLIFICADO'),
    ]

    tipo_identificacion = models.CharField(
        max_length=10,
        choices=TIPO_IDENTIFICACION_CHOICES,
        default='NIT',
        verbose_name='Tipo de identificación'
    )
    identificacion = models.CharField(
        max_length=20,
        verbose_name='Número de identificación'
    )
    dv = models.CharField(
        max_length=1,
        blank=True,
        verbose_name='Dígito de verificación'
    )
    tipo_persona = models.CharField(
        max_length=20,
        choices=TIPO_PERSONA_CHOICES,
        default='NATURAL',
        verbose_name='Tipo de persona'
    )
    razon_social = models.CharField(
        max_length=200,
        verbose_name='Razón social'
    )
    regimen = models.CharField(
        max_length=20,
        choices=REGIMEN_CHOICES,
        default='COMUN',
        verbose_name='Régimen'
    )
    direccion = models.CharField(
        max_length=200,
        verbose_name='Dirección'
    )
    ciudad = models.CharField(
        max_length=100,
        verbose_name='Departamento/Ciudad'
    )
    municipio = models.CharField(
        max_length=100,
        verbose_name='Municipio'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono'
    )
    sitio_web = models.URLField(
        blank=True,
        verbose_name='Sitio web'
    )
    correo = models.EmailField(
        blank=True,
        verbose_name='Correo electrónico'
    )
    logo = models.ImageField(
        upload_to='empresa/',
        blank=True,
        null=True,
        verbose_name='Logo de la empresa'
    )

    class Meta:
        db_table = 'configuracion_empresa'
        verbose_name = 'Configuración de Empresa'
        verbose_name_plural = 'Configuración de Empresa'

    def __str__(self):
        return self.razon_social

    def save(self, *args, **kwargs):
        # Asegurar que solo exista un registro
        if not self.pk and ConfiguracionEmpresa.objects.exists():
            raise ValueError('Solo puede existir una configuración de empresa')
        return super().save(*args, **kwargs)


class Impuesto(BaseModel):
    """
    Impuestos configurables del sistema (IVA, etc.)
    """
    nombre = models.CharField(
        max_length=50,
        verbose_name='Nombre del impuesto'
    )
    valor = models.CharField(
        max_length=10,
        verbose_name='Valor',
        help_text='Puede ser porcentaje (19) o letra (E para exento)'
    )
    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Porcentaje',
        help_text='Valor numérico del porcentaje'
    )
    es_exento = models.BooleanField(
        default=False,
        verbose_name='Es exento'
    )

    class Meta:
        db_table = 'impuestos'
        verbose_name = 'Impuesto'
        verbose_name_plural = 'Impuestos'
        ordering = ['nombre', 'valor']

    def __str__(self):
        return f"{self.nombre} - {self.valor}"


class Auditoria(models.Model):
    """
    Registro de auditoría para rastrear cambios en el sistema.
    """
    ACCION_CHOICES = [
        ('CREAR', 'Crear'),
        ('ACTUALIZAR', 'Actualizar'),
        ('ELIMINAR', 'Eliminar'),
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
        ('OTRO', 'Otro'),
    ]

    fecha_hora = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y hora'
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias',
        verbose_name='Usuario'
    )
    usuario_nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre de usuario',
        help_text='Nombre del usuario que realizó la acción'
    )
    accion = models.CharField(
        max_length=20,
        choices=ACCION_CHOICES,
        verbose_name='Acción'
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Modelo afectado'
    )
    objeto_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='ID del objeto'
    )
    notas = models.TextField(
        verbose_name='Notas/Descripción'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )

    class Meta:
        db_table = 'auditoria'
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['-fecha_hora']),
            models.Index(fields=['usuario']),
            models.Index(fields=['accion']),
        ]

    def __str__(self):
        return f"{self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')} - {self.usuario_nombre} - {self.accion}"


class ConfiguracionFacturacion(models.Model):
    """
    Configuración de facturación y numeración.
    Solo debe existir un registro.
    """
    prefijo_factura = models.CharField(
        max_length=10,
        default='FAC',
        verbose_name='Prefijo de factura'
    )
    numero_factura = models.IntegerField(
        default=1,
        verbose_name='Próximo número de factura'
    )
    prefijo_remision = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Prefijo de remisión'
    )
    numero_remision = models.IntegerField(
        default=1,
        verbose_name='Próximo número de remisión'
    )
    resolucion = models.TextField(
        blank=True,
        verbose_name='Resolución DIAN'
    )
    notas_factura = models.TextField(
        blank=True,
        verbose_name='Notas en factura de venta'
    )

    class Meta:
        db_table = 'configuracion_facturacion'
        verbose_name = 'Configuración de Facturación'
        verbose_name_plural = 'Configuración de Facturación'

    def __str__(self):
        return f"Configuración de Facturación"

    def save(self, *args, **kwargs):
        # Asegurar que solo exista un registro
        if not self.pk and ConfiguracionFacturacion.objects.exists():
            raise ValueError('Solo puede existir una configuración de facturación')
        return super().save(*args, **kwargs)