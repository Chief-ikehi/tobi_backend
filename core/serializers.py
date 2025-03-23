# core/serializers.py

from django.db.models import Avg
from rest_framework import serializers

from .models import (
    User, Property, Booking, Commission, Gift,
    Investment, Review, AgentVerification, Favorite, RefundLog, InvestmentROI
)

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'full_name', 'password', 'role')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        role = validated_data.get('role', User.Role.CUSTOMER)

        # Security: Prevent users from registering as admin unless current user is admin
        request = self.context.get('request')
        if role == User.Role.ADMIN and (not request or not request.user.is_staff):
            raise serializers.ValidationError("You are not allowed to create admin users.")

        user = User.objects.create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=validated_data['password'],
            role=role
        )
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role')

    def get_average_rating(self, obj):
        from .models import Review
        avg = Review.objects.filter(
            agent=obj,
            review_type='agent',
            is_approved=True
        ).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else None


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = '__all__'
        read_only_fields = ['agent', 'is_approved', 'created_at']

    def get_average_rating(self, obj):
        from .models import Review
        avg = Review.objects.filter(
            property=obj,
            review_type='property',
            is_approved=True
        ).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else None

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['user', 'total_price', 'is_paid', 'created_at']


class CommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commission
        fields = '__all__'

class GiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gift
        fields = '__all__'
        read_only_fields = ['sender', 'recipient_user', 'status', 'created_at']


class InvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investment
        fields = '__all__'
        read_only_fields = ['investor', 'amount_paid', 'remaining_balance', 'status', 'started_at']

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['user', 'is_approved', 'created_at']


class AgentVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentVerification
        fields = '__all__'
        read_only_fields = ['agent', 'is_verified', 'submitted_at']


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = '__all__'
        read_only_fields = ['user', 'created_at']


class RefundLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundLog
        fields = '__all__'
        read_only_fields = ['user', 'created_at']


class InvestmentROISerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentROI
        fields = '__all__'
        read_only_fields = ['date_paid']