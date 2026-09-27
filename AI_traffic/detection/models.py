from django.db import models
from django.contrib.auth.models import User


class RegisteredUser(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)
    vehicle_number = models.CharField(max_length=20, unique=True)
    image = models.ImageField(upload_to='user_images/')
    password = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.vehicle_number})"




class VehicleOwner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=15)
    vehicle_number = models.CharField(max_length=20, unique=True)
    image = models.ImageField(upload_to='owner_images/')
    def __str__(self):
        return f"{self.name} ({self.vehicle_number})"
    

class TrafficViolation(models.Model):
    owner = models.ForeignKey(VehicleOwner, on_delete=models.CASCADE)
    violation_type = models.CharField(max_length=100)
    date = models.DateTimeField(auto_now_add=True)
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=150)

    # ✅ Add ImageField to store violation proof
    image = models.ImageField(upload_to='violation_images/', null=True, blank=True)

    def __str__(self):
        return f"{self.violation_type} - {self.owner.vehicle_number}"


from django.db import models
from django.contrib.auth.models import User

class Violation(models.Model):
    VIOLATION_TYPES = (
        ("NO_HELMET", "No Helmet"),
        ("NO_SEATBELT", "No Seatbelt"),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    vehicle_number = models.CharField(max_length=20)
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPES)
    date = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="violations/", null=True, blank=True)

    def __str__(self):
        return f"{self.vehicle_number} - {self.violation_type}"
