# Generated by Django 4.2.6 on 2023-12-04 22:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('georga', '0007_alter_operation_description_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='operation',
            name='description',
            field=models.CharField(blank=True, default='', max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='description',
            field=models.CharField(blank=True, default='', max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='project',
            name='description',
            field=models.CharField(blank=True, default='', max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='resource',
            name='description',
            field=models.CharField(blank=True, default='', max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='role',
            name='description',
            field=models.CharField(blank=True, default='', max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='description',
            field=models.CharField(blank=True, default='', max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='taskfield',
            name='description',
            field=models.CharField(blank=True, default='', max_length=500, null=True),
        ),
    ]
