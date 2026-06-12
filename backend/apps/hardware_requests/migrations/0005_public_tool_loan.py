import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("boxes", "0006_qr_scan_event_immutable_triggers"),
        ("hardware_requests", "0004_return_records_immutable_triggers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicToolLoan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_type", models.CharField(max_length=20)),
                ("target_id", models.PositiveIntegerField()),
                ("target_label", models.CharField(max_length=200)),
                ("asset_ids", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(choices=[("checked_out", "Checked Out"), ("returned", "Returned")], db_index=True, default="checked_out", max_length=20)),
                ("checked_out_at", models.DateTimeField(auto_now_add=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="public_tool_loans", to="makerspaces.makerspace")),
                ("qr_code", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="public_tool_loans", to="boxes.qrcode")),
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="public_tool_loan", to="hardware_requests.hardwarerequest")),
                ("requester", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="public_tool_loans", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="publictoolloan",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "checked_out")), fields=("qr_code",), name="uniq_active_public_tool_loan_per_qr"),
        ),
        migrations.AddIndex(
            model_name="publictoolloan",
            index=models.Index(fields=["makerspace", "status"], name="hardware_re_makersp_4525eb_idx"),
        ),
        migrations.AddIndex(
            model_name="publictoolloan",
            index=models.Index(fields=["requester", "status"], name="hardware_re_request_4bb8e1_idx"),
        ),
    ]
