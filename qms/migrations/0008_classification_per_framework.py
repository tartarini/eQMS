"""Device classification per regulatory framework: the single class (EU MDR classes) becomes
the EU MDR class, and UK MDR 2002 and FDA classes are added."""
from django.db import migrations, models

from qms.models.devices import EU_CLASSES, UK_CLASSES, US_CLASSES


class Migration(migrations.Migration):

    dependencies = [("qms", "0007_mdr_class_i_subclasses")]

    operations = [
        migrations.RenameField("device", "classification", "eu_classification"),
        migrations.AlterField(
            model_name="device", name="eu_classification",
            field=models.CharField("EU MDR class", max_length=5, choices=EU_CLASSES,
                                   blank=True, default="")),
        migrations.AddField(
            model_name="device", name="uk_classification",
            field=models.CharField("UK MDR 2002 class (UKCA)", max_length=5,
                                   choices=UK_CLASSES, blank=True, default="")),
        migrations.AddField(
            model_name="device", name="us_classification",
            field=models.CharField("FDA class", max_length=5, choices=US_CLASSES, blank=True,
                                   default="")),
    ]
