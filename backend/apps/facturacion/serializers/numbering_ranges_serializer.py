import re

from rest_framework import serializers

from apps.facturacion.models import RemisionNumeracion, RemisionNumeracionHistorial, RangoNumeracionDIAN


class RangoNumeracionDIANSerializer(serializers.ModelSerializer):
    id_factus = serializers.IntegerField(source='factus_id', allow_null=True)
    document_code_label = serializers.SerializerMethodField()
    is_near_expiration = serializers.SerializerMethodField()

    class Meta:
        model = RangoNumeracionDIAN
        fields = [
            'id',
            'id_factus',
            'factus_range_id',
            'environment',
            'document_code',
            'document_name',
            'document_code_label',
            'prefijo',
            'desde',
            'hasta',
            'consecutivo_actual',
            'resolucion',
            'fecha_autorizacion',
            'fecha_expiracion',
            'technical_key',
            'activo',
            'is_active_remote',
            'is_expired_remote',
            'is_associated_to_software',
            'is_selected_local',
            'is_near_expiration',
            'last_synced_at',
            'metadata_json',
        ]

    def get_document_code_label(self, obj: RangoNumeracionDIAN) -> str:
        return obj.get_document_code_display()

    def get_is_near_expiration(self, obj: RangoNumeracionDIAN) -> bool:
        if not obj.fecha_expiracion:
            return False
        from django.utils import timezone

        return (obj.fecha_expiracion - timezone.localdate()).days <= 15


class CreateRangoFactusSerializer(serializers.Serializer):
    document = serializers.ChoiceField(choices=['21', '22', '24'])
    prefix = serializers.CharField(max_length=20)
    current = serializers.IntegerField(min_value=1)
    resolution_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    technical_key = serializers.CharField(max_length=255, required=False, allow_blank=True)
    from_number = serializers.IntegerField(min_value=1, source='from')
    to_number = serializers.IntegerField(min_value=1, source='to')

    def validate(self, attrs):
        doc = attrs.get('document')
        resolution = (attrs.get('resolution_number') or '').strip()
        from_number = attrs.get('from')
        to_number = attrs.get('to')
        current = attrs.get('current')

        if doc in {'21', '24', '30'} and not resolution:
            raise serializers.ValidationError({'resolution_number': 'Este campo es obligatorio para el documento seleccionado.'})
        if from_number and to_number and from_number > to_number:
            raise serializers.ValidationError({'to_number': 'Debe ser mayor o igual que desde.'})
        if current and from_number and to_number and not (from_number <= current <= to_number):
            raise serializers.ValidationError({'current': 'Debe estar dentro del rango.'})

        return attrs


class LocalRangoNumeracionSerializer(serializers.ModelSerializer):
    MODE_AUTHORIZED = 'autorizado'
    MODE_MANUAL = 'manual'

    activate_now = serializers.BooleanField(write_only=True, required=False, default=False)
    create_mode = serializers.ChoiceField(choices=[MODE_AUTHORIZED, MODE_MANUAL], required=False, default=MODE_MANUAL, write_only=True)

    class Meta:
        model = RangoNumeracionDIAN
        fields = [
            'id',
            'environment',
            'document_code',
            'document_name',
            'factus_id',
            'factus_range_id',
            'prefijo',
            'desde',
            'hasta',
            'consecutivo_actual',
            'resolucion',
            'fecha_autorizacion',
            'fecha_expiracion',
            'technical_key',
            'is_active_remote',
            'is_expired_remote',
            'is_associated_to_software',
            'is_selected_local',
            'activo',
            'metadata_json',
            'activate_now',
            'create_mode',
        ]
        read_only_fields = ['id', 'environment', 'is_expired_remote', 'document_name']

    def validate(self, attrs):
        instance = self.instance
        document_code = attrs.get('document_code', getattr(instance, 'document_code', 'FACTURA_VENTA'))
        mode = attrs.get('create_mode', self.MODE_MANUAL)
        prefijo = (attrs.get('prefijo', getattr(instance, 'prefijo', '')) or '').strip()
        desde = attrs.get('desde', getattr(instance, 'desde', 0))
        hasta = attrs.get('hasta', getattr(instance, 'hasta', 0))
        actual = attrs.get('consecutivo_actual', getattr(instance, 'consecutivo_actual', 0))
        resolucion = (attrs.get('resolucion', getattr(instance, 'resolucion', '')) or '').strip()
        fecha_autorizacion = attrs.get('fecha_autorizacion', getattr(instance, 'fecha_autorizacion', None))
        fecha_expiracion = attrs.get('fecha_expiracion', getattr(instance, 'fecha_expiracion', None))
        factus_range_id = int(attrs.get('factus_range_id', getattr(instance, 'factus_range_id', 0)) or 0)

        if not document_code:
            raise serializers.ValidationError({'document_code': 'El tipo de documento es obligatorio.'})
        if not prefijo:
            raise serializers.ValidationError({'prefijo': 'El prefijo es obligatorio.'})
        if desde > hasta:
            raise serializers.ValidationError({'hasta': 'Debe ser mayor o igual que desde.'})
        if not (desde <= actual <= hasta):
            raise serializers.ValidationError({'consecutivo_actual': 'Debe estar dentro del rango configurado.'})
        if not re.fullmatch(r'[A-Za-z0-9-]{1,20}', prefijo):
            raise serializers.ValidationError({'prefijo': 'Solo se permiten letras, números y guion (máximo 20 caracteres).'})
        if fecha_autorizacion and fecha_expiracion and fecha_expiracion < fecha_autorizacion:
            raise serializers.ValidationError({'fecha_expiracion': 'Debe ser mayor o igual a la fecha de expedición.'})
        if document_code in {'FACTURA_VENTA', 'DOCUMENTO_SOPORTE'} and not resolucion:
            raise serializers.ValidationError({'resolucion': 'Este campo es obligatorio para el documento seleccionado.'})
        if mode == self.MODE_AUTHORIZED and factus_range_id <= 0:
            raise serializers.ValidationError({'factus_range_id': 'En modo autorizado debe seleccionar una resolución de Factus.'})

        environment = attrs.get('environment', getattr(instance, 'environment', None))
        queryset = RangoNumeracionDIAN.objects.filter(
            environment=environment,
            document_code=document_code,
            prefijo__iexact=prefijo,
            desde=desde,
            hasta=hasta,
        )
        if instance:
            queryset = queryset.exclude(pk=instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                {'prefijo': 'Ya existe un rango equivalente para este documento con el mismo prefijo y límites.'}
            )
        return attrs


