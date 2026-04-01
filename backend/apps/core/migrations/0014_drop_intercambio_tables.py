from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_merge_20260329_2259'),
    ]

    operations = [
        migrations.RunSQL(
            sql='''
            DROP TABLE IF EXISTS intercambio_import_row_result CASCADE;
            DROP TABLE IF EXISTS intercambio_import_sheet_analysis CASCADE;
            DROP TABLE IF EXISTS intercambio_import_file CASCADE;
            DROP TABLE IF EXISTS intercambio_import_job CASCADE;
            DROP TABLE IF EXISTS intercambio_export_job CASCADE;
            DROP TABLE IF EXISTS intercambio_import_profile CASCADE;
            DROP TABLE IF EXISTS intercambio_export_profile CASCADE;
            DELETE FROM django_migrations WHERE app = 'intercambio_datos';
            ''',
            reverse_sql='''
            -- irreversible cleanup migration
            ''',
        ),
    ]
