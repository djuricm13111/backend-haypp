from django.core.management.base import BaseCommand

from account.tasks import process_due_subscriptions


class Command(BaseCommand):
    help = "Procesira pretplate sa isteklim next_order_at (isto kao Celery task)."

    def handle(self, *args, **options):
        process_due_subscriptions()
        self.stdout.write(self.style.SUCCESS("process_due_subscriptions završen."))
