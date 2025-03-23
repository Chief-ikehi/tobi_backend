# core/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta

class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        AGENT = "AGENT", "Agent"
        INVESTOR = "INVESTOR", "Investor"
        ADMIN = "ADMIN", "Admin"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    is_verified = models.BooleanField(default=False)
    membership_tier = models.CharField(max_length=20, blank=True, null=True)  # 'Gold' or 'Platinum'
    membership_expires_at = models.DateTimeField(null=True, blank=True)
    shortlet_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # ₦5M credit
    was_verified_as_agent = models.BooleanField(default=False)
    was_verified_as_investor = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return self.email

class Property(models.Model):
    PROPERTY_TYPE_CHOICES = [
        ('shortlet', 'Short-Let'),
        ('investment', 'Investment'),
        ('sale', 'Outright Sale'),
    ]

    agent = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': User.Role.AGENT})
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES)
    amenities = models.JSONField(default=list)  # We'll store amenities like ['Wi-Fi', 'Pool']
    images = models.JSONField(default=list)     # List of image URLs (Cloudinary)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_available = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)  # Admin must approve
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.location}"


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateField()
    end_date = models.DateField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_cancelled = models.BooleanField(default=False)  # ✅ New field
    is_paid = models.BooleanField(default=False)
    tx_ref = models.CharField(max_length=100, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('property', 'start_date', 'end_date')

    def __str__(self):
        return f"{self.user.email} - {self.property.title} ({self.start_date} to {self.end_date})"

class Commission(models.Model):
    agent = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': User.Role.AGENT})
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    withdrawal_requested = models.BooleanField(default=False)
    is_withdrawn = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.agent.full_name} - ₦{self.amount} from booking {self.booking.id}"

class Gift(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_gifts')
    recipient_email = models.EmailField()
    recipient_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_gifts')
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # for short-let gifts
    reassigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reassigned_gifts'
    )
    converted_to_credit = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender.email} → {self.recipient_email} ({self.status})"

class Investment(models.Model):
    PAYMENT_PLAN_CHOICES = [
        ('full', 'Full Payment'),
        ('installment', 'Installment Plan'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]

    investor = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': User.Role.INVESTOR})
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    payment_plan = models.CharField(max_length=20, choices=PAYMENT_PLAN_CHOICES)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    tx_ref = models.CharField(max_length=100, null=True, blank=True, unique=True)
    started_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('investor', 'property')

    def __str__(self):
        return f"{self.investor.email} - {self.property.title}"

class Review(models.Model):
    REVIEW_TYPE_CHOICES = [
        ('property', 'Property'),
        ('agent', 'Agent'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True, blank=True)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='agent_reviews')
    rating = models.PositiveIntegerField()
    comment = models.TextField()
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPE_CHOICES)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} → {self.review_type} ({self.rating})"

class AgentVerification(models.Model):
    agent = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': User.Role.AGENT})
    valid_id = models.URLField()
    cac_certificate = models.URLField()
    proof_of_location = models.URLField()
    property_ownership_doc = models.URLField()
    is_verified = models.BooleanField(default=False)
    rejection_reason = models.TextField(null=True, blank=True)
    was_rejected = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Verification - {self.agent.email}"

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'property')

    def __str__(self):
        return f"{self.user.email} → {self.property.title}"

class RefundLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - ₦{self.amount} refund"

class InvestmentROI(models.Model):
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='rois')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_paid = models.DateField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"ROI: ₦{self.amount} for {self.investment.investor.email}"