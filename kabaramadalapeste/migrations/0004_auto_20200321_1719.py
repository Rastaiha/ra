# Generated by Django 3.0.4 on 2020-03-21 17:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kabaramadalapeste', '0003_way'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='way',
            unique_together={('first_end', 'second_end')},
        ),
    ]
