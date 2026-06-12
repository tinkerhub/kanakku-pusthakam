from django.db import migrations, models


def rename_admin_to_space_manager(apps, schema_editor):
    MakerspaceMembership = apps.get_model("makerspaces", "MakerspaceMembership")
    MakerspaceMembership.objects.filter(role="admin").update(role="space_manager")


def downgrade_space_manager_and_inventory_manager(apps, schema_editor):
    MakerspaceMembership = apps.get_model("makerspaces", "MakerspaceMembership")
    MakerspaceMembership.objects.filter(role="space_manager").update(role="admin")
    MakerspaceMembership.objects.filter(role="inventory_manager").update(
        role="guest_admin"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0007_makerspace_public_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="makerspacemembership",
            name="role",
            field=models.CharField(
                choices=[
                    ("space_manager", "Space Manager"),
                    ("guest_admin", "Guest Admin"),
                    ("inventory_manager", "Inventory Manager"),
                    ("print_manager", "Print Manager"),
                ],
                default="space_manager",
                max_length=32,
            ),
        ),
        migrations.RunPython(
            rename_admin_to_space_manager,
            downgrade_space_manager_and_inventory_manager,
        ),
    ]
