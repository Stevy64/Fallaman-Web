# Generated manually for single-recipient staff broadcasts

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dashboard", "0001_admin_messaging_intros"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffbroadcast",
            name="recipient",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="received_staff_broadcasts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="staffbroadcast",
            name="audience",
            field=models.CharField(
                choices=[
                    ("all", "Tous les membres"),
                    ("active", "Comptes actifs uniquement"),
                    ("one", "Une seule personne"),
                ],
                default="active",
                max_length=20,
            ),
        ),
    ]
