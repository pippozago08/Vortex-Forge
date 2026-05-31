from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_accountdeletionrequest"),
    ]

    # The Render startup recipe seeds the account without committing credentials.
    operations = []
