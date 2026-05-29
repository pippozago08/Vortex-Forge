from decimal import Decimal, InvalidOperation, ROUND_CEILING

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, FormView, ListView, TemplateView

from payments.service import (
    PaymentConfigurationError,
    PaymentGatewayError,
    PaymentStateError,
    finalize_simulated_payment,
    get_paypal_runtime_summary,
    start_custom_request_checkout,
)
from core.utils import log_admin_action

from .forms import BuildPurchaseRequestForm, CheckoutStartForm, CustomBuildRequestForm, SimulatedCheckoutConfirmForm
from .models import Build, CustomBuildPayment, CustomBuildRequest
from .notifications import (
    notify_admin_payment_received,
    notify_custom_request_paid,
    notify_custom_request_submitted,
)


class BuildListView(ListView):
    template_name = "catalog/build_list.html"
    model = Build
    context_object_name = "builds"
    paginate_by = 12
    ram_slider_min = Build.RAM_GB_MIN
    ram_slider_max = Build.RAM_GB_MAX
    vram_slider_min = Build.VRAM_GB_MIN
    vram_slider_max = Build.VRAM_GB_MAX
    price_slider_min = Decimal("0.00")
    price_slider_step = Decimal("0.01")

    def get_filter_values(self):
        sort = self.request.GET.get("sort", "default") or "default"
        valid_sorts = {
            "default",
            "price_asc",
            "price_desc",
            "sold_desc",
            "sold_asc",
            "best_seller_desc",
            "best_seller_asc",
            "date_desc",
            "date_asc",
        }
        if sort not in valid_sorts:
            sort = "default"
        if sort == "best_seller_desc":
            sort = "sold_desc"
        elif sort == "best_seller_asc":
            sort = "sold_asc"
        cpu_brand = self.get_choice_filter("cpu_brand", Build.CpuBrand.values)
        gpu_brand = self.get_choice_filter("gpu_brand", Build.GpuBrand.values)
        case_brand = self.get_choice_filter("case_brand", Build.CaseBrand.values)
        price_slider_max = self.get_price_slider_max()
        return {
            "cpu_brand": cpu_brand,
            "gpu_brand": gpu_brand,
            "case_brand": case_brand,
            "sort": sort,
            "price_max": self.get_number_filter("price_max", price_slider_max, self.price_slider_min, price_slider_max),
            "ram_max": self.get_slider_value("ram_max", self.ram_slider_max),
            "vram_max": self.get_slider_value("vram_max", self.vram_slider_max),
        }

    def get_choice_filter(self, name, valid_values):
        value = self.request.GET.get(name, "")
        return value if value in valid_values else ""

    def get_slider_value(self, name, default):
        raw_value = self.request.GET.get(name)
        if raw_value in (None, ""):
            return default
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return default
        minimum = self.ram_slider_min if name == "ram_max" else self.vram_slider_min
        return max(minimum, min(default, value))

    def get_number_filter(self, name, default, minimum, maximum):
        raw_value = self.request.GET.get(name)
        if raw_value in (None, ""):
            return default
        try:
            value = Decimal(str(raw_value).replace(",", ".")).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return default
        return max(minimum, min(maximum, value))

    def get_price_slider_max(self):
        if hasattr(self, "_price_slider_max"):
            return self._price_slider_max
        max_price = (
            Build.objects.filter(is_visible=True, is_archived=False)
            .aggregate(max_price=Max("price"))
            .get("max_price")
        )
        if not max_price or max_price <= 0:
            self._price_slider_max = Decimal("10000.00")
            return self._price_slider_max
        rounded = (max(max_price, Decimal("10000")) / Decimal("500")).to_integral_value(rounding=ROUND_CEILING) * Decimal("500")
        self._price_slider_max = rounded.quantize(Decimal("0.01"))
        return self._price_slider_max

    def get_queryset(self):
        self.filters = self.get_filter_values()
        queryset = Build.objects.filter(is_visible=True, is_archived=False)

        if self.filters["cpu_brand"]:
            queryset = queryset.filter(cpu_brand=self.filters["cpu_brand"])
        if self.filters["gpu_brand"]:
            queryset = queryset.filter(gpu_brand=self.filters["gpu_brand"])
        if self.filters["case_brand"]:
            queryset = queryset.filter(case_brand=self.filters["case_brand"])
        if self.filters["price_max"] < self.get_price_slider_max():
            queryset = queryset.filter(price__lte=self.filters["price_max"])
        if self.filters["ram_max"] < self.ram_slider_max:
            queryset = queryset.filter(ram_gb__lte=self.filters["ram_max"])
        if self.filters["vram_max"] < self.vram_slider_max:
            queryset = queryset.filter(vram_gb__lte=self.filters["vram_max"])
        builds = list(queryset.order_by("-is_featured", "sort_order", "-created_at"))

        sort = self.filters["sort"]
        if sort == "price_asc":
            builds.sort(key=lambda build: (build.price, build.sort_order, build.name.casefold()))
        elif sort == "price_desc":
            builds.sort(key=lambda build: (build.price, build.sort_order, build.name.casefold()), reverse=True)
        elif sort == "sold_desc":
            builds.sort(key=lambda build: (-build.sold_count, build.sort_order, -build.created_at.timestamp()))
        elif sort == "sold_asc":
            builds.sort(key=lambda build: (build.sold_count, build.sort_order, -build.created_at.timestamp()))
        elif sort == "date_asc":
            builds.sort(key=lambda build: (build.release_date, build.name.casefold(), build.pk))
        elif sort == "date_desc":
            builds.sort(key=lambda build: (build.release_date, build.name.casefold(), build.pk), reverse=True)

        self.result_count = len(builds)
        return builds

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = getattr(self, "filters", self.get_filter_values())
        active_filters_count = sum(
            [
                bool(filters["cpu_brand"]),
                bool(filters["gpu_brand"]),
                bool(filters["case_brand"]),
                filters["sort"] != "default",
                filters["price_max"] < self.get_price_slider_max(),
                filters["ram_max"] < self.ram_slider_max,
                filters["vram_max"] < self.vram_slider_max,
            ]
        )
        context["filters"] = filters
        context["active_filters_count"] = active_filters_count
        context["result_count"] = getattr(self, "result_count", len(context["builds"]))
        context["price_slider_min"] = self.price_slider_min
        context["price_slider_max"] = self.get_price_slider_max()
        context["price_slider_step"] = self.price_slider_step
        context["ram_slider_min"] = self.ram_slider_min
        context["ram_slider_max"] = self.ram_slider_max
        context["vram_slider_min"] = self.vram_slider_min
        context["vram_slider_max"] = self.vram_slider_max
        context["cpu_brand_options"] = [
            {"value": value, "label": label}
            for value, label in Build.CpuBrand.choices
        ]
        context["gpu_brand_options"] = [
            {"value": value, "label": label}
            for value, label in Build.GpuBrand.choices
        ]
        context["case_brand_options"] = [
            {"value": value, "label": label}
            for value, label in Build.CaseBrand.choices
        ]
        context["sort_options"] = [
            {"value": "default", "label": _("Predefinito")},
            {"value": "price_asc", "label": _("Prezzo crescente")},
            {"value": "price_desc", "label": _("Prezzo decrescente")},
            {"value": "sold_desc", "label": _("Piu vendute")},
            {"value": "sold_asc", "label": _("Meno vendute")},
            {"value": "date_desc", "label": _("Data uscita recente")},
            {"value": "date_asc", "label": _("Data uscita meno recente")},
        ]
        return context


