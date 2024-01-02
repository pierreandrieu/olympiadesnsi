# Generated by Django 5.0 on 2024-01-02 12:15

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("epreuve", "0002_rename_creepar_usercreepar_groupecreepar"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="epreuve",
            constraint=models.CheckConstraint(
                check=models.Q(("date_fin__gte", models.F("date_debut"))),
                name="date_fin_apres_date_debut",
            ),
        ),
    ]