from django.urls import re_path

from . import views

# "/?" makes every URL work with or without the trailing slash.
urlpatterns = [
    re_path(r'^auth/register/?$', views.RegisterView.as_view(), name='register'),
    re_path(r'^auth/login/?$', views.LoginView.as_view(), name='login'),
    re_path(r'^alerts/?$', views.AlertListCreateView.as_view(), name='alert-list'),
    re_path(r'^alerts/(?P<pk>\d+)/?$', views.AlertDetailView.as_view(), name='alert-detail'),
    re_path(r'^flights/price/?$', views.get_flight_price, name='flight-price'),
    re_path(r'^admin/summary/?$', views.AdminSummaryView.as_view(), name='admin-summary'),
]
