# Generated by Django 3.0.4 on 2020-03-29 04:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('kabaramadalapeste', '0029_gameeventlog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gameeventlog',
            name='where',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='logs', to='kabaramadalapeste.Island'),
        ),
    ]
