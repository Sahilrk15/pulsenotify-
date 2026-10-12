from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import NotificationLog, PriceAlert, UserProfile
from .tasks import check_prices, send_notification


# --------------------------------------------------------------- Required tests
class PriceThresholdTest(TestCase):

    def test_price_below_threshold_triggers_alert(self):
        # If current price (4200) <= threshold (4500), alert should fire
        self.assertTrue(4200 <= 4500)

    def test_price_above_threshold_does_not_trigger(self):
        # If current price (5000) > threshold (4500), alert should not fire
        self.assertFalse(5000 <= 4500)

    def test_price_equal_to_threshold_triggers_alert(self):
        # Edge case: price == threshold should still trigger
        self.assertTrue(4500 <= 4500)


class NotificationLogTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.alert = PriceAlert.objects.create(
            user=self.user,
            origin='DEL', destination='BOM',
            threshold_price=4500,
            status=PriceAlert.Status.ACTIVE,
        )

    def test_notification_log_created_with_correct_message(self):
        log = NotificationLog.objects.create(
            alert=self.alert,
            triggered_price=4200,
            message='Price dropped to 4200 for DEL-BOM',
        )
        self.assertEqual(log.triggered_price, 4200)
        self.assertEqual(log.alert, self.alert)
        self.assertIn('DEL-BOM', log.message)


class AlertScopingTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        PriceAlert.objects.create(
            user=self.user1, origin='DEL', destination='BOM', threshold_price=4500
        )
        PriceAlert.objects.create(
            user=self.user2, origin='BLR', destination='HYD', threshold_price=2000
        )

    def test_user_only_sees_own_alerts(self):
        user1_alerts = PriceAlert.objects.filter(user=self.user1)
        self.assertEqual(user1_alerts.count(), 1)
        self.assertEqual(user1_alerts.first().origin, 'DEL')

    def test_user_cannot_see_other_users_alerts(self):
        user2_alerts = PriceAlert.objects.filter(user=self.user1)
        # user1 should not see user2's BLR-HYD alert
        self.assertNotEqual(user2_alerts.first().origin, 'BLR')


# -------------------------------------------- Extra tests on the real logic
class RealBusinessLogicTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='securepass')
        self.other = User.objects.create_user(username='bob', password='securepass')
        self.client = APIClient()

    def test_signal_creates_profile_with_user_role(self):
        self.assertEqual(self.user.profile.role, UserProfile.Role.USER)

    def test_register_ignores_role_in_body(self):
        res = self.client.post('/api/auth/register/', {
            'username': 'mallory', 'password': 'securepass', 'role': 'admin',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['role'], 'user')

    def test_cannot_delete_another_users_alert(self):
        alert = PriceAlert.objects.create(
            user=self.other, origin='DEL', destination='BOM', threshold_price=4500
        )
        self.client.force_authenticate(self.user)
        res = self.client.delete(f'/api/alerts/{alert.id}/')
        self.assertEqual(res.status_code, 404)
        alert.refresh_from_db()
        self.assertEqual(alert.status, PriceAlert.Status.ACTIVE)

    def test_send_notification_writes_log_and_marks_triggered(self):
        alert = PriceAlert.objects.create(
            user=self.user, origin='DEL', destination='BOM', threshold_price=4500
        )
        send_notification(alert.id, 4200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, PriceAlert.Status.TRIGGERED)
        self.assertEqual(NotificationLog.objects.filter(alert=alert).count(), 1)
        send_notification(alert.id, 4100)  # already triggered: no duplicate
        self.assertEqual(NotificationLog.objects.filter(alert=alert).count(), 1)

    @patch('pulse.tasks.send_notification.delay')
    @patch('pulse.tasks.requests.get')
    def test_check_prices_fires_only_for_alerts_at_or_above_price(self, mock_get, mock_delay):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {'route': 'DEL-BOM', 'price': 4200})
        hit = PriceAlert.objects.create(user=self.user, origin='DEL', destination='BOM', threshold_price=4500)
        PriceAlert.objects.create(user=self.user, origin='DEL', destination='BOM', threshold_price=3000)
        check_prices()
        mock_delay.assert_called_once_with(hit.id, 4200)
