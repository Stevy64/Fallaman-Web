# Generated manually for notification body (staff broadcasts)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_staff_broadcast_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="body",
            field=models.TextField(blank=True, default=""),
        ),
    ]
