from django.db import migrations, models
import apps.makerspaces.models
import django.core.validators
from django.utils.crypto import get_random_string


def generate_code():
    return get_random_string(4, allowed_chars="ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


def populate_codes(apps, schema_editor):
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    used = set(
        Makerspace.objects.exclude(public_code__isnull=True)
        .exclude(public_code="")
        .values_list("public_code", flat=True)
    )
    for makerspace in Makerspace.objects.filter(public_code__isnull=True):
        code = generate_code()
        while code in used:
            code = generate_code()
        used.add(code)
        makerspace.public_code = code
        makerspace.save(update_fields=["public_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0006_makerspace_integrations"),
    ]

    operations = [
        migrations.AddField(
            model_name="makerspace",
            name="public_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=4,
                null=True,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="Public code must be exactly 4 uppercase letters or digits.",
                        regex="^[A-Z0-9]{4}$",
                    )
                ],
            ),
        ),
        migrations.RunPython(populate_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="makerspace",
            name="public_code",
            field=models.CharField(
                default=apps.makerspaces.models.generate_public_code,
                db_index=True,
                max_length=4,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="Public code must be exactly 4 uppercase letters or digits.",
                        regex="^[A-Z0-9]{4}$",
                    )
                ],
            ),
        ),
    ]
