from django.db import migrations, models
import django.db.models.constraints


def populate_public_keys(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    for makerspace in Makerspace.objects.all():
        makerspace.public_api_key = f"pk_{makerspace.pk:08x}000000000000000000000000"
        makerspace.cors_allowed_origins = []
        makerspace.save(update_fields=["public_api_key", "cors_allowed_origins"])


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0003_alter_makerspacemembership_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="makerspace",
            name="cors_allowed_origins",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="makerspace",
            name="public_api_key",
            field=models.CharField(blank=True, default="", editable=False, max_length=40),
        ),
        migrations.RunPython(populate_public_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="makerspace",
            name="public_api_key",
            field=models.CharField(editable=False, max_length=40),
        ),
        migrations.AddConstraint(
            model_name="makerspace",
            constraint=django.db.models.constraints.UniqueConstraint(
                fields=("public_api_key",),
                name="uniq_makerspace_public_api_key",
            ),
        ),
    ]
