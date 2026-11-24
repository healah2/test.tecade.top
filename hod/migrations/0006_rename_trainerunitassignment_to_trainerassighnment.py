from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hod', '0005_alter_trainerunitassignment_class_slot'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='TrainerUnitAssignment',
            new_name='TrainerAssighnment',
        ),
    ]
