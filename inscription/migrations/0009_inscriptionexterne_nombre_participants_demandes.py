# Generated by Django 5.0.2 on 2024-02-28 14:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inscription", "0008_remove_inscriptionexterne_inscription_validee"),
    ]

    operations = [
        migrations.AddField(
            model_name="inscriptionexterne",
            name="nombre_participants_demandes",
            field=models.IntegerField(default=0),
        ),
    ]
