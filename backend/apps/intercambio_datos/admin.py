from django.contrib import admin
from .models import ImportProfile, ImportJob, ImportFile, ImportSheetAnalysis, ImportRowResult, ExportProfile, ExportJob

admin.site.register(ImportProfile)
admin.site.register(ImportJob)
admin.site.register(ImportFile)
admin.site.register(ImportSheetAnalysis)
admin.site.register(ImportRowResult)
admin.site.register(ExportProfile)
admin.site.register(ExportJob)
