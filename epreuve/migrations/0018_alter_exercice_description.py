# Generated by Django 5.0 on 2024-01-16 12:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("epreuve", "0017_remove_exercice_type_exercice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exercice",
            name="description",
            field=models.TextField(null=True),
        ),
    ]
