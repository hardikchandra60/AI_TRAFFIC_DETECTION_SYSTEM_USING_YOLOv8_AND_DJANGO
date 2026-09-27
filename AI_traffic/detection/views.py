# views.py (final)
import os
import queue
import threading
import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, StreamingHttpResponse
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client

from .models import RegisteredUser, VehicleOwner, TrafficViolation
# We import the generator only to stream video; no other imports to avoid circulars
from AI_traffic.helmet_seatbelt_detect import gen_frames, save_violation_image

logger = logging.getLogger(__name__)

# ----------------------------
# Simple pages & auth views
# ----------------------------
def home(request):
    return render(request, 'home.html')


def register(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        contact = request.POST.get('contact', '').strip()
        vehicle_number = request.POST.get('vehicle_number', '').strip().upper()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        image = request.FILES.get('image')

        if not vehicle_number:
            messages.error(request, "Vehicle number required.")
            return redirect('register')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        if VehicleOwner.objects.filter(vehicle_number__iexact=vehicle_number).exists():
            messages.error(request, "This vehicle number is already registered.")
            return redirect('register')

        # create Django user and vehicle owner record
        user = User.objects.create_user(username=vehicle_number, password=password, email=request.POST.get('email', '').strip())
        VehicleOwner.objects.create(
            user=user,
            name=name,
            contact=contact,
            vehicle_number=vehicle_number,
            image=image
        )

        # optional RegisteredUser mirror (if used)
        try:
            RegisteredUser.objects.create(
                name=name,
                contact=contact,
                vehicle_number=vehicle_number,
                image=image,
                password=password
            )
        except Exception:
            logger.debug("RegisteredUser create skipped (optional).")

        messages.success(request, "Registration successful. You may now log in.")
        return redirect('login')

    return render(request, 'register.html')


def login_view(request):
    if request.method == 'POST':
        vehicle_number = request.POST.get('vehicle_number', '').strip().upper()
        password = request.POST.get('password', '')

        try:
            owner = VehicleOwner.objects.get(vehicle_number__iexact=vehicle_number)

            # authenticate using the linked Django User
            user = authenticate(username=owner.user.username, password=password)

            if user:
                login(request, user)

                # 🔥 ROLE-BASED REDIRECTION HERE
                if user.is_staff or user.is_superuser:
                    messages.success(request, f"Welcome Admin, {user.username}!")
                    return redirect('adminhome')  # staff admin home

                # normal user goes to dashboard
                messages.success(request, f"Welcome back, {owner.name}!")
                return redirect('dashboard')

            else:
                messages.error(request, "Invalid credentials.")

        except VehicleOwner.DoesNotExist:
            messages.error(request, "No account found with this vehicle number.")

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')


@login_required
def dashboard(request):
    owner = VehicleOwner.objects.get(user=request.user)
    recent_violations = TrafficViolation.objects.filter(owner=owner).order_by('-date')[:10]
    return render(request, 'dashboard.html', {'owner': owner, 'violations': recent_violations})


# ----------------------------
# API endpoint: find owner by plate (used by detection module)
# Supports GET ?plate=XXXX
# ----------------------------
@csrf_exempt
def find_owner_by_plate(request):
    plate = (request.GET.get('plate') or request.POST.get('plate') or '').strip().upper()
    if not plate:
        return JsonResponse({'found': False, 'message': 'plate missing'}, status=400)

    try:
        owner = VehicleOwner.objects.get(vehicle_number__iexact=plate)
        data = {
            'found': True,
            'name': owner.name,
            'vehicle_number': owner.vehicle_number,
            'email': owner.user.email if hasattr(owner, 'user') else '',
            'phone': owner.contact
        }
        return JsonResponse(data)
    except VehicleOwner.DoesNotExist:
        return JsonResponse({'found': False})


# ----------------------------
# API endpoint: record_violation (called by detection module)
# Accepts multipart POST with vehicle_number, violation_type, location (optional), image (optional)
# This endpoint creates TrafficViolation and sends alerts (email + Twilio SMS if configured)
# ----------------------------
@csrf_exempt
def record_violation(request):
    if request.method == "POST":
        vehicle_number = request.POST.get+22("vehicle_number")
        violation_type = request.POST.get("violation_type")
        location = request.POST.get("location")
        image = request.FILES.get("image")

        # 1️⃣ Check owner exists
        owner = VehicleOwner.objects.filter(vehicle_number=vehicle_number).first()

        if not owner:
            return JsonResponse({
                "status": "not_found",
                "message": "Vehicle number not found in database."
            }, status=404)

        # 2️⃣ Create violation (no errors now)
        violation = TrafficViolation.objects.create(
            owner=owner,
            violation_type=violation_type,
            location=location,
            fine_amount=500,
            image=image
        )

        # 3️⃣ Send alert
        send_mail(
            subject=f"Traffic Violation Alert - {owner.vehicle_number}",
            message=f"Dear {owner.name},\n\nYour vehicle committed the following violation:\n"
                    f"{violation_type}\n"
                    f"Location: {location}\n\nPlease pay the fine amount: ₹500.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.user.email],
            fail_silently=False,
        )

        return JsonResponse({
            "status": "success",
            "message": "Violation recorded and owner notified."
        })

    return JsonResponse({"error": "Invalid request"}, status=400)



# ----------------------------
# Live streaming view (uses generator from detection module)
# ----------------------------
def live_feed(request):
    return StreamingHttpResponse(
        gen_frames(), content_type='multipart/x-mixed-replace; boundary=frame'
    )



from django.contrib.auth.models import User
from .models import VehicleOwner, TrafficViolation  # if you have these models

@login_required
def admin_home(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('dashboard')

    context = {
        "username": request.user.username,
        "total_users": User.objects.count(),
        "vehicle_count": VehicleOwner.objects.count(),
        "pending_violations": TrafficViolation.objects.filter(status="pending").count() if hasattr(TrafficViolation, 'status') else 0,
    }

    return render(request, "adminhome.html", context)



from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from .models import Violation

def is_staff_user(user):
    return user.is_staff  # Only staff can manage users

@login_required
@user_passes_test(is_staff_user)
def manage_users(request):
    users = User.objects.filter(is_superuser=False).order_by('-date_joined')
    return render(request, 'manage_users.html', {'users': users})


@login_required
@user_passes_test(is_staff_user)
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()
        messages.success(request, "User details updated successfully.")
        return redirect('manage_users')

    return render(request, 'edit_user.html', {'user': user})

@login_required
@user_passes_test(is_staff_user)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    messages.success(request, "User deleted successfully.")
    return redirect('manage_users')

@login_required
@user_passes_test(is_staff_user)
def violation_list(request):
    violations = Violation.objects.all().order_by('-date')
    return render(request, 'violation_list.html', {'violations': violations})

@login_required
@user_passes_test(is_staff_user)
def delete_violation(request, vid):
    v = get_object_or_404(Violation, id=vid)
    v.delete()
    messages.success(request, "Violation record removed.")
    return redirect('violation_list')





def vehicle_list(request):
    return render(request, "vehicle_list.html")

def add_vehicle(request):
    return render(request, "add_vehicle.html")

def reports(request):
    return render(request, "reports.html")





from django.http import HttpResponse
from django.conf import settings
from django.core.mail import send_mail
from .models import VehicleOwner, TrafficViolation

# If using Twilio
from twilio.rest import Client

def send_sms(number, message):
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to="+916388674946"
        )
    except Exception as e:
        print("SMS Error:", e)


def test_notification(request):
    # Your details
    vehicle_number = "UP51T2212"

    owner = VehicleOwner.objects.filter(vehicle_number=vehicle_number).first()

    if owner is None:
        return HttpResponse("❌ Owner not found in DB. Add it in VehicleOwner table first.")

    # Create a dummy violation
    violation = TrafficViolation.objects.create(
        owner=owner,
        violation_type="Manual Test: Without Helmet",
        fine_amount=500,
        location="Test Area"
    )

    # ---- SMS ----
    sms_message = f"Traffic Alert ⚠️\nYour vehicle {vehicle_number} committed: {violation.violation_type}. Fine ₹500."
    send_sms(owner.contact, sms_message)

    # ---- Email ----
    email_message = (
        f"Dear {owner.name},\n\n"
        f"Your vehicle ({vehicle_number}) has a new violation entry:\n"
        f"Violation: {violation.violation_type}\n"
        f"Fine: ₹500\n"
        f"Location: Test Area\n\n"
        f"This is a manual test alert.\n"
    )

    send_mail(
        "Traffic Violation Test Alert",
        email_message,
        settings.EMAIL_HOST_USER,
        [owner.user.email],
        fail_silently=False
    )

    return HttpResponse("✅ Test Notification Sent Successfully!")
