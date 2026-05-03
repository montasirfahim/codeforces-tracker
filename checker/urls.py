from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/upload/', views.upload_csv, name='upload_csv'),
    path('api/lists/', views.get_student_lists, name='get_student_lists'),
    path('api/clear/', views.clear_lists, name='clear_lists'),
    path('api/students/<int:list_id>/', views.get_students, name='get_students'),
    path('api/check/', views.check_solves, name='check_solves'),
]
