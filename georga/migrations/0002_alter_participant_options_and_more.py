# Generated by Django 4.1.2 on 2022-11-25 15:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('georga', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='participant',
            options={'verbose_name': 'participant', 'verbose_name_plural': 'participants'},
        ),
        migrations.AlterModelOptions(
            name='rolespecification',
            options={'verbose_name': 'role specificatioin', 'verbose_name_plural': 'role specifications'},
        ),
        migrations.RenameField(
            model_name='resource',
            old_name='title',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='role',
            old_name='title',
            new_name='name',
        ),
    ]