from django.core.management.base import BaseCommand
from django.utils import timezone

from cviky.reminders import send_due


class Command(BaseCommand):
    help = "Odešle denní připomínky sérií, které jsou právě na řadě."

    def handle(self, *args, **options):
        count = send_due(timezone.now())
        self.stdout.write(f"Odesláno: {count}")
