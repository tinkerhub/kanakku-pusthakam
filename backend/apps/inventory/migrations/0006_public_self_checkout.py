from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_inventoryasset"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryproduct",
            name="public_self_checkout_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="inventoryasset",
            name="public_self_checkout_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
