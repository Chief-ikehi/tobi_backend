# core/views.py

# Standard Library
from datetime import timedelta
from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.permissions import AllowAny
from .models import Booking, Investment
import uuid
from core.utils import has_active_membership

# Django & DRF Core
from django.utils import timezone
from django.contrib.auth import authenticate
from django.db.models import Avg

from rest_framework import generics, viewsets, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

# Core App Models
from .models import (
    User, Property, Booking, Commission, Gift,
    Investment, Review, AgentVerification, Favorite, RefundLog, InvestmentROI
)

# Core App Serializers
from .serializers import (
    RegisterSerializer, UserSerializer, PropertySerializer,
    BookingSerializer, CommissionSerializer, GiftSerializer,
    InvestmentSerializer, FavoriteSerializer, ReviewSerializer,
    AgentVerificationSerializer, RefundLogSerializer, InvestmentROISerializer
)

# Core App Permissions
from .permissions import IsAgentOrReadOnly, IsAgentOwnerOrAdmin

import uuid
import requests
from django.conf import settings
FLW_SECRET = settings.FLW_SECRET


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def get_serializer_context(self):
        return {'request': self.request}


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(request, email=email, password=password)

        if not user:
            return Response({"detail": "Invalid credentials"}, status=400)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = Property.objects.filter()
    serializer_class = PropertySerializer

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAgentOwnerOrAdmin()]
        return [IsAgentOrReadOnly()]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.role == User.Role.ADMIN):
            return Property.objects.all()
        return Property.objects.filter(is_approved=True)

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.is_approved = False
        instance.save(update_fields=["is_approved"])

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def approve(self, request, pk=None):
        property = self.get_object()
        property.is_approved = True
        property.save()
        return Response({'status': 'property approved ✅'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reject(self, request, pk=None):
        property = self.get_object()
        property.delete()
        return Response({'status': 'property rejected and deleted ❌'})




@api_view(['POST'])
@permission_classes([AllowAny])
def get_jwt_for_user(request):
    email = request.data.get("email")
    try:
        user = User.objects.get(email=email)
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

class BookingCreateView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        property = serializer.validated_data['property']
        start = serializer.validated_data['start_date']
        end = serializer.validated_data['end_date']
        user = self.request.user

        # Property must be approved + of type shortlet
        if not property.is_approved or property.property_type != 'shortlet':
            raise serializers.ValidationError("Property not available for short-let booking.")

        # Overlapping date check
        overlaps = Booking.objects.filter(
            property=property,
            is_cancelled=False,  # ✅ Ignore cancelled bookings
            start_date__lt=end,
            end_date__gt=start
        ).exists()

        if overlaps:
            raise serializers.ValidationError("This date range is already booked.")

        # Simple total price logic (flat rate per night)
        days = (end - start).days
        if days <= 0:
            raise serializers.ValidationError("Invalid date range.")
        total_price = days * property.price

        tx_ref = f"TobiTx-{uuid.uuid4()}"

        # Check if user has shortlet credit
        if user.shortlet_credit and user.shortlet_credit >= total_price:
            user.shortlet_credit -= total_price
            user.save()
            is_paid = True
        else:
            raise serializers.ValidationError("Insufficient shortlet credit to book this property.")

        serializer.save(user=user, total_price=total_price, tx_ref=tx_ref, is_paid=is_paid)

class MarkBookingAsPaidView(APIView):
    permission_classes = [permissions.IsAdminUser]  # ✅ Only Admins for now

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=404)

        if booking.is_paid:
            return Response({"message": "Already paid ✅"})

        booking.is_paid = True
        booking.save()
        return Response({"message": "Booking marked as paid 💰"})

class MarkBookingAsPaidView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=404)

        if booking.is_paid:
            return Response({"message": "Already paid ✅"})

        booking.is_paid = True
        booking.save()

        # Calculate and store commission
        property = booking.property
        agent = property.agent
        commission_amount = booking.total_price * Decimal("0.10")  # 10% commission

        Commission.objects.create(
            agent=agent,
            booking=booking,
            amount=commission_amount
        )

        return Response({
            "message": "Booking marked as paid 💰",
            "commission": f"{commission_amount} added to agent wallet 🏦"
        })

class AgentWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role != User.Role.AGENT:
            return Response({"error": "Only agents have wallets"}, status=403)

        commissions = Commission.objects.filter(agent=user, is_withdrawn=False)
        total_balance = sum(c.amount for c in commissions)

        return Response({
            "agent": user.full_name,
            "wallet_balance": total_balance,
            "commissions": CommissionSerializer(commissions, many=True).data
        })


