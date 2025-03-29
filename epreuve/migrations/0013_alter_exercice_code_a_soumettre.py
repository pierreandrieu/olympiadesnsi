from django.db import migrations


def corriger_valeurs_booleennes_code_a_soumettre(apps, schema_editor):
    Exercice = apps.get_model("epreuve", "Exercice")
    Exercice.objects.filter(code_a_soumettre='true').update(code_a_soumettre='python')
    Exercice.objects.filter(code_a_soumettre='false').update(code_a_soumettre='aucun')


class Migration(migrations.Migration):
    dependencies = [
        ("epreuve", "0012_alter_exercice_code_a_soumettre"),
    ]

    operations = [
        migrations.RunPython(corriger_valeurs_booleennes_code_a_soumettre),
    ]
