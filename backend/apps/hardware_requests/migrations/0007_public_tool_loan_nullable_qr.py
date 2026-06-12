import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("boxes", "0006_qr_scan_event_immutable_triggers"),
        ("hardware_requests", "0006_direct_loan_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="publictoolloan",
            name="qr_code",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="public_tool_loans",
                to="boxes.qrcode",
            ),
        ),
    ]
