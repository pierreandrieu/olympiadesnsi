# Generated by Django 5.0 on 2024-01-11 08:48

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("epreuve", "0011_exercice"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserExercice",
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
                ("instance_participant", models.TextField(null=True)),
                ("solution_instance_participant", models.TextField(null=True)),
                ("solution_instance_correction", models.TextField(null=True)),
                ("code_participant", models.TextField(null=True)),
                (
                    "nombre_soumissions_solution_instance",
                    models.IntegerField(default=0),
                ),
                ("nombre_soumissions_code", models.IntegerField(default=0)),
                (
                    "exercice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="association_UserExercice_Exercice",
                        to="epreuve.exercice",
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="association_UserExercice_User",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "ParticipantExercice",
            },
        ),
        migrations.CreateModel(
            name="UserEpreuve",
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
                ("debut_epreuve", models.DateTimeField(auto_now=True)),
                (
                    "epreuve",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="association_UserEpreuve_Epreuve",
                        to="epreuve.epreuve",
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="association_UserEpreuve_User",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "UserEpreuve",
                "indexes": [
                    models.Index(
                        fields=["participant", "epreuve"],
                        name="UserEpreuve_partici_e8c70c_idx",
                    ),
                    models.Index(
                        fields=["epreuve", "participant"],
                        name="UserEpreuve_epreuve_68a92c_idx",
                    ),
                ],
            },
        ),
    ]
