# Generated by Django 4.1 on 2022-08-12 20:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('georga', '0018_personproperty_personpropertygroup_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='equipment',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='location',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='locationcategory',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='notification',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='notificationcategory',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='operation',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='personproperty',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='personpropertygroup',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='resource',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='role',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='task',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='taskcategory',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AddField(
            model_name='timeslot',
            name='organization',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
        migrations.AlterField(
            model_name='project',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='georga.organization'),
        ),
    ]
