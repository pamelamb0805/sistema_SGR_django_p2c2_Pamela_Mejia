#correccion eva2-n3
from django.shortcuts import render

# Create your views here.
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import ArchiveDevicesForm
from .models import Device


def get_visible_devices(user):
    """Dispositivos activos que el usuario puede ver (scoping por organización)."""
    qs = Device.objects.filter(deleted_at__isnull=True).select_related(
        "product", "zone"
    )
    if user.is_superuser:
        return qs
    profile = getattr(user, "profile", None)
    # Sin perfil u organización: no ve nada (nunca acceso global por error)
    if profile is None or profile.organization_id is None:
        return qs.none()
    return qs.filter(zone__organization=profile.organization)


@login_required
@permission_required("devices.view_device", raise_exception=True)
def device_list(request):
    devices = get_visible_devices(request.user)
    can_archive = request.user.has_perm("devices.change_device")

    if request.method == "POST":
        if not can_archive:
            raise PermissionDenied
        form = ArchiveDevicesForm(request.POST, queryset=devices)
        if form.is_valid():
            now = timezone.now()
            updated = form.cleaned_data["devices"].update(
                deleted_at=now, updated_at=now
            )
            messages.success(request, f"{updated} dispositivo(s) archivado(s).")
        else:
            messages.error(request, "Selecciona al menos un dispositivo válido.")
        return redirect("devices:device_list")

    return render(
        request,
        "devices/device_list.html",
        {"devices": devices, "can_archive": can_archive},
    )