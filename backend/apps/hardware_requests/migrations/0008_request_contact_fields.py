from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hardware_requests", "0007_public_tool_loan_nullable_qr"),
    ]

    operations = [
        migrations.AddField(
            model_name="hardwarerequest",
            name="requester_contact_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="hardwarerequest",
            name="requester_contact_phone",
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
