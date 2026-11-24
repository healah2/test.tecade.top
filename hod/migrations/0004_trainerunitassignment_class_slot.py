# Generated migration for class_slot field

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hod', '0003_classes'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainerunitassignment',
            name='class_slot',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='trainer_assignments', to='hod.classes'),
        ),
    ]
