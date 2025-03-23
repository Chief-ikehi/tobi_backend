# core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from .views import (
    # Auth
    RegisterView, LoginView, UserProfileView, get_jwt_for_user,
    SwitchUserRoleView, AssignAdminRoleView,

    # Properties & Favorites
    PropertyViewSet, FavoriteViewSet,

    # Bookings
    BookingCreateView, MarkBookingAsPaidView,
    CancelBookingView, AdminCancelBookingView,

    # Wallet & Commissions
    AgentWalletView, RequestWithdrawalView, ApproveWithdrawalView,

    # Gifts
    GiftCreateView, GiftDecisionView, ExpireOldGiftsView, ReassignGiftView,

    # Investments
    CreateInvestmentView, TopUpInvestmentView,

    # Reviews
    ReviewViewSet, AdminReviewModerationView,

    # Agent Verification
    AgentVerificationUploadView, AgentVerificationApprovalView, RejectAgentVerificationView,

    # Dashboard, Refunds & Payments
    DashboardView, RefundLogView, InitiatePaymentView, VerifyFlutterwavePaymentView,
    FlutterwaveWebhookView, InvestmentROIView, AdminDashboardView,
)

# --- Swagger Schema View ---
schema_view = get_schema_view(
    openapi.Info(
        title="Your API Title",
        default_version='v1',
        description="API documentation",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@yourapi.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

# --- DRF Router ---
router = DefaultRouter()
router.register(r'properties', PropertyViewSet, basename='property')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'favorites', FavoriteViewSet, basename='favorites')

# --- URL Patterns ---
urlpatterns = [
    # --- Auth ---
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/user/', UserProfileView.as_view(), name='user-profile'),
    path('auth/', include('allauth.socialaccount.urls')),  # Google login
    path('auth/get-jwt/', get_jwt_for_user),
    path('profile/switch-role/', SwitchUserRoleView.as_view(), name='switch-role'),
    path('admin/users/<int:user_id>/make-admin/', AssignAdminRoleView.as_view(), name='assign-admin'),

    # --- Bookings ---
    path('bookings/create/', BookingCreateView.as_view(), name='create-booking'),
    path('bookings/<int:booking_id>/pay/', MarkBookingAsPaidView.as_view(), name='mark-paid'),
    path('bookings/<int:booking_id>/cancel/', CancelBookingView.as_view(), name='cancel-booking'),
    path('admin/bookings/<int:booking_id>/cancel/', AdminCancelBookingView.as_view(), name='admin-cancel-booking'),

    # --- Wallet & Commissions ---
    path('wallet/agent/', AgentWalletView.as_view(), name='agent-wallet'),
    path('commissions/<int:commission_id>/request-withdrawal/', RequestWithdrawalView.as_view(), name='request-withdrawal'),
    path('admin/commissions/pending-withdrawals/', ApproveWithdrawalView.as_view(), name='view-withdrawals'),
    path('admin/commissions/<int:commission_id>/approve-withdrawal/', ApproveWithdrawalView.as_view(), name='approve-withdrawal'),

    # --- Gifts ---
    path('gifts/create/', GiftCreateView.as_view(), name='create-gift'),
    path('gifts/<int:gift_id>/<str:action>/', GiftDecisionView.as_view(), name='gift-action'),
    path('gifts/expire-old/', ExpireOldGiftsView.as_view(), name='expire-gifts'),
    path('gifts/<int:gift_id>/reassign/', ReassignGiftView.as_view(), name='reassign-gift'),

    # --- Investments ---
    path('investments/create/', CreateInvestmentView.as_view(), name='create-investment'),
    path('investments/<int:investment_id>/top-up/', TopUpInvestmentView.as_view(), name='topup-investment'),

    # --- Reviews ---
    path('reviews/pending/', AdminReviewModerationView.as_view(), name='pending-reviews'),
    path('reviews/<int:review_id>/approve/', AdminReviewModerationView.as_view(), name='approve-review'),

    # --- Agent Verification ---
    path('agents/verify-docs/', AgentVerificationUploadView.as_view(), name='agent-verification'),
    path('admin/agent-verifications/', AgentVerificationApprovalView.as_view(), name='pending-verifications'),
    path('admin/agent-verifications/<int:verification_id>/approve/', AgentVerificationApprovalView.as_view(), name='approve-verification'),
    path('admin/agent-verifications/<int:verification_id>/reject/', RejectAgentVerificationView.as_view(), name='reject-verification'),

    # --- Dashboard, Refunds, and Payments ---
    path('dashboard/', DashboardView.as_view(), name='user-dashboard'),
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('refunds/', RefundLogView.as_view(), name='refund-logs'),

    path('payments/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('payments/verify/', VerifyFlutterwavePaymentView.as_view(), name='verify-payment'),
    path('payments/webhook/', FlutterwaveWebhookView.as_view(), name='flutterwave-webhook'),
    path('admin/roi/', InvestmentROIView.as_view(), name='investment-roi'),

    # --- API Docs (Swagger/OpenAPI) ---
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# --- Append router URLs ---
urlpatterns += router.urls