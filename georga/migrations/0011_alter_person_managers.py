# Generated by Django 4.2.11 on 2024-04-07 21:11

from django.db import migrations
import georga.models


class Migration(migrations.Migration):

    dependencies = [
        ('georga', '0010_alter_person_managers'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='person',
            managers=[
                ('objects', georga.models.PersonManager()),
            ],
        ),
    ]
