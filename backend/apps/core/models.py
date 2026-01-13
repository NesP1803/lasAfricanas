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
        ('Persona natural', 'Persona natural'),
        ('Persona jurídica', 'Persona jurídica'),
    ]

    REGIMEN_CHOICES = [
        ('RÉGIMEN COMÚN', 'RÉGIMEN COMÚN'),
        ('RÉGIMEN SIMPLIFICADO', 'RÉGIMEN SIMPLIFICADO'),
    ]

    tipo_identificacion = models.CharField(
        max_length=10,
        choices=TIPO_IDENTIFICACION_CHOICES,
        default='NIT'
    )
    identificacion = models.CharField(max_length=20)
    dv = models.CharField(max_length=1, blank=True)
    tipo_persona = models.CharField(
        max_length=20,
        choices=TIPO_PERSONA_CHOICES,
        default='Persona natural'
    )
    razon_social = models.CharField(max_length=200)
    regimen = models.CharField(
        max_length=25,
        choices=REGIMEN_CHOICES,
        default='RÉGIMEN COMÚN'
    )
    direccion = models.CharField(max_length=200)
    ciudad = models.CharField(max_length=100)
    municipio = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True)
    sitio_web = models.URLField(blank=True)
    correo = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='empresa/', blank=True, null=True)

    class Meta:
        db_table = 'configuracion_empresa'
        verbose_name = 'Configuración de Empresa'
        verbose_name_plural = 'Configuración de Empresa'

    def __str__(self):
        return self.razon_social


class Impuesto(BaseModel):
    """Impuestos configurables del sistema (IVA, etc.)"""
    nombre = models.CharField(max_length=50)
    valor = models.CharField(max_length=10)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    es_exento = models.BooleanField(default=False)

    class Meta:
        db_table = 'impuestos'
        verbose_name = 'Impuesto'
        verbose_name_plural = 'Impuestos'

    def __str__(self):
        return f"{self.nombre} - {self.valor}"


class Auditoria(models.Model):
    """Registro de auditoría para rastrear cambios en el sistema"""
    ACCION_CHOICES = [
        ('CREAR', 'Crear'),
        ('ACTUALIZAR', 'Actualizar'),
        ('ELIMINAR', 'Eliminar'),
        ('LOGIN', 'Inicio de sesión'),
        ('LOGOUT', 'Cierre de sesión'),
        ('OTRO', 'Otro'),
    ]

    fecha_hora = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias'
    )
    usuario_nombre = models.CharField(max_length=150)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    modelo = models.CharField(max_length=100, blank=True)
    objeto_id = models.CharField(max_length=100, blank=True)
    notas = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'auditoria'
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')} - {self.usuario_nombre} - {self.accion}"


class ConfiguracionFacturacion(models.Model):
    """Configuración de facturación y numeración"""
    prefijo_factura = models.CharField(max_length=10, default='FAC')
    numero_factura = models.IntegerField(default=1)
    prefijo_remision = models.CharField(max_length=10, blank=True)
    numero_remision = models.IntegerField(default=1)
    resolucion = models.TextField(blank=True)
    notas_factura = models.TextField(blank=True)

    class Meta:
        db_table = 'configuracion_facturacion'
        verbose_name = 'Configuración de Facturación'
        verbose_name_plural = 'Configuración de Facturación'

    def __str__(self):
        return "Configuración de Facturación"