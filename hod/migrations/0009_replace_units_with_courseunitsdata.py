from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hod", "0008_curriculumlearningoutcome"),
    ]

    operations = [
        # Safe rename: this is a simple table rename in SQLite.
        migrations.RenameModel(
            old_name="CurricumData",
            new_name="CourseUnitsData",
        ),
        migrations.AlterField(
            model_name="curriculumlearningoutcome",
            name="curriculum_data",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="learning_outcomes",
                to="hod.courseunitsdata",
            ),
        ),
        # IMPORTANT: don't mutate the existing M2M join table in-place, because it already
        # contains FK values pointing at `hod_units`. Altering it to point at
        # `hod_courseunitsdata` causes immediate FK integrity failures.
        #
        # We add a new M2M with a new join table, then copy data in a follow-up migration.
        migrations.AddField(
            model_name="trainerassighnment",
            name="course_units",
            field=models.ManyToManyField(
                blank=True,
                related_name="trainer_assignments",
                to="hod.courseunitsdata",
            ),
        ),
    ]
