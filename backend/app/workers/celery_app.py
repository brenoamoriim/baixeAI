from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery("baixeai", broker=settings.redis_url, backend=None, include=["app.workers.tasks"])
celery.conf.update(
    task_acks_late=True,  # a job interrupted by a dead worker is redelivered (run() is idempotent)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_soft_time_limit=300,
    task_time_limit=330,
    task_always_eager=settings.celery_task_always_eager,
    timezone="UTC",
    beat_schedule={
        "expire-credit-buckets": {"task": "maintenance.expire_buckets", "schedule": 300.0},
        "sweep-stuck-jobs": {"task": "maintenance.sweep_stuck_jobs", "schedule": 300.0},
        "cleanup-expired-outputs": {"task": "maintenance.cleanup_outputs", "schedule": 600.0},
        "cleanup-expired-uploads": {"task": "maintenance.cleanup_uploads", "schedule": 600.0},
        "ledger-reconciliation": {"task": "maintenance.ledger_reconciliation", "schedule": 86400.0},
        "payments-reconcile": {"task": "maintenance.payments_reconcile", "schedule": 600.0},
        "subscriptions": {"task": "maintenance.subscriptions", "schedule": 3600.0},
    },
)
app = celery
