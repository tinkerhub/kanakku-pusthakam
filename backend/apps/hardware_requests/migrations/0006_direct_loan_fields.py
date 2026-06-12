from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hardware_requests", "0005_public_tool_loan"),
    ]

    operations = [
        migrations.AddField(
            model_name="publictoolloan",
            name="source",
            field=models.CharField(
                choices=[
                    ("public_self_checkout", "Public Self Checkout"),
                    ("admin_direct", "Admin Direct"),
                ],
                db_index=True,
                default="public_self_checkout",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="publictoolloan",
            name="due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
