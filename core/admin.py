from django.contrib import admin
from django.utils.html import format_html
from .models import (
    User,
    Property,
    Booking,
    Gift,
    Investment,
    Commission,
    Review,
    AgentVerification,
    InvestmentROI,
    Favorite,
    RefundLog
)

# --- USER ---
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'role', 'is_verified', 'membership_tier', 'membership_expires_at', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_verified', 'membership_tier')
    search_fields = ('email', 'full_name')
    readonly_fields = ('date_joined',)

# --- PROPERTY ---
@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'property_type', 'agent', 'price', 'is_approved', 'is_available', 'created_at')
    list_filter = ('property_type', 'is_approved')
    search_fields = ('title', 'location', 'agent__email')
    actions = ['approve_selected']

    def approve_selected(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} properties approved.")
    approve_selected.short_description = "Approve selected properties"

# --- BOOKING ---
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'property', 'start_date', 'end_date', 'total_price', 'is_paid', 'is_cancelled', 'tx_ref', 'created_at')
    list_filter = ('is_paid', 'is_cancelled')
    search_fields = ('user__email', 'property__title', 'tx_ref')

# --- GIFT ---
@admin.register(Gift)
class GiftAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient_email', 'property', 'status', 'expires_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('sender__email', 'recipient_email')

# --- INVESTMENT ---
@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ('investor', 'property', 'payment_plan', 'amount_paid', 'remaining_balance', 'status', 'tx_ref', 'started_at')
    list_filter = ('payment_plan', 'status')
    search_fields = ('investor__email', 'property__title', 'tx_ref')

# --- COMMISSION ---
@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('agent', 'booking', 'amount', 'is_withdrawn', 'withdrawal_requested', 'created_at')
    list_filter = ('is_withdrawn', 'withdrawal_requested')
    search_fields = ('agent__email', 'booking__tx_ref')

# --- REVIEW ---
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'review_type', 'property', 'agent', 'rating', 'is_approved', 'created_at')
    list_filter = ('review_type', 'is_approved', 'rating')
    search_fields = ('user__email', 'property__title', 'agent__email')
    actions = ['approve_reviews']

    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} reviews approved.")
    approve_reviews.short_description = "Approve selected reviews"

# --- AGENT VERIFICATION ---
@admin.register(AgentVerification)
class AgentVerificationAdmin(admin.ModelAdmin):
    list_display = ('agent', 'is_verified', 'was_rejected', 'submitted_at')
    search_fields = ('agent__email',)
    list_filter = ('is_verified', 'was_rejected')

# --- ROI ---
@admin.register(InvestmentROI)
class InvestmentROIAdmin(admin.ModelAdmin):
    list_display = ('investment', 'amount', 'date_paid', 'note')
    search_fields = ('investment__investor__email', 'investment__property__title')

# --- FAVORITE ---
@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'property', 'created_at')
    search_fields = ('user__email', 'property__title')

# --- REFUND LOG ---
@admin.register(RefundLog)
class RefundLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'reason', 'created_at')
    search_fields = ('user__email', 'reason')