class GiftCreateView(generics.CreateAPIView):
    serializer_class = GiftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        property = serializer.validated_data['property']
        recipient_email = serializer.validated_data['recipient_email']

        # Optionally: block gifting unapproved/investment properties
        if not property.is_approved:
            raise serializers.ValidationError("Property must be approved to be gifted.")

        recipient = User.objects.filter(email=recipient_email).first()

        serializer.save(
            sender=self.request.user,
            recipient_user=recipient,
            expires_at=timezone.now() + timedelta(days=7) if property.property_type == 'shortlet' else None
        )


class GiftDecisionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, gift_id, action):
        gift = Gift.objects.filter(id=gift_id, recipient_user=request.user).first()
        if not gift or gift.status != 'pending':
            return Response({"error": "Gift not found or already handled"}, status=400)

        if action == 'accept':
            gift.status = 'accepted'
        elif action == 'decline':
            gift.status = 'declined'
        else:
            return Response({"error": "Invalid action"}, status=400)

        gift.save()
        return Response({"message": f"Gift {action}ed."})

class ExpireOldGiftsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        now = timezone.now()
        expired = 0
        converted = 0

        # Expire short-let gifts past the expiration date
        gifts = Gift.objects.filter(
            property__property_type='shortlet',
            expires_at__lt=now,
            status='pending'
        )

        for gift in gifts:
            gift.status = 'expired'
            gift.save()
            expired += 1

            # Auto-convert to wallet credit if not reassigned
            if not gift.reassigned_to and not gift.converted_to_credit:
                gift.sender.wallet_balance += gift.property.price
                gift.converted_to_credit = True
                gift.sender.save()
                gift.save()
                converted += 1

        return Response({
            "expired": expired,
            "converted_to_credit": converted
        })

class ReassignGiftView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, gift_id):
        gift = Gift.objects.filter(id=gift_id, sender=request.user, status='pending').first()
        new_email = request.data.get("new_email")

        if not gift:
            return Response({"error": "Gift not found or cannot be reassigned"}, status=404)

        if gift.reassigned_to:
            return Response({"error": "Gift has already been reassigned"}, status=400)

        new_recipient = User.objects.filter(email=new_email).first()
        gift.recipient_email = new_email
        gift.recipient_user = new_recipient
        gift.reassigned_to = new_recipient
        gift.save()

        return Response({"message": "Gift successfully reassigned."})


class CreateInvestmentView(generics.CreateAPIView):
    serializer_class = InvestmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        property = serializer.validated_data['property']
        plan = serializer.validated_data['payment_plan']

        if user.role != User.Role.INVESTOR:
            raise serializers.ValidationError("Only investors can invest in properties.")

        if not property.is_approved:
            raise serializers.ValidationError("This property is not approved for investment.")

        if not property.cost_price:
            raise serializers.ValidationError("This property doesn't have a cost price set.")

        total_price = property.cost_price

        if plan == 'full':
            amount_paid = total_price
            remaining = 0
            user.membership_tier = "Platinum"
            user.membership_expires_at = timezone.now() + timedelta(days=365)
        elif plan == 'installment':
            amount_paid = total_price * Decimal("0.60")
            remaining = total_price - amount_paid
            user.membership_tier = "Gold"
            user.membership_expires_at = timezone.now() + timedelta(days=365)
            user.shortlet_credit = Decimal("5000000.00")
        else:
            raise serializers.ValidationError("Invalid payment plan.")

        tx_ref = f"TobiInvest-{uuid.uuid4()}"

        user.save()  # 👈 Save membership & credit
        serializer.save(
            investor=user,
            total_price=total_price,
            amount_paid=amount_paid,
            remaining_balance=remaining,
            tx_ref=tx_ref
        )

class TopUpInvestmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, investment_id):
        user = request.user
        amount = Decimal(request.data.get('amount', 0))

        if amount <= 0:
            return Response({"error": "Top-up amount must be greater than 0"}, status=400)

        try:
            investment = Investment.objects.get(id=investment_id, investor=user)
        except Investment.DoesNotExist:
            return Response({"error": "Investment not found or not yours"}, status=404)

        if investment.status == "completed":
            return Response({"error": "This investment is already completed"}, status=400)

        if amount > investment.remaining_balance:
            return Response({"error": "Amount exceeds remaining balance"}, status=400)

        investment.amount_paid += amount
        investment.remaining_balance -= amount

        if investment.remaining_balance == 0:
            investment.status = "completed"
            user.membership_tier = "Platinum"
            user.membership_expires_at = timezone.now() + timedelta(days=365)
            user.shortlet_credit = 0  # Optional: wipe shortlet credit on full ownership
            user.save()

        investment.save()

        return Response({
            "message": "Top-up successful",
            "new_balance": str(investment.remaining_balance),
            "status": investment.status
        })


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.filter(is_approved=True)
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AdminReviewModerationView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        reviews = Review.objects.filter(is_approved=False)
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    def post(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id, is_approved=False)
        except Review.DoesNotExist:
            return Response({"error": "Review not found or already approved"}, status=404)

        review.is_approved = True
        review.save()
        return Response({"message": "Review approved ✅"})



class AgentVerificationUploadView(generics.CreateAPIView):
    serializer_class = AgentVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != User.Role.AGENT:
            raise serializers.ValidationError("Only agents can submit verification documents.")

        if AgentVerification.objects.filter(agent=user).exists():
            raise serializers.ValidationError("You’ve already submitted your documents.")

        serializer.save(agent=user)

class AgentVerificationApprovalView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        unverified = AgentVerification.objects.filter(is_verified=False)
        serializer = AgentVerificationSerializer(unverified, many=True)
        return Response(serializer.data)

    def post(self, request, verification_id):
        try:
            verification = AgentVerification.objects.get(id=verification_id)
        except AgentVerification.DoesNotExist:
            return Response({"error": "Verification not found"}, status=404)

        # Approve agent
        verification.is_verified = True
        verification.save()

        agent = verification.agent
        agent.is_verified = True
        agent.save()

        return Response({"message": f"{agent.full_name} is now a verified agent ✅"})

class RejectAgentVerificationView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, verification_id):
        reason = request.data.get("reason")
        if not reason:
            return Response({"error": "A rejection reason is required"}, status=400)

        try:
            verification = AgentVerification.objects.get(id=verification_id)
        except AgentVerification.DoesNotExist:
            return Response({"error": "Verification not found"}, status=404)

        verification.rejection_reason = reason
        verification.was_rejected = True
        verification.save()

        agent = verification.agent
        agent.is_verified = False
        agent.save()

        return Response({
            "message": f"{agent.full_name}'s verification was rejected ❌",
            "reason": reason
        })

class RequestWithdrawalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, commission_id):
        user = request.user

        try:
            commission = Commission.objects.get(id=commission_id, agent=user)
        except Commission.DoesNotExist:
            return Response({"error": "Commission not found or not yours"}, status=404)

        if commission.is_withdrawn:
            return Response({"error": "This commission has already been withdrawn"}, status=400)

        if commission.withdrawal_requested:
            return Response({"error": "Withdrawal already requested"}, status=400)

        commission.withdrawal_requested = True
        commission.save()

        return Response({"message": "Withdrawal request submitted ✅"})


class ApproveWithdrawalView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        requests = Commission.objects.filter(withdrawal_requested=True, is_withdrawn=False)
        serializer = CommissionSerializer(requests, many=True)
        return Response(serializer.data)

    def post(self, request, commission_id):
        try:
            commission = Commission.objects.get(id=commission_id, withdrawal_requested=True, is_withdrawn=False)
        except Commission.DoesNotExist:
            return Response({"error": "No such pending withdrawal"}, status=404)

        commission.is_withdrawn = True
        commission.withdrawal_requested = False
        commission.save()

        return Response({
            "message": f"Withdrawal of ₦{commission.amount} approved for {commission.agent.full_name} ✅"
        })

