from django.urls import path
from . import views

urlpatterns = [
    path("sessions/", views.session_list),
    path("messages/", views.message_list),
    path("sessions/end/", views.session_end),
]
