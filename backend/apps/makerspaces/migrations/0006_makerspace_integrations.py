from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("makerspaces", "0005_alter_makerspace_public_api_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="makerspace",
            name="telegram_bot_token",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="makerspace",
            name="smtp_host",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="makerspace",
            name="smtp_port",
            field=models.PositiveIntegerField(default=587),
        ),
        migrations.AddField(
            model_name="makerspace",
            name="smtp_username",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="makerspace",
            name="smtp_password",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="makerspace",
            name="smtp_use_tls",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="makerspace",
            name="smtp_from_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
