from rest_framework import serializers
from .models import ImportJob, ImportFile, ImportSheetAnalysis, ImportRowResult, ImportProfile, ExportProfile, ExportJob


class ImportRowResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRowResult
        fields = '__all__'


class ImportSheetAnalysisSerializer(serializers.ModelSerializer):
    row_results = ImportRowResultSerializer(many=True, read_only=True)

    class Meta:
        model = ImportSheetAnalysis
        fields = '__all__'


class ImportFileSerializer(serializers.ModelSerializer):
    sheets = ImportSheetAnalysisSerializer(many=True, read_only=True)

    class Meta:
        model = ImportFile
        fields = '__all__'


class ImportJobSerializer(serializers.ModelSerializer):
    files = ImportFileSerializer(many=True, read_only=True)

    class Meta:
        model = ImportJob
        fields = '__all__'


class ImportAnalyzeSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField(required=False)
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False)


class ImportExecuteSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()


class ExportProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportProfile
        fields = '__all__'


class ExportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportJob
        fields = '__all__'


class ExportGenerateSerializer(serializers.Serializer):
    profile_code = serializers.CharField()
