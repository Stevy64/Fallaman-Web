"""Reprend le numéro du compte comme WhatsApp sur les profils déjà créés.

Le champ est désormais prérempli à l'inscription, mais les profils existants
sont vides : sans ce rattrapage, leurs propriétaires devraient ressaisir un
numéro que l'application connaît déjà.
"""

from django.db import migrations


def remplir_whatsapp(apps, schema_editor):
    Profile = apps.get_model("profiles", "Profile")
    a_completer = Profile.objects.filter(whatsapp_number="").select_related("user")
    for profile in a_completer.iterator():
        numero = getattr(profile.user, "phone_number", "") or ""
        if numero:
            profile.whatsapp_number = numero
            profile.save(update_fields=["whatsapp_number"])


def vider_whatsapp(apps, schema_editor):
    """
    Retour arrière volontairement inopérant.

    Impossible de distinguer un numéro rempli par ce rattrapage d'un numéro
    saisi par la personne : les effacer tous détruirait de la donnée réelle.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0002_recommendation_system"),
    ]

    operations = [
        migrations.RunPython(remplir_whatsapp, vider_whatsapp),
    ]
