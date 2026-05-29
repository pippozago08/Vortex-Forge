from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.models import Ban
from catalog.models import Build, BuildImage, BuildPurchaseRequest, CustomBuildPayment, CustomBuildRequest
from catalog.notifications import notify_custom_request_approved
from contacts.models import ContactMessage
from core.models import AdminActivityLog, SiteSetting
from core.utils import log_admin_action
from payments.service import get_paypal_runtime_summary

from .forms import (
    BanForm,
    BuildForm,
    BuildGalleryUploadForm,
    CustomBuildReviewForm,
    SiteSettingForm,
    TargetUserBanForm,
    UserRoleForm,
)


User = get_user_model()


def admin_log_filter_categories(action):
    categories = []
    if action in {"create_ban", "revoke_ban"}:
        categories.append("bans")
    if action in {"start_custom_payment", "payment_succeeded", "payment_failed"}:
        categories.append("payments")
    if action in {"update_custom_quote", "reject_custom_request", "cancel_custom_request", "reopen_custom_request", "save_custom_request_notes"}:
        categories.append("requests")
    if action == "approve_custom_request":
        categories.append("request_approvals")
    if action in {"delete_account", "request_account_deletion"}:
        categories.append("account_deletions")
    if action == "create_user":
        categories.append("new_users")
    if action in {"promote_user_to_admin", "demote_admin_to_user", "update_user_role"}:
        categories.append("role_changes")
    return " ".join(categories or ["other"])


def admin_log_actor_rank(actor):
    if not actor:
        return 3
    return {
        User.Role.SUPER_ADMIN: 0,
        User.Role.ADMIN: 1,
        User.Role.USER: 2,
    }.get(actor.role, 3)


def admin_log_display_description(log, target_user=None, target_ban=None):
    user_action_labels = {
        "create_user": _("Nuovo utente creato %(username)s"),
        "promote_user_to_admin": _("Nominato admin %(username)s"),
        "demote_admin_to_user": _("Retrocesso admin %(username)s a utente"),
        "update_user_role": _("Cambiato ruolo utente %(username)s"),
        "update_user": _("Aggiornato utente %(username)s"),
        "delete_account": _("Eliminato account %(username)s"),
    }
    if log.action in user_action_labels:
        username = target_user.display_name if target_user else str(_("utente non piu presente"))
        return user_action_labels[log.action] % {"username": username}

    ban_action_labels = {
        "create_ban": _("Creato ban per %(username)s"),
        "revoke_ban": _("Revocato ban per %(username)s"),
    }
    if log.action in ban_action_labels:
        if target_ban:
            username = target_ban.user.display_name
            return ban_action_labels[log.action] % {"username": username}
        return ban_action_labels[log.action] % {"username": str(_("utente non piu presente"))}

    return log.description


def prepare_admin_activity_logs(logs):
    logs = list(logs)
    user_ids = {
        int(log.object_id)
        for log in logs
        if log.object_type == "User" and str(log.object_id).isdigit()
    }
    ban_ids = {
        int(log.object_id)
        for log in logs
        if log.object_type == "Ban" and str(log.object_id).isdigit()
    }
    users_by_id = User.objects.in_bulk(user_ids)
    bans_by_id = Ban.objects.select_related("user").in_bulk(ban_ids)

    for log in logs:
        target_user = users_by_id.get(int(log.object_id)) if log.object_type == "User" and str(log.object_id).isdigit() else None
        target_ban = bans_by_id.get(int(log.object_id)) if log.object_type == "Ban" and str(log.object_id).isdigit() else None
        log.filter_categories = admin_log_filter_categories(log.action)
        log.actor_rank = admin_log_actor_rank(log.actor)
        log.created_timestamp = int(log.created_at.timestamp())
        log.actor_display = log.actor.display_name if log.actor else str(_("Sistema"))
        log.object_label = target_user.display_name if target_user else target_ban.user.display_name if target_ban else ""
        log.display_description = admin_log_display_description(log, target_user, target_ban)
        yield log


