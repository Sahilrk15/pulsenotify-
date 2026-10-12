import requests
from celery import shared_task
from django.conf import settings

from .models import NotificationLog, PriceAlert


@shared_task
def check_prices():
    """Runs every 60 s (Celery Beat). Fetches the price per active route and fires notifications."""
    active_alerts = PriceAlert.objects.filter(status=PriceAlert.Status.ACTIVE)
    # .order_by() clears the model's default ordering, otherwise DISTINCT also sees created_at
    routes = active_alerts.order_by().values_list('origin', 'destination').distinct()

    for origin, destination in routes:
        route = f'{origin}-{destination}'

        # backend-to-backend call to our own mock price endpoint
        try:
            response = requests.get(settings.PRICE_FEED_URL, params={'route': route}, timeout=5)
        except requests.RequestException:
            continue  # feed unreachable: try again on the next beat
        if response.status_code != 200:
            continue
        current_price = response.json().get('price')

        route_alerts = active_alerts.filter(origin=origin, destination=destination)
        for alert in route_alerts:
            if current_price <= float(alert.threshold_price):
                # .delay() -> async: check_prices does not wait for the notification
                send_notification.delay(alert.id, current_price)


@shared_task
def send_notification(alert_id, triggered_price):
    alert = PriceAlert.objects.get(id=alert_id)
    if alert.status != PriceAlert.Status.ACTIVE:
        return  # already triggered or deactivated: never notify twice
    message = (
        f'Price alert triggered! {alert.origin}-{alert.destination} '
        f'is now ₹{triggered_price} - below your threshold of '
        f'₹{alert.threshold_price}'
    )
    NotificationLog.objects.create(
        alert=alert,
        triggered_price=triggered_price,
        message=message,
    )
    # Mark alert as triggered so it doesn't fire again
    alert.status = PriceAlert.Status.TRIGGERED
    alert.save(update_fields=['status'])
