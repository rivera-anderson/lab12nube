from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'matches', views.MatchViewSet, basename='match')
router.register(r'predictions', views.PredictionViewSet, basename='prediction')
router.register(r'rooms', views.RoomViewSet, basename='room')

urlpatterns = [
    # Web Views
    path('', views.index_view, name='index'),
    path('rooms/', views.rooms_view, name='rooms'),
    path('rooms/create/', views.create_room_view, name='create_room'),
    path('rooms/join/', views.join_room_view, name='join_room'),
    path('rooms/<int:room_id>/', views.room_detail_view, name='room_detail'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('monitor/', views.monitor_view, name='monitor'),
    path('predict/<int:match_id>/', views.submit_prediction_view, name='submit_prediction'),
    path('simulate-score/<int:match_id>/', views.simulate_match_score_view, name='simulate_score'),
    path('ai-analysis/<int:match_id>/', views.ai_match_analysis_view, name='ai_analysis'),
    
    # Auth
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # REST API
    path('api/', include(router.urls)),
    path('api/health/', views.SystemHealthAPIView.as_view(), name='api_health'),
    path('api/global-leaderboard/', views.GlobalLeaderboardAPIView.as_view(), name='api_global_leaderboard'),
    path('api/ai-stats/<int:match_id>/', views.AIMatchAnalysisAPIView.as_view(), name='api_ai_stats'),
]