class BuildDetailView(DetailView):
    template_name = "catalog/build_detail.html"
    model = Build
    context_object_name = "build"

    def get_queryset(self):
        return Build.objects.filter(is_visible=True, is_archived=False)

    def get_gallery_item(self, image_file, alt):
        item = {
            "url": image_file.url,
            "alt": alt,
        }
        try:
            item["width"] = image_file.width
            item["height"] = image_file.height
        except (OSError, ValueError):
            pass
        return item

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gallery_items = []
        if self.object.primary_image:
            gallery_items.append(self.get_gallery_item(self.object.primary_image, self.object.localized_name))
        for image in self.object.gallery_images.all():
            gallery_items.append(self.get_gallery_item(image.image, image.alt_text or self.object.localized_name))
        context["gallery_items"] = gallery_items
        initial = {}
        if self.request.user.is_authenticated:
            initial = {
                "full_name": self.request.user.get_full_name() or self.request.user.username,
                "email": self.request.user.email,
                "phone": self.request.user.phone,
            }
        context["purchase_form"] = BuildPurchaseRequestForm(initial=initial)
        return context


class CustomBuildRequestView(FormView):
    template_name = "catalog/custom_build_request.html"
    form_class = CustomBuildRequestForm

    def get(self, request, *args, **kwargs):
        return redirect(f"{reverse('core:home')}#custom-section")

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, _("Devi accedere per inviare una richiesta personalizzata."))
            return redirect(f"{reverse('accounts:login')}?next={reverse('core:home')}")
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        request_obj = form.save(commit=False)
        request_obj.user = self.request.user
        request_obj.save()
        notify_custom_request_submitted(request_obj, request=self.request)
        messages.success(
            self.request,
            _("Richiesta inviata correttamente. Ora la trovi nel tuo account con stato In approvazione."),
        )
        return redirect("accounts:dashboard")


