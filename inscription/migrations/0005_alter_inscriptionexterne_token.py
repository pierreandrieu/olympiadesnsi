# Generated by Django 5.0.2 on 2024-02-19 14:27

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inscription", "0004_delete_inscripteur"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inscriptionexterne",
            name="token",
            field=models.CharField(blank=True, max_length=50, unique=True),
        ),
    ]