from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hardware_requests", "0008_request_contact_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="publictoolloan",
            name="qr_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