class UpdateConsecutivoSerializer(serializers.Serializer):
    current = serializers.IntegerField(min_value=1)
    sync_local = serializers.BooleanField(default=True)


class SelectActiveRangeSerializer(serializers.Serializer):
    ELECTRONIC_DOCUMENT_CODES = {
        'FACTURA_VENTA',
        'NOTA_CREDITO',
        'NOTA_DEBITO',
        'DOCUMENTO_SOPORTE',
        'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
    }

    document_code = serializers.ChoiceField(choices=RangoNumeracionDIAN.DOCUMENT_CODE_CHOICES)

    def validate_document_code(self, value: str) -> str:
        if value not in self.ELECTRONIC_DOCUMENT_CODES:
            raise serializers.ValidationError(
                'Solo se puede seleccionar numbering_range_id para documentos electrónicos.'
            )
        return value


class AuthorizedAvailableRangeSerializer(serializers.Serializer):
    remote_id = serializers.IntegerField()
    factus_range_id = serializers.IntegerField()
    document = serializers.CharField()
    document_code = serializers.CharField()
    prefix = serializers.CharField()
    from_number = serializers.IntegerField(source='from')
    to_number = serializers.IntegerField(source='to')
    current = serializers.IntegerField()
    resolution_number = serializers.CharField(allow_blank=True)
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    technical_key = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    is_associated_to_software = serializers.BooleanField()


class RemisionNumeracionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemisionNumeracion
        fields = [
            'id',
            'prefix',
            'current',
            'range_from',
            'range_to',
            'resolution_reference',
            'notes',
            'updated_by',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_by', 'updated_at']

    def validate(self, attrs):
        current = attrs.get('current', getattr(self.instance, 'current', 1))
        range_from = attrs.get('range_from', getattr(self.instance, 'range_from', 1))
        range_to = attrs.get('range_to', getattr(self.instance, 'range_to', 1))
        prefix = (attrs.get('prefix', getattr(self.instance, 'prefix', '')) or '').strip()
        if not prefix:
            raise serializers.ValidationError({'prefix': 'El prefijo de remisión es obligatorio.'})
        if range_from > range_to:
            raise serializers.ValidationError({'range_to': 'Debe ser mayor o igual al inicio.'})
        if current < range_from or current > range_to:
            raise serializers.ValidationError({'current': 'Debe estar dentro del rango configurado.'})
        return attrs


class RemisionNumeracionHistorialSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RemisionNumeracionHistorial
        fields = ['id', 'numeracion', 'previous_data', 'new_data', 'changed_by', 'changed_by_name', 'changed_at']

    def get_changed_by_name(self, obj: RemisionNumeracionHistorial) -> str:
        if obj.changed_by:
            return obj.changed_by.get_full_name() or obj.changed_by.username
        return 'Sistema'
