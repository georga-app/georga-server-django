# Generated by Django 4.1 on 2022-09-13 15:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('georga', '0009_remove_shift_locations_remove_task_locations_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='ace',
            unique_together={('access_object_ct', 'access_object_id', 'person', 'ace_string')},
        ),
    ]
