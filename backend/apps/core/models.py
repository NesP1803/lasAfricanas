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
    TIPO_IDENTIFICACION = [
        ('NIT', 'NÚMERO DE IDENTIFICACIÓN TRIBUTARIA (NIT)'),
        ('CC', 'CÉDULA DE CIUDADANÍA'),
        ('CE', 'CÉDULA DE EXTRANJERÍA'),
    ]

    TIPO_PERSONA = [
        ('Persona natural', 'Persona natural'),
        ('Persona jurídica', 'Persona jurídica'),
    ]

    REGIMEN = [
        ('RÉGIMEN COMÚN', 'RÉGIMEN COMÚN'),
        ('RÉGIMEN SIMPLIFICADO', 'RÉGIMEN SIMPLIFICADO'),
    ]

    tipo_identificacion = models.CharField(
        max_length=10,
        choices=TIPO_IDENTIFICACION,
        default='NIT',
    )
    identificacion = models.CharField(max_length=20)
    dv = models.CharField(max_length=1, blank=True)
    tipo_persona = models.CharField(
        max_length=20,
        choices=TIPO_PERSONA,
        default='Persona natural',
    )
    razon_social = models.CharField(max_length=200)
    regimen = models.CharField(
        max_length=25,
        choices=REGIMEN,
        default='RÉGIMEN COMÚN',
    )
    direccion = models.CharField(max_length=200)
    ciudad = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True)
    sitio_web = models.URLField(blank=True)
    correo = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='empresa/', blank=True, null=True)

    class Meta:
        verbose_name = 'Configuración de Empresa'
        verbose_name_plural = 'Configuración de Empresa'
        db_table = 'configuracion_empresa'

    def __str__(self):
        return self.razon_social


class ConfiguracionFacturacion(models.Model):
    FACTUS_OPERATION_MODES = [
        ('FACTUS_MANAGED', 'Numeración oficial gestionada en Factus'),
    ]

    prefijo_factura = models.CharField(max_length=10, default='FAC')
    numero_factura = models.IntegerField(default=1)
    prefijo_remision = models.CharField(max_length=10, blank=True)
    numero_remision = models.IntegerField(default=1)
    resolucion = models.TextField(blank=True)
    ambiente_factus = models.CharField(max_length=20, default='SANDBOX')
    factus_numbering_range_id_factura_venta = models.PositiveIntegerField(null=True, blank=True)
    factus_numbering_range_id_nota_credito = models.PositiveIntegerField(null=True, blank=True)
    prefijo_factura_electronica = models.CharField(max_length=20, blank=True, default='')
    modo_operacion_electronica = models.CharField(
        max_length=30,
        choices=FACTUS_OPERATION_MODES,
        default='FACTUS_MANAGED',
    )
    permitir_cache_metadatos_factus = models.BooleanField(default=True)
    notas_factura = models.TextField(blank=True)
    plantilla_factura_carta = models.TextField(blank=True)
    plantilla_factura_tirilla = models.TextField(blank=True)
    plantilla_remision_carta = models.TextField(blank=True)
    plantilla_remision_tirilla = models.TextField(blank=True)
    plantilla_nota_credito_carta = models.TextField(blank=True)
    plantilla_nota_credito_tirilla = models.TextField(blank=True)
    redondeo_caja_efectivo = models.BooleanField(default=True)
    redondeo_caja_incremento = models.PositiveIntegerField(default=100)

    class Meta:
        verbose_name = 'Configuración de Facturación'
        verbose_name_plural = 'Configuración de Facturación'
        db_table = 'configuracion_facturacion'

    def __str__(self):
        return f"{self.prefijo_factura} {self.numero_factura}"


class Impuesto(BaseModel):
    nombre = models.CharField(max_length=50)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    factus_tribute_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'Impuesto'
        verbose_name_plural = 'Impuestos'
        db_table = 'impuestos'
        ordering = ['nombre', 'id']

    def __str__(self):
        return self.nombre


class Auditoria(models.Model):
    ACCION_CHOICES = [
        ('CREAR', 'Crear'),
        ('ACTUALIZAR', 'Actualizar'),
        ('ELIMINAR', 'Eliminar'),
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
        ('OTRO', 'Otro'),
    ]

    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='auditorias',
        null=True,
        blank=True,
    )
    usuario_nombre = models.CharField(max_length=150)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES, db_index=True)
    modelo = models.CharField(max_length=100, blank=True, db_index=True)
    objeto_id = models.CharField(max_length=100, blank=True, db_index=True)
    notas = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        db_table = 'auditoria'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['-fecha_hora'], name='auditoria_fh_idx'),
            models.Index(fields=['usuario', '-fecha_hora'], name='auditoria_user_fh_idx'),
            models.Index(fields=['accion', '-fecha_hora'], name='auditoria_act_fh_idx'),
        ]

    def __str__(self):
        return f"{self.usuario_nombre} - {self.accion}"


class AuditoriaArchivo(models.Model):
    fecha_hora = models.DateTimeField(db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='auditorias_archivo',
        null=True,
        blank=True,
    )
    usuario_nombre = models.CharField(max_length=150)
    accion = models.CharField(max_length=20, choices=Auditoria.ACCION_CHOICES, db_index=True)
    modelo = models.CharField(max_length=100, blank=True, db_index=True)
    objeto_id = models.CharField(max_length=100, blank=True, db_index=True)
    notas = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    archivado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Registro de Auditoría Archivado'
        verbose_name_plural = 'Registros de Auditoría Archivados'
        db_table = 'auditoria_archivo'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['-fecha_hora'], name='aud_arch_fh_idx'),
            models.Index(fields=['usuario', '-fecha_hora'], name='aud_arch_user_fh_idx'),
            models.Index(fields=['accion', '-fecha_hora'], name='aud_arch_act_fh_idx'),
        ]

    def __str__(self):
        return f"{self.usuario_nombre} - {self.accion} (archivado)"
