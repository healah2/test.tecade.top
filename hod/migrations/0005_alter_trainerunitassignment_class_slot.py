# Migration to change class_slot on_delete from SET_NULL to CASCADE

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hod', '0004_trainerunitassignment_class_slot'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trainerunitassignment',
            name='class_slot',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trainer_assignments', to='hod.classes'),
        ),
    ]