def save_gallery_images(build, image_files):
    existing_total = build.gallery_images.count()
    for offset, image_file in enumerate(image_files, start=1):
        BuildImage.objects.create(
            build=build,
            image=image_file,
            sort_order=existing_total + offset,
        )


def backoffice_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not request.user.has_backoffice_access():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


def backoffice_permission(checker_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if not request.user.has_backoffice_access():
                raise PermissionDenied
            if not getattr(request.user, checker_name)():
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def custom_request_available_actions(custom_request):
    if custom_request.status == CustomBuildRequest.Status.PAID:
        return {"save_notes"}
    if custom_request.status == CustomBuildRequest.Status.PAYMENT_PENDING:
        return {"save_notes", "cancel"}
    if custom_request.status == CustomBuildRequest.Status.IN_APPROVAL:
        return {"approve", "reject", "save_notes"}
    if custom_request.status in {CustomBuildRequest.Status.APPROVED, CustomBuildRequest.Status.PAYMENT_FAILED}:
        return {"approve", "update_quote", "reopen", "cancel", "save_notes"}
    if custom_request.status in {CustomBuildRequest.Status.REJECTED, CustomBuildRequest.Status.CANCELLED}:
        return {"reopen", "save_notes"}
    return {"save_notes"}


@backoffice_required
@never_cache
def dashboard(request):
    custom_requests = CustomBuildRequest.objects.all()
    can_view_contact_sections = request.user.can_access_contacts()
    legacy_purchase_requests = BuildPurchaseRequest.objects.filter(custom_request__isnull=True) if can_view_contact_sections else BuildPurchaseRequest.objects.none()
    recent_contacts = ContactMessage.objects.all()[:5] if can_view_contact_sections else ContactMessage.objects.none()
    context = {
        "build_total": Build.objects.count(),
        "visible_build_total": Build.objects.filter(is_visible=True, is_archived=False).count(),
        "user_total": User.objects.count(),
        "active_ban_total": sum(1 for ban in Ban.objects.all() if ban.is_active),
        "custom_request_total": custom_requests.count(),
        "approval_request_total": custom_requests.filter(status__in=CustomBuildRequest.approval_queue_statuses()).count(),
        "approved_request_total": custom_requests.filter(status__in=CustomBuildRequest.approved_queue_statuses()).count(),
        "paid_custom_request_total": custom_requests.filter(status__in=CustomBuildRequest.paid_queue_statuses()).count(),
        "purchase_request_total": legacy_purchase_requests.count(),
        "contact_total": ContactMessage.objects.count() if can_view_contact_sections else 0,
        "recent_logs": list(prepare_admin_activity_logs(AdminActivityLog.objects.select_related("actor")[:100])),
        "admin_log_total": AdminActivityLog.objects.count(),
        "recent_contacts": recent_contacts,
        "recent_custom_requests": custom_requests.select_related("user")[:5],
        "show_contact_sections": can_view_contact_sections,
    }
    return render(request, "backoffice/dashboard.html", context)


@backoffice_permission("can_access_builds")
@never_cache
def build_list(request):
    builds = Build.objects.all().order_by("sort_order", "-created_at")
    return render(request, "backoffice/build_list.html", {"builds": builds})


@backoffice_permission("can_access_builds")
def build_create(request):
    form = BuildForm(request.POST or None, request.FILES or None)
    gallery_form = BuildGalleryUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid() and gallery_form.is_valid():
        build = form.save(commit=False)
        build.created_by = request.user
        build.updated_by = request.user
        build.save()
        save_gallery_images(build, gallery_form.cleaned_data.get("gallery_images", []))
        log_admin_action(request.user, "create_build", _("Creata build %(name)s") % {"name": build.name}, build)
        messages.success(request, _("Build creata correttamente."))
        return redirect("backoffice:build_edit", pk=build.pk)
    return render(
        request,
        "backoffice/build_form.html",
        {"form": form, "build": None, "gallery_form": BuildGalleryUploadForm()},
    )


@backoffice_permission("can_access_builds")
def build_edit(request, pk):
    build = get_object_or_404(Build, pk=pk)
    form = BuildForm(request.POST or None, request.FILES or None, instance=build)
    gallery_form = BuildGalleryUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and "save_build" in request.POST and form.is_valid() and gallery_form.is_valid():
        build = form.save(commit=False)
        build.updated_by = request.user
        build.save()
        save_gallery_images(build, gallery_form.cleaned_data.get("gallery_images", []))
        log_admin_action(request.user, "update_build", _("Aggiornata build %(name)s") % {"name": build.name}, build)
        messages.success(request, _("Build aggiornata."))
        return redirect("backoffice:build_edit", pk=build.pk)

    return render(
        request,
        "backoffice/build_form.html",
        {
            "form": form,
            "build": build,
            "gallery_form": gallery_form,
            "gallery_images": build.gallery_images.all(),
        },
    )


@backoffice_permission("can_access_builds")
@require_POST
def build_toggle_visibility(request, pk):
    build = get_object_or_404(Build, pk=pk)
    build.is_visible = not build.is_visible
    build.updated_by = request.user
    build.save(update_fields=["is_visible", "updated_by", "updated_at"])
    log_admin_action(
        request.user,
        "toggle_build_visibility",
        _("Visibilita build %(name)s: %(value)s") % {"name": build.name, "value": build.is_visible},
        build,
    )
    messages.success(request, _("Visibilita della build aggiornata."))
    return redirect("backoffice:build_list")


@backoffice_permission("can_access_builds")
@require_POST
def build_toggle_archive(request, pk):
    build = get_object_or_404(Build, pk=pk)
    build.is_archived = not build.is_archived
    build.updated_by = request.user
    build.save(update_fields=["is_archived", "updated_by", "updated_at"])
    log_admin_action(
        request.user,
        "toggle_build_archive",
        _("Archiviazione build %(name)s: %(value)s") % {"name": build.name, "value": build.is_archived},
        build,
    )
    messages.success(request, _("Stato archivio della build aggiornato."))
    return redirect("backoffice:build_list")


@backoffice_permission("can_access_builds")
@require_POST
def build_delete_image(request, image_id):
    image = get_object_or_404(BuildImage, pk=image_id)
    build_id = image.build_id
    log_admin_action(
        request.user,
        "delete_build_image",
        _("Eliminata immagine build %(name)s") % {"name": image.build.name},
        image.build,
    )
    image.delete()
    messages.success(request, _("Immagine rimossa."))
    return redirect("backoffice:build_edit", pk=build_id)


@backoffice_permission("can_access_builds")
@require_POST
def build_delete(request, pk):
    build = get_object_or_404(Build, pk=pk)
    build_name = build.name
    log_admin_action(
        request.user,
        "delete_build",
        _("Eliminata build %(name)s") % {"name": build_name},
        build,
    )
    build.delete()
    messages.success(request, _("Build eliminata definitivamente."))
    return redirect("backoffice:build_list")


@backoffice_required
@never_cache
def user_list(request):
    if not (request.user.can_access_users() or request.user.can_access_bans()):
        raise PermissionDenied

    search_query = (request.GET.get("q") or "").strip()
    users = User.objects.prefetch_related("bans").all()
    if request.user.role != User.Role.SUPER_ADMIN:
        users = users.filter(role=User.Role.USER)
    if search_query:
        users = users.filter(username__icontains=search_query)
    users = users.order_by("-date_joined")
    return render(request, "backoffice/user_list.html", {"users": users, "search_query": search_query})


@backoffice_required
def user_edit(request, pk):
    target_user = get_object_or_404(User.objects.prefetch_related("bans"), pk=pk)
    active_ban = target_user.get_active_ban()
    can_manage_user = request.user.can_manage_user_target(target_user)
    can_ban_user = request.user.can_ban_target(target_user)
    can_revoke_ban = bool(active_ban and request.user.can_revoke_ban_target(active_ban))

    if not (can_manage_user or can_ban_user or can_revoke_ban):
        raise PermissionDenied

    previous_role = target_user.role
    user_form_data = request.POST if request.method == "POST" and request.POST.get("action") == "save_user" else None
    ban_form_data = request.POST if request.method == "POST" and request.POST.get("action") == "create_ban" else None
    form = UserRoleForm(user_form_data, instance=target_user, actor=request.user)
    ban_form = TargetUserBanForm(
        ban_form_data,
        target_user=target_user,
        actor=request.user,
    )

    if request.user.role != User.Role.SUPER_ADMIN:
        form.fields["role"].disabled = True

    if request.method == "POST" and request.POST.get("action") == "save_user" and not can_manage_user:
        raise PermissionDenied

    if request.method == "POST" and request.POST.get("action") == "save_user" and form.is_valid():
        updated_user = form.save()
        if previous_role != updated_user.role:
            if previous_role == User.Role.USER and updated_user.role == User.Role.ADMIN:
                action = "promote_user_to_admin"
                description = _("Nominato admin %(username)s dal super admin") % {"username": updated_user.display_name}
            elif previous_role == User.Role.ADMIN and updated_user.role == User.Role.USER:
                action = "demote_admin_to_user"
                description = _("Retrocesso admin %(username)s a utente") % {"username": updated_user.display_name}
            else:
                action = "update_user_role"
                description = _("Cambiato ruolo utente %(username)s") % {"username": updated_user.display_name}
        else:
            action = "update_user"
            description = _("Aggiornato utente %(username)s") % {"username": updated_user.display_name}
        log_admin_action(request.user, action, description, updated_user)
        messages.success(request, _("Utente aggiornato."))
        return redirect("backoffice:user_edit", pk=updated_user.pk)

    if request.method == "POST" and request.POST.get("action") == "create_ban":
        if active_ban:
            messages.error(request, _("Questo utente ha gia un ban attivo. Revocalo prima di crearne un altro."))
        elif not can_ban_user:
            raise PermissionDenied
        elif ban_form.is_valid():
            ban = ban_form.save(commit=False)
            ban.user = target_user
            ban.issued_by = request.user
            ban.full_clean()
            ban.save()
            log_admin_action(request.user, "create_ban", _("Creato ban per %(username)s") % {"username": target_user.display_name}, ban)
            messages.success(request, _("Ban creato correttamente."))
            return redirect("backoffice:user_edit", pk=target_user.pk)

    return render(
        request,
        "backoffice/user_form.html",
        {
            "form": form,
            "ban_form": ban_form,
            "target_user": target_user,
            "active_ban": active_ban,
            "ban_history": target_user.bans.select_related("issued_by", "revoked_by").all(),
            "can_manage_user": can_manage_user,
            "can_ban_user": can_ban_user,
            "can_revoke_ban": can_revoke_ban,
        },
    )


@backoffice_permission("can_access_bans")
@never_cache
def ban_list(request):
    bans = Ban.objects.select_related("user", "issued_by", "revoked_by").all()
    if request.user.role != User.Role.SUPER_ADMIN:
        bans = bans.filter(user__role=User.Role.USER)
    return render(request, "backoffice/ban_list.html", {"bans": bans})


@backoffice_permission("can_access_bans")
def ban_create(request):
    form = BanForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        ban = form.save(commit=False)
        ban.issued_by = request.user
        ban.full_clean()
        ban.save()
        log_admin_action(request.user, "create_ban", _("Creato ban per %(username)s") % {"username": ban.user.display_name}, ban)
        messages.success(request, _("Ban creato correttamente."))
        return redirect("backoffice:user_edit", pk=ban.user_id)
    return render(request, "backoffice/ban_form.html", {"form": form})


@backoffice_permission("can_access_bans")
@require_POST
def ban_revoke(request, pk):
    ban = get_object_or_404(Ban, pk=pk)
    if not request.user.can_revoke_ban_target(ban):
        raise PermissionDenied
    user_id = ban.user_id
    ban.revoke(request.user, request.POST.get("reason", ""))
    log_admin_action(request.user, "revoke_ban", _("Revocato ban per %(username)s") % {"username": ban.user.display_name}, ban)
    messages.success(request, _("Ban revocato manualmente."))
    return redirect("backoffice:user_edit", pk=user_id)


@backoffice_permission("can_access_requests")
@never_cache
def requests_overview(request):
    custom_requests = CustomBuildRequest.objects.select_related("user", "reviewed_by").order_by("-created_at")
    payments = CustomBuildPayment.objects.select_related("custom_request", "user").order_by("-initiated_at")
    can_view_contact_sections = request.user.can_access_contacts()
    legacy_purchase_requests = (
        BuildPurchaseRequest.objects.filter(custom_request__isnull=True).order_by("-created_at")
        if can_view_contact_sections
        else BuildPurchaseRequest.objects.none()
    )
    contact_messages = ContactMessage.objects.all()[:20] if can_view_contact_sections else ContactMessage.objects.none()
    context = {
        "approval_requests": custom_requests.filter(status__in=CustomBuildRequest.approval_queue_statuses()),
        "approved_requests": custom_requests.filter(status__in=CustomBuildRequest.approved_queue_statuses()),
        "paid_requests": custom_requests.filter(status__in=CustomBuildRequest.paid_queue_statuses()),
        "closed_requests": custom_requests.filter(status__in=CustomBuildRequest.closed_queue_statuses()),
        "approval_count": custom_requests.filter(status__in=CustomBuildRequest.approval_queue_statuses()).count(),
        "approved_count": custom_requests.filter(status__in=CustomBuildRequest.approved_queue_statuses()).count(),
        "paid_count": custom_requests.filter(status__in=CustomBuildRequest.paid_queue_statuses()).count(),
        "closed_count": custom_requests.filter(status__in=CustomBuildRequest.closed_queue_statuses()).count(),
        "payment_pending_count": payments.filter(status__in=[CustomBuildPayment.Status.CREATED, CustomBuildPayment.Status.PENDING]).count(),
        "payment_success_count": payments.filter(status=CustomBuildPayment.Status.SUCCEEDED).count(),
        "payment_failed_count": payments.filter(status=CustomBuildPayment.Status.FAILED).count(),
        "recent_payments": payments[:12],
        "purchase_requests": legacy_purchase_requests[:20],
        "contact_messages": contact_messages,
        "payment_runtime": get_paypal_runtime_summary(),
        "show_contact_sections": can_view_contact_sections,
    }
    return render(request, "backoffice/requests.html", context)


@backoffice_permission("can_access_requests")
@never_cache
def custom_request_review(request, pk):
    custom_request = get_object_or_404(
        CustomBuildRequest.objects.select_related("user", "reviewed_by"),
        pk=pk,
    )
    form = CustomBuildReviewForm(request.POST or None, instance=custom_request)
    available_actions = custom_request_available_actions(custom_request)

    if request.method == "POST":
        action = request.POST.get("action")
        if action not in available_actions:
            raise PermissionDenied

        if form.is_valid():
            reviewed_request = form.save(commit=False)
            reviewed_request.reviewed_by = request.user
            reviewed_request.reviewed_at = timezone.now()
            reviewed_request.currency = reviewed_request.currency or settings.PAYMENT_DEFAULT_CURRENCY

            update_fields = ["approved_price", "admin_notes", "reviewed_by", "reviewed_at", "currency", "updated_at"]

            if action in {"approve", "update_quote"} and reviewed_request.approved_price is None:
                form.add_error("approved_price", _("Inserisci il prezzo finale prima di approvare o aggiornare il preventivo."))
            else:
                if action == "approve":
                    reviewed_request.status = CustomBuildRequest.Status.APPROVED
                    reviewed_request.approved_at = timezone.now()
                    update_fields.extend(["status", "approved_at"])
                    reviewed_request.save(update_fields=update_fields)
                    notify_custom_request_approved(reviewed_request, request=request)
                    log_admin_action(
                        request.user,
                        "approve_custom_request",
                        _("Approvata richiesta %(reference)s") % {"reference": reviewed_request.reference_code},
                        reviewed_request,
                    )
                    messages.success(request, _("Richiesta approvata. Il cliente ora vede il prezzo finale e puo pagare."))
                    return redirect("backoffice:custom_request_review", pk=reviewed_request.pk)

                if action == "update_quote":
                    reviewed_request.save(update_fields=update_fields)
                    log_admin_action(
                        request.user,
                        "update_custom_quote",
                        _("Aggiornato preventivo richiesta %(reference)s") % {"reference": reviewed_request.reference_code},
                        reviewed_request,
                    )
                    messages.success(request, _("Preventivo aggiornato. Il nuovo prezzo finale e stato salvato."))
                    return redirect("backoffice:custom_request_review", pk=reviewed_request.pk)

                if action == "reject":
                    reviewed_request.status = CustomBuildRequest.Status.REJECTED
                    update_fields.append("status")
                    reviewed_request.save(update_fields=update_fields)
                    log_admin_action(
                        request.user,
                        "reject_custom_request",
                        _("Rifiutata richiesta %(reference)s") % {"reference": reviewed_request.reference_code},
                        reviewed_request,
                    )
                    messages.success(request, _("Richiesta rifiutata. Il cliente non vedra nessun pagamento attivo."))
                    return redirect("backoffice:custom_request_review", pk=reviewed_request.pk)

                if action == "cancel":
                    reviewed_request.status = CustomBuildRequest.Status.CANCELLED
                    update_fields.append("status")
                    reviewed_request.save(update_fields=update_fields)
                    log_admin_action(
                        request.user,
                        "cancel_custom_request",
                        _("Annullata richiesta %(reference)s") % {"reference": reviewed_request.reference_code},
                        reviewed_request,
                    )
                    messages.success(request, _("Richiesta annullata."))
                    return redirect("backoffice:custom_request_review", pk=reviewed_request.pk)

                if action == "reopen":
                    reviewed_request.status = CustomBuildRequest.Status.IN_APPROVAL
                    update_fields.append("status")
                    reviewed_request.save(update_fields=update_fields)
                    log_admin_action(
                        request.user,
                        "reopen_custom_request",
                        _("Riaperta richiesta %(reference)s") % {"reference": reviewed_request.reference_code},
                        reviewed_request,
                    )
                    messages.success(request, _("Richiesta riportata in approvazione."))
                    return redirect("backoffice:custom_request_review", pk=reviewed_request.pk)

                if action == "save_notes":
                    reviewed_request.save(update_fields=update_fields)
                    log_admin_action(
                        request.user,
                        "save_custom_request_notes",
                        _("Aggiornate note richiesta %(reference)s") % {"reference": reviewed_request.reference_code},
                        reviewed_request,
                    )
                    messages.success(request, _("Messaggio e note del preventivo aggiornati."))
                    return redirect("backoffice:custom_request_review", pk=reviewed_request.pk)

    context = {
        "custom_request": custom_request,
        "form": form,
        "available_actions": available_actions,
        "payment_history": custom_request.payments_queryset(),
        "latest_payment": custom_request.latest_payment,
        "active_payment": custom_request.active_payment,
        "payment_runtime": get_paypal_runtime_summary(),
    }
    return render(request, "backoffice/custom_request_review.html", context)


@backoffice_permission("can_access_settings")
@never_cache
def settings_view(request):
    settings_obj = SiteSetting.load()
    form = SiteSettingForm(request.POST or None, instance=settings_obj)
    if request.method == "POST" and form.is_valid():
        settings_obj = form.save()
        log_admin_action(request.user, "update_site_settings", _("Aggiornate le impostazioni del sito"), settings_obj)
        messages.success(request, _("Impostazioni salvate."))
        return redirect("backoffice:settings")
    return render(request, "backoffice/settings.html", {"form": form})
