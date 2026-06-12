import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("printing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="printrequest",
            name="model_file",
            field=models.FileField(
                blank=True,
                upload_to="printing/models/%Y/%m/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ["stl", "3mf", "step", "stp", "obj"]
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="printrequest",
            name="preferred_settings",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="printrequest",
            name="estimate_screenshot",
            field=models.FileField(
                blank=True,
                upload_to="printing/estimates/%Y/%m/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ["png", "jpg", "jpeg", "webp", "pdf"]
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="printrequest",
            name="preview_screenshot",
            field=models.FileField(
                blank=True,
                upload_to="printing/previews/%Y/%m/",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        ["png", "jpg", "jpeg", "webp", "pdf"]
                    )
                ],
            ),
        ),
    ]
