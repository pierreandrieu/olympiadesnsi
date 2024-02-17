# Generated by Django 5.0.1 on 2024-02-17 08:44

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("inscription", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupeCreePar",
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
                ("nombre_participants", models.IntegerField(default=0)),
                ("date_creation", models.DateField()),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("VALIDE", "Valide"),
                            ("CREATION", "En cours de création"),
                            ("ECHEC", "Échec"),
                        ],
                        default="CREATION",
                        max_length=10,
                    ),
                ),
                (
                    "createur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="groupes_crees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "groupe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="associations_groupe_createur",
                        to="auth.group",
                    ),
                ),
                (
                    "inscripteur",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inscripteur_groupe",
                        to="inscription.inscripteur",
                    ),
                ),
            ],
            options={
                "db_table": "GroupeCreePar",
                "indexes": [
                    models.Index(
                        fields=["createur"], name="GroupeCreeP_createu_819c01_idx"
                    )
                ],
                "unique_together": {("groupe", "createur")},
            },
        ),
    ]
