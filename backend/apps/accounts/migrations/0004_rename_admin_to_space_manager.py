from django.db import migrations, models


def rename_admin_to_space_manager(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="admin").update(role="space_manager")


def rename_space_manager_to_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="space_manager").update(role="admin")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_user_telegram_user_id_user_uniq_telegram_user_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("superadmin", "Super Admin"),
                    ("space_manager", "Space Manager"),
                    ("guest_admin", "Guest Admin"),
                    ("requester", "Requester"),
                ],
                default="requester",
                max_length=32,
            ),
        ),
        migrations.RunPython(
            rename_admin_to_space_manager,
            rename_space_manager_to_admin,
        ),
    ]
