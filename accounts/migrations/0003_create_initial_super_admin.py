from django.db import migrations
from django.contrib.auth.hashers import make_password


def create_initial_super_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")

    email = "pippozago08@gmail.com"
    username = "pippozago08"

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "password": make_password("VortexForgeAdmin!2026#R7q"),
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "role": "super_admin",
            "is_email_verified": True,
            "can_manage_builds": True,
            "can_manage_users": True,
            "can_manage_bans": True,
            "can_view_contacts": True,
            "can_manage_settings": True,
        },
    )

    if not created:
        user.username = username
        user.password = make_password("VortexForgeAdmin!2026#R7q")
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = "super_admin"
        user.is_email_verified = True
        user.can_manage_builds = True
        user.can_manage_users = True
        user.can_manage_bans = True
        user.can_view_contacts = True
        user.can_manage_settings = True
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_accountdeletionrequest"),
    ]

    operations = [
        migrations.RunPython(create_initial_super_admin, migrations.RunPython.noop),
    ]
