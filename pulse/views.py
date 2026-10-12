import random

from django.contrib.auth import authenticate
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import NotificationLog, PriceAlert, UserProfile
from .permissions import IsAdminUser
from .serializers import LoginSerializer, PriceAlertSerializer, RegisterSerializer


def access_token_for(user):
    return str(RefreshToken.for_user(user).access_token)


# ------------------------------------------------------------------ Auth
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # duplicate username -> 400
        user = serializer.save()  # post_save signal creates the UserProfile (role=user)
        return Response(
            {
                'username': user.username,
                'access': access_token_for(user),
                'role': user.profile.role,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({
            'username': user.username,
            'access': access_token_for(user),
            'role': user.profile.role,
        })


# ---------------------------------------------------------------- Alerts
class AlertListCreateView(APIView):
    """GET /api/alerts/  and  POST /api/alerts/  (JWT required)."""

    def get_queryset(self):
        # A user must only ever see their own alerts.
        return PriceAlert.objects.filter(user=self.request.user)

    def get(self, request):
        serializer = PriceAlertSerializer(self.get_queryset(), many=True)
        return Response(serializer.data)  # empty list (not 404) when there are no alerts

    def post(self, request):
        serializer = PriceAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        alert = serializer.save(user=request.user)  # user from the token, never the body
        return Response(PriceAlertSerializer(alert).data, status=status.HTTP_201_CREATED)


class AlertDetailView(APIView):
    """DELETE /api/alerts/<id>/ -> soft delete (status=inactive)."""

    def delete(self, request, pk):
        alert = get_object_or_404(PriceAlert, id=pk)
        if alert.user != request.user:
            # 404, not 403: never reveal that someone else's alert exists.
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        alert.status = PriceAlert.Status.INACTIVE
        alert.save(update_fields=['status'])
        return Response({'status': 'inactive'}, status=status.HTTP_200_OK)


# ------------------------------------------------------- Mock price feed
MOCK_PRICES = {
    'DEL-BOM': (3000, 7000),
    'BLR-HYD': (1500, 4000),
    'DEL-BLR': (4000, 9000),
    'BOM-GOA': (2000, 5000),
}


def get_flight_price(request):
    """Plain Django view, public. Called by the Celery task with requests.get()."""
    route = request.GET.get('route', '')
    price_range = MOCK_PRICES.get(route)
    if not price_range:
        return JsonResponse({'error': 'Route not found'}, status=404)
    price = random.randint(*price_range)
    return JsonResponse({'route': route, 'price': price})


# --------------------------------------------------------- Admin summary
class AdminSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        alert_counts = PriceAlert.objects.aggregate(
            total_alerts=Count('id'),
            active_alerts=Count('id', filter=Q(status=PriceAlert.Status.ACTIVE)),
            triggered_alerts=Count('id', filter=Q(status=PriceAlert.Status.TRIGGERED)),
        )
        total_notifications = NotificationLog.objects.aggregate(total=Count('id'))['total']

        top = (
            PriceAlert.objects.values('origin', 'destination')
            .annotate(alert_count=Count('id'))
            .order_by('-alert_count', 'origin', 'destination')[:5]
        )
        top_routes = [
            {'route': f"{row['origin']}-{row['destination']}", 'alert_count': row['alert_count']}
            for row in top
        ]
        return Response({
            **alert_counts,
            'total_notifications': total_notifications,
            'top_routes': top_routes,
        })
