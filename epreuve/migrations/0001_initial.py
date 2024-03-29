# Generated by Django 5.0.1 on 2024-02-18 01:16

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Epreuve",
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
                ("nom", models.CharField(max_length=100)),
                ("date_debut", models.DateTimeField()),
                ("date_fin", models.DateTimeField()),
                ("duree", models.IntegerField(null=True)),
                ("exercices_un_par_un", models.BooleanField(default=False)),
                ("temps_limite", models.BooleanField(default=False)),
                ("inscription_externe", models.BooleanField(default=False)),
            ],
            options={
                "db_table": "Epreuve",
            },
        ),
        migrations.CreateModel(
            name="Exercice",
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
                ("titre", models.CharField(max_length=100)),
                ("bareme", models.IntegerField(null=True)),
                (
                    "type_exercice",
                    models.CharField(
                        choices=[
                            ("programmation", "Programmation"),
                            ("qcm", "QCM"),
                            ("qroc", "QROC"),
                            ("qcs", "QCS"),
                        ],
                        default="programmation",
                        max_length=14,
                    ),
                ),
                ("enonce", models.TextField(blank=True, null=True)),
                ("enonce_code", models.TextField(blank=True, null=True)),
                ("avec_jeu_de_test", models.BooleanField(default=False)),
                ("retour_en_direct", models.BooleanField(default=False)),
                ("code_a_soumettre", models.BooleanField(default=False)),
                ("nombre_max_soumissions", models.IntegerField(default=50)),
                ("numero", models.IntegerField(blank=True, null=True)),
            ],
            options={
                "db_table": "Exercice",
            },
        ),
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
            ],
            options={
                "db_table": "JeuDeTest",
            },
        ),
        migrations.CreateModel(
            name="MembreComite",
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
            ],
            options={
                "db_table": "MembreComite",
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
                ("fin_epreuve", models.DateTimeField(null=True)),
            ],
            options={
                "db_table": "UserEpreuve",
            },
        ),
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
                ("solution_instance_participant", models.TextField(null=True)),
                ("code_participant", models.TextField(null=True)),
                ("nb_soumissions", models.IntegerField(default=0)),
            ],
            options={
                "db_table": "User_Exercice",
            },
        ),
    ]