class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role
        data = {
            "full_name": user.full_name,
            "role": role,
        }

        if role == User.Role.CUSTOMER:
            data["bookings"] = Booking.objects.filter(user=user).count()
            # add favorite count if implemented

        elif role == User.Role.AGENT:
            data["total_properties"] = Property.objects.filter(agent=user).count()
            commissions = Commission.objects.filter(agent=user)
            data["total_commission"] = sum(c.amount for c in commissions)
            data["pending_withdrawals"] = commissions.filter(withdrawal_requested=True, is_withdrawn=False).count()
            avg = Review.objects.filter(agent=user, review_type='agent', is_approved=True).aggregate(Avg('rating'))[
                'rating__avg']
            data["average_rating"] = round(avg, 1) if avg else None

        elif role == User.Role.INVESTOR:
            investments = Investment.objects.filter(investor=user)
            data["total_investments"] = investments.count()
            data["remaining_balance_total"] = sum(i.remaining_balance for i in investments)
            data["shortlet_credit"] = user.shortlet_credit
            data["total_invested"] = sum(i.total_price for i in investments)
            data["total_earnings"] = sum(roi.amount for i in investments for roi in i.rois.all())
            data["roi_logs"] = InvestmentROISerializer(
                InvestmentROI.objects.filter(investment__investor=user), many=True
            ).data

        elif role == User.Role.ADMIN:
            data["unapproved_properties"] = Property.objects.filter(is_approved=False).count()
            data["pending_verifications"] = AgentVerification.objects.filter(is_verified=False, was_rejected=False).count()
            data["pending_withdrawals"] = Commission.objects.filter(withdrawal_requested=True, is_withdrawn=False).count()
            data["unapproved_reviews"] = Review.objects.filter(is_approved=False).count()

        if user.membership_tier:
            data["membership_tier"] = user.membership_tier
            data["membership_expires_at"] = user.membership_expires_at
            data["membership_active"] = has_active_membership(user)
        return Response(data)

class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        property = serializer.validated_data['property']

        if not property.is_approved:
            raise serializers.ValidationError("You cannot favorite unapproved properties.")

        # Prevent Customers from favoriting investment properties
        if user.role == User.Role.CUSTOMER and property.property_type == 'investment':
            raise serializers.ValidationError("Customers cannot favorite investment properties.")

        serializer.save(user=user)

class RefundLogView(generics.ListCreateAPIView):
    serializer_class = RefundLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == User.Role.ADMIN:
            return RefundLog.objects.all()
        return RefundLog.objects.filter(user=user)

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_staff and user.role != User.Role.ADMIN:
            raise permissions.PermissionDenied("Only admins can issue refunds")
        serializer.save(user=self.request.data.get("user"))


class CancelBookingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        user = request.user

        try:
            booking = Booking.objects.get(id=booking_id, user=user)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=404)

        if booking.is_cancelled:
            return Response({"error": "This booking is already cancelled."}, status=400)

        if booking.start_date <= timezone.now().date():
            return Response({"error": "You cannot cancel a booking that has already started."}, status=400)

        # Cancel the booking
        booking.is_cancelled = True
        booking.save()

        # Log refund if it was paid
        if booking.is_paid:
            RefundLog.objects.create(
                user=user,
                amount=booking.total_price,
                reason=f"Cancelled short-let booking for '{booking.property.title}'"
            )

        return Response({"message": "Booking cancelled and refund logged ✅"})

class AdminCancelBookingView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=404)

        if booking.is_cancelled:
            return Response({"error": "Booking is already cancelled."}, status=400)

        booking.is_cancelled = True
        booking.save()

        if booking.is_paid:
            RefundLog.objects.create(
                user=booking.user,
                amount=booking.total_price,
                reason=f"Admin cancelled booking for '{booking.property.title}'"
            )

        return Response({"message": f"Booking for {booking.user.email} has been cancelled by admin."})


class SwitchUserRoleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        new_role = request.data.get('role')
        valid_roles = [User.Role.CUSTOMER, User.Role.AGENT, User.Role.INVESTOR]

        if new_role not in valid_roles:
            return Response({"error": "Invalid role."}, status=400)

        user = request.user
        old_role = user.role

        if old_role == new_role:
            return Response({"message": f"You're already a {new_role.lower()}."})

        # Save old verification status
        if old_role == User.Role.AGENT and user.is_verified:
            user.was_verified_as_agent = True
        if old_role == User.Role.INVESTOR and user.is_verified:
            user.was_verified_as_investor = True

        # Role switch happens
        user.role = new_role
        user.is_verified = False  # Require re-verification on return
        user.save()

        return Response({
            "message": f"Your role has been changed to {new_role}. Please re-verify if required.",
            "re_verification_required": new_role in [User.Role.AGENT, User.Role.INVESTOR]
        })

class AssignAdminRoleView(APIView):
    permission_classes = [permissions.IsAdminUser]  # ✅ Super-admin only

    def post(self, request, user_id):
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        if target_user.role == User.Role.ADMIN and target_user.is_staff:
            return Response({"message": "User is already an admin."})

        target_user.role = User.Role.ADMIN
        target_user.is_verified = True
        target_user.is_staff = True  # ✅ Gives them access to Django admin & full privileges
        target_user.save()

        return Response({"message": f"{target_user.full_name} has been promoted to Admin ✅"})

class InitiatePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        amount = request.data.get("amount")
        tx_ref = f"TobiTx-{uuid.uuid4()}"
        redirect_url = request.data.get("redirect_url")  # Provided by frontend

        headers = {
            "Authorization": f"Bearer {FLW_SECRET}",
            "Content-Type": "application/json"
        }

        data = {
            "tx_ref": tx_ref,
            "amount": amount,
            "currency": "NGN",
            "redirect_url": redirect_url,
            "customer": {
                "email": user.email,
                "name": user.full_name
            },
            "customizations": {
                "title": "T.O.B.I Payment",
                "description": "Property investment or short-let booking"
            }
        }

        flutterwave_url = "https://api.flutterwave.com/v3/payments"
        response = requests.post(flutterwave_url, json=data, headers=headers)
        result = response.json()

        if response.status_code == 200 and result.get("status") == "success":
            return Response({
                "payment_link": result["data"]["link"],
                "tx_ref": tx_ref
            })
        else:
            return Response({"error": "Failed to initiate payment"}, status=400)

class VerifyFlutterwavePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tx_id = request.query_params.get("transaction_id")
        if not tx_id:
            return Response({"error": "No transaction ID provided"}, status=400)

        url = f"https://api.flutterwave.com/v3/transactions/{tx_id}/verify"
        headers = {
            "Authorization": f"Bearer {FLW_SECRET}"
        }

        response = requests.get(url, headers=headers)
        result = response.json()

        if result["status"] == "success" and result["data"]["status"] == "successful":
            # TODO: Update booking/investment with tx_ref match
            return Response({"message": "Payment verified ✅", "data": result["data"]})
        else:
            return Response({"error": "Payment verification failed"}, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class FlutterwaveWebhookView(APIView):
    permission_classes = [AllowAny]  # Webhooks are unauthenticated (but secret-key validated)

    def post(self, request):
        data = request.data

        if data.get('event') != 'charge.completed':
            return Response({"message": "Ignored non-payment event"}, status=200)

        payment = data.get('data', {})
        tx_ref = payment.get('tx_ref')
        status = payment.get('status')

        if status != 'successful':
            return Response({"message": "Payment not successful"}, status=200)

        # Match to Booking by tx_ref
        try:
            booking = Booking.objects.get(tx_ref=tx_ref)
            if not booking.is_paid:
                booking.is_paid = True
                booking.save()
                return Response({"message": "Booking marked as paid ✅"})
        except Booking.DoesNotExist:
            pass

        # Match to Investment by tx_ref
        try:
            investment = Investment.objects.get(tx_ref=tx_ref)
            if investment.amount_paid < investment.total_price:
                investment.amount_paid = investment.total_price
                investment.remaining_balance = 0
                investment.status = "completed"
                investment.investor.membership_tier = "Platinum"
                investment.investor.membership_expires_at = timezone.now() + timedelta(days=365)
                investment.investor.is_verified = True
                investment.investor.save()
                investment.save()
                return Response({"message": "Investment marked as fully paid ✅"})
        except Investment.DoesNotExist:
            pass

        return Response({"message": "No matching record found"}, status=404)


class InvestmentROIView(generics.ListCreateAPIView):
    serializer_class = InvestmentROISerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return InvestmentROI.objects.all()

    def perform_create(self, serializer):
        serializer.save()


class AdminDashboardView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        data = {
            "pending_properties": Property.objects.filter(is_approved=False).count(),
            "pending_reviews": Review.objects.filter(is_approved=False).count(),
            "pending_verifications": AgentVerification.objects.filter(is_verified=False, was_rejected=False).count(),
            "pending_withdrawals": Commission.objects.filter(withdrawal_requested=True, is_withdrawn=False).count(),
            "recent_bookings": BookingSerializer(Booking.objects.order_by('-created_at')[:5], many=True).data,
            "user_counts": {
                "agents": User.objects.filter(role=User.Role.AGENT).count(),
                "customers": User.objects.filter(role=User.Role.CUSTOMER).count(),
                "investors": User.objects.filter(role=User.Role.INVESTOR).count(),
                "admins": User.objects.filter(role=User.Role.ADMIN).count()
            }
        }
        return Response(data)
