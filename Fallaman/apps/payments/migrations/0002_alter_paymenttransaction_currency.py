"""Passe la devise de XOF à XAF.

Le Gabon est en zone CEMAC : le franc CFA y est le XAF. XOF est la devise
d'Afrique de l'Ouest — mauvaise devise sur toutes les transactions existantes.
"""

from django.db import migrations, models


def xof_to_xaf(apps, schema_editor):
    PaymentTransaction = apps.get_model("payments", "PaymentTransaction")
    PaymentTransaction.objects.filter(currency="XOF").update(currency="XAF")


def xaf_to_xof(apps, schema_editor):
    PaymentTransaction = apps.get_model("payments", "PaymentTransaction")
    PaymentTransaction.objects.filter(currency="XAF").update(currency="XOF")


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_recommendation_system"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymenttransaction",
            name="currency",
            field=models.CharField(default="XAF", max_length=8),
        ),
        migrations.RunPython(xof_to_xaf, xaf_to_xof),
    ]
