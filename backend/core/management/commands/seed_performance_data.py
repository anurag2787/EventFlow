import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import Organization, Repository, Activity

User = get_user_model()


class Command(BaseCommand):
    help = "Seed 100k+ realistic Activity records for PostgreSQL performance testing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=100000,
            help='Number of activity records to generate (default: 100000)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10000,
            help='Batch size for bulk insertion (default: 10000)',
        )

    def handle(self, *args, **options):
        total_count = options['count']
        batch_size = options['batch_size']

        self.stdout.write(self.style.NOTICE(f"Starting seed process for {total_count} activities..."))

        # 1. Setup prerequisite models
        org, _ = Organization.objects.get_or_create(name="Acme Performance Corp")

        repo_names = ["web-frontend", "api-gateway", "data-pipeline", "auth-service", "payment-engine"]
        repos = []
        for r_name in repo_names:
            repo, _ = Repository.objects.get_or_create(
                organization=org,
                name=r_name,
                defaults={"provider": "github", "external_id": f"acme-corp/{r_name}"}
            )
            repos.append(repo)

        user_names = ["alice_dev", "bob_lead", "charlie_ops", "diana_qa", "eve_sec"]
        users = []
        for u_name in user_names:
            user, _ = User.objects.get_or_create(
                username=u_name,
                defaults={"email": f"{u_name}@acme.com"}
            )
            users.append(user)

        activity_types = [
            "PR_OPENED", "PR_MERGED", "ISSUE_CREATED",
            "COMMIT_PUSHED", "STAR_ADDED", "WORKFLOW_FAILED"
        ]

        now = timezone.now()
        activities = []
        created_so_far = 0

        self.stdout.write("Generating data batches in memory...")

        for i in range(1, total_count + 1):
            # Generate random timestamp within last 180 days
            random_days = random.uniform(0, 180)
            random_time = now - timedelta(days=random_days)

            repo = random.choice(repos)
            actor = random.choice(users)
            act_type = random.choice(activity_types)

            activity = Activity(
                repository=repo,
                actor=actor,
                activity_type=act_type,
                target_id=str(random.randint(100, 9999)),
                source_provider="github",
                source_event_id=f"evt_{uuid.uuid4().hex[:12]}",
                source_event_type="push" if act_type == "COMMIT_PUSHED" else "pull_request",
                source_url=f"https://github.com/acme-corp/{repo.name}/pull/{random.randint(1, 500)}",
                metadata={"seeded": True, "performance_test": True},
                created_at=random_time
            )
            activities.append(activity)

            if len(activities) >= batch_size or i == total_count:
                Activity.objects.bulk_create(activities)
                created_so_far += len(activities)
                self.stdout.write(f"Inserted {created_so_far}/{total_count} records...")
                activities = []

        total_activities = Activity.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully seeded database! Total Activity count: {total_activities}")
        )
