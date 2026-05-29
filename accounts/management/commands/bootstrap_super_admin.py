from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea o aggiorna il super admin iniziale."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--first-name", default="Super")
        parser.add_argument("--last-name", default="Admin")

    def handle(self, *args, **options):
        User = get_user_model()
        if len(options["password"]) < 10:
            raise CommandError("La password deve contenere almeno 10 caratteri.")

        user, created = User.objects.get_or_create(
            email=options["email"].lower(),
            defaults={
                "username": options["username"],
                "first_name": options["first_name"],
                "last_name": options["last_name"],
            },
        )

        user.username = options["username"]
        user.first_name = options["first_name"]
        user.last_name = options["last_name"]
        user.role = User.Role.SUPER_ADMIN
        user.is_active = True
        user.set_password(options["password"])
        user.save()

        message = "Creato" if created else "Aggiornato"
        self.stdout.write(self.style.SUCCESS(f"{message} super admin: {user.email}"))
