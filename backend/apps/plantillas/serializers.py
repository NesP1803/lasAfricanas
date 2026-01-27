from rest_framework import serializers

from .models import Template, TemplateVersion


class TemplateVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source='created_by.nombre_completo', read_only=True
    )

    class Meta:
        model = TemplateVersion
        fields = [
            'id',
            'version_number',
            'html',
            'css',
            'receipt_text',
            'created_by',
            'created_by_name',
            'created_at',
            'comment',
        ]
        read_only_fields = [
            'id',
            'version_number',
            'created_by',
            'created_at',
        ]


class TemplateSerializer(serializers.ModelSerializer):
    current_version = TemplateVersionSerializer(read_only=True)

    class Meta:
        model = Template
        fields = [
            'id',
            'name',
            'document_type',
            'output_type',
            'is_active',
            'current_version',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'current_version']


class TemplateCreateSerializer(serializers.ModelSerializer):
    html = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    css = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    receipt_text = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    comment = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Template
        fields = [
            'id',
            'name',
            'document_type',
            'output_type',
            'is_active',
            'html',
            'css',
            'receipt_text',
            'comment',
        ]


class TemplateVersionCreateSerializer(serializers.Serializer):
    html = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    css = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    receipt_text = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    comment = serializers.CharField(required=False, allow_blank=True)
