# Generated by Django 5.0 on 2024-01-14 22:24

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("epreuve", "0013_remove_userepreuve_debut_epreuve_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="JeuDeTest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("instance", models.TextField()),
                ("reponse", models.TextField()),
                (
                    "exercice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jeu_de_test",
                        to="epreuve.exercice",
                    ),
                ),
            ],
            options={
                "db_table": "JeuDeTest",
                "indexes": [
                    models.Index(
                        fields=["exercice"], name="JeuDeTest_exercic_715cb2_idx"
                    )
                ],
            },
        ),
    ]
