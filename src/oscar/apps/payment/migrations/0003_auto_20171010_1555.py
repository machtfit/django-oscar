# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0002_auto_20141007_2032'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bankcard',
            name='user',
        ),
        migrations.DeleteModel(
            name='Bankcard',
        ),
    ]
