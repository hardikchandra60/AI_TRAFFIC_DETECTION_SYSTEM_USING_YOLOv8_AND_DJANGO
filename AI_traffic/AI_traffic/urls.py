from django.contrib import admin
from django.urls import path
from detection import views 
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # API
    path('api/record_violation/', views.record_violation, name='record_violation'),
    path('api/find_owner_by_plate/', views.find_owner_by_plate, name='find_owner_by_plate'),

    # Camera
    path('live_feed/', views.live_feed, name='live_feed'),

    # Admin
    path('adminhome/', views.admin_home, name='adminhome'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),

    # Data
    path('violations/', views.violation_list, name='violation_list'),
    path('vehicles/', views.vehicle_list, name='vehicle_list'),
    path('add-vehicle/', views.add_vehicle, name='add_vehicle'),
    path('delete-violation/<int:vid>/', views.delete_violation, name='delete_violation'),

    path('reports/', views.reports, name='reports'),
    path("test_notification/", views.test_notification, name="test_notification"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)