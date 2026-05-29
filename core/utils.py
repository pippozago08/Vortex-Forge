from core.models import AdminActivityLog


def log_admin_action(actor, action, description, obj=None):
    AdminActivityLog.objects.create(
        actor=actor,
        action=action,
        description=description,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
    )