class CustomBuildPaymentView(LoginRequiredMixin, TemplateView):
    template_name = "catalog/custom_request_payment.html"

    def get_checkout_methods(self):
        return [
            {
                "value": CustomBuildPayment.CheckoutMethod.PAYPAL,
                "label": _("PayPal"),
                "eyebrow": _("Wallet protetto"),
                "description": _("In futuro il cliente verra reindirizzato al checkout ufficiale PayPal Business."),
                "badges": ["PayPal"],
            },
            {
                "value": CustomBuildPayment.CheckoutMethod.MASTERCARD,
                "label": _("Mastercard"),
                "eyebrow": _("Carta di credito o debito"),
                "description": _("Flusso pronto per un futuro gateway carta con circuito Mastercard."),
                "badges": ["Mastercard"],
            },
            {
                "value": CustomBuildPayment.CheckoutMethod.VISA,
                "label": _("Visa"),
                "eyebrow": _("Carta di credito o debito"),
                "description": _("Flusso pronto per un futuro gateway carta con circuito Visa."),
                "badges": ["Visa"],
            },
            {
                "value": CustomBuildPayment.CheckoutMethod.AMEX,
                "label": _("American Express"),
                "eyebrow": _("Carta dedicata"),
                "description": _("Flusso pronto per un futuro checkout carta dedicato ad American Express."),
                "badges": ["Amex"],
            },
        ]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.custom_request = get_object_or_404(
            CustomBuildRequest.objects.select_related("user", "reviewed_by"),
            pk=kwargs["pk"],
            user=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action == "start_payment":
            start_form = CheckoutStartForm(request.POST)
            if not start_form.is_valid():
                context = self.get_context_data(start_checkout_form=start_form)
                return self.render_to_response(context)
            try:
                _payment, session = start_custom_request_checkout(
                    self.custom_request,
                    user=request.user,
                    checkout_method=start_form.cleaned_data["checkout_method"],
                    return_url=reverse("catalog:custom_request_payment", kwargs={"pk": self.custom_request.pk}),
                    cancel_url=reverse("catalog:custom_request_payment", kwargs={"pk": self.custom_request.pk}),
                )
            except (PaymentConfigurationError, PaymentGatewayError, PaymentStateError) as exc:
                messages.error(request, str(exc))
            else:
                log_admin_action(
                    request.user,
                    "start_custom_payment",
                    _("Avviato pagamento richiesta %(reference)s") % {"reference": self.custom_request.reference_code},
                    _payment,
                )
                if session.redirect_url:
                    return redirect(session.redirect_url)
                messages.info(request, session.message or _("Checkout dev avviato. Completa ora il passaggio di conferma pagamento."))
            return redirect("catalog:custom_request_payment", pk=self.custom_request.pk)

        if action == "confirm_checkout":
            payment = self.custom_request.active_payment
            if not payment:
                messages.error(request, _("Nessun pagamento attivo da completare."))
                return redirect("catalog:custom_request_payment", pk=self.custom_request.pk)

            simulation_form = SimulatedCheckoutConfirmForm(request.POST)
            if not simulation_form.is_valid():
                context = self.get_context_data(simulation_form=simulation_form)
                return self.render_to_response(context)

            try:
                finalized_payment = finalize_simulated_payment(
                    payment,
                    success=simulation_form.cleaned_data["simulation_result"] == "success",
                )
            except PaymentStateError as exc:
                messages.error(request, str(exc))
            else:
                self.custom_request.refresh_from_db()
                if finalized_payment.status == CustomBuildPayment.Status.SUCCEEDED:
                    log_admin_action(
                        request.user,
                        "payment_succeeded",
                        _("Pagamento confermato richiesta %(reference)s") % {"reference": self.custom_request.reference_code},
                        finalized_payment,
                    )
                    notify_custom_request_paid(self.custom_request, finalized_payment, request=request)
                    notify_admin_payment_received(self.custom_request, finalized_payment, request=request)
                    messages.success(request, _("Pagamento test registrato correttamente. Ora trovi il riepilogo completo nella schermata checkout."))
                else:
                    log_admin_action(
                        request.user,
                        "payment_failed",
                        _("Pagamento fallito richiesta %(reference)s") % {"reference": self.custom_request.reference_code},
                        finalized_payment,
                    )
                    messages.error(request, _("Il checkout dev ha restituito un esito negativo. Puoi riprovare quando vuoi dalla stessa pagina."))
            return redirect("catalog:custom_request_payment", pk=self.custom_request.pk)

        messages.error(request, _("Azione di pagamento non riconosciuta."))
        return redirect("catalog:custom_request_payment", pk=self.custom_request.pk)

    def get_checkout_stage(self, active_payment):
        status = self.custom_request.status

        if status == CustomBuildRequest.Status.IN_APPROVAL:
            return "waiting"
        if status in {CustomBuildRequest.Status.REJECTED, CustomBuildRequest.Status.CANCELLED}:
            return "closed"
        if active_payment is not None:
            return "confirm"
        if status == CustomBuildRequest.Status.PAID:
            return "success"
        if status == CustomBuildRequest.Status.PAYMENT_FAILED:
            return "failure"
        if status in {CustomBuildRequest.Status.APPROVED, CustomBuildRequest.Status.PAYMENT_PENDING}:
            return "review"
        return "review"

    def get_context_data(self, simulation_form=None, start_checkout_form=None, **kwargs):
        context = super().get_context_data(**kwargs)
        self.custom_request = CustomBuildRequest.objects.select_related("user", "reviewed_by").get(
            pk=self.custom_request.pk,
            user=self.request.user,
        )
        runtime = get_paypal_runtime_summary()
        active_payment = self.custom_request.active_payment
        latest_payment = self.custom_request.latest_payment
        checkout_payment = active_payment or latest_payment
        checkout_stage = self.get_checkout_stage(active_payment)
        selected_checkout_method = (
            active_payment.checkout_method
            if active_payment
            else (latest_payment.checkout_method if checkout_stage in {"success", "failure"} and latest_payment else CustomBuildPayment.CheckoutMethod.PAYPAL)
        )
        context.update(
            {
                "custom_request": self.custom_request,
                "payment_history": self.custom_request.payments_queryset(),
                "latest_payment": latest_payment,
                "active_payment": active_payment,
                "checkout_payment": checkout_payment,
                "checkout_stage": checkout_stage,
                "checkout_methods": self.get_checkout_methods(),
                "selected_checkout_method": selected_checkout_method,
                "payment_runtime": runtime,
                "start_checkout_form": start_checkout_form or CheckoutStartForm(initial={"checkout_method": selected_checkout_method}),
                "simulation_form": simulation_form or SimulatedCheckoutConfirmForm(),
                "show_start_payment": self.custom_request.is_payment_available and active_payment is None,
                "show_checkout_confirmation": active_payment is not None and runtime["provider"] == "simulated",
                "start_payment_label": _("Riprova il pagamento") if self.custom_request.status == CustomBuildRequest.Status.PAYMENT_FAILED else _("Conferma e procedi al pagamento"),
            }
        )
        return context


CustomBuildRequestView = method_decorator(never_cache, name="dispatch")(CustomBuildRequestView)
CustomBuildPaymentView = method_decorator(never_cache, name="dispatch")(CustomBuildPaymentView)


class BuildPurchaseRequestCreateView(LoginRequiredMixin, FormView):
    form_class = BuildPurchaseRequestForm

    def dispatch(self, request, *args, **kwargs):
        self.build = get_object_or_404(Build, slug=kwargs["slug"], is_visible=True, is_archived=False)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            purchase_request = form.save(commit=False)
            purchase_request.build = self.build
            purchase_request.user = self.request.user
            purchase_request.save()

            custom_request = CustomBuildRequest.objects.create(
                user=self.request.user,
                request_origin=CustomBuildRequest.Origin.CATALOG_BUILD,
                requested_build=self.build,
                budget_max=self.build.price if self.build.price and self.build.price > 0 else None,
                currency="EUR",
                notes=_("Richiesta inviata dalla build %(build)s.\n\nMessaggio cliente:\n%(message)s")
                % {
                    "build": self.build.localized_name,
                    "message": purchase_request.message or _("Nessuna nota aggiuntiva."),
                },
            )

            purchase_request.custom_request = custom_request
            purchase_request.save(update_fields=["custom_request", "updated_at"])

        notify_custom_request_submitted(custom_request, request=self.request)
        messages.success(
            self.request,
            _("Richiesta build inviata correttamente. La trovi ora in approvazione nel tuo account e il team potra approvarla prima del pagamento."),
        )
        return redirect("accounts:dashboard")

    def form_invalid(self, form):
        messages.error(self.request, _("Controlla i dati inseriti e riprova."))
        return redirect("catalog:build_detail", slug=self.build.slug)
