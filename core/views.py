from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Room, RoomMember, Match, Prediction, UserProfile
from .serializers import MatchSerializer, PredictionSerializer, RoomSerializer, UserProfileSerializer
from .scoring import calculate_match_points, evaluate_user_predictions, recalculate_all_scores
from .ai_engine import generate_match_ai_analysis

import socket
import os
import json


# ============================================================================
# VISTAS WEB (FRONTEND)
# ============================================================================

def index_view(request):
    """Vista principal: Partidos, predicciones del usuario y resumen de tabla."""
    matches = Match.objects.all().order_by('match_date')
    user_predictions = {}
    user_profile = None

    if request.user.is_authenticated:
        preds = Prediction.objects.filter(user=request.user).select_related('match')
        user_predictions = {p.match_id: p for p in preds}
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    top_leaderboard = UserProfile.objects.select_related('user').order_by('-total_points', '-exact_hits')[:10]

    # Contadores
    scheduled_matches = matches.filter(status='SCHEDULED')
    finished_matches = matches.filter(status='FINISHED')

    context = {
        'matches': matches,
        'scheduled_matches': scheduled_matches,
        'finished_matches': finished_matches,
        'user_predictions': user_predictions,
        'user_profile': user_profile,
        'top_leaderboard': top_leaderboard,
    }
    return render(request, 'index.html', context)


@login_required
def rooms_view(request):
    """Gestión de Salas / Grupos: Mis salas, crear sala, unirse por código."""
    user = request.user
    user_memberships = RoomMember.objects.filter(user=user).select_related('room')
    user_rooms = [m.room for m in user_memberships]

    context = {
        'user_rooms': user_rooms,
    }
    return render(request, 'rooms.html', context)


@login_required
def room_detail_view(request, room_id):
    """Detalle de una sala específica: Código de invitación, participantes y ranking de la sala."""
    room = get_object_or_404(Room, id=room_id)
    
    # Verificar si el usuario ya es miembro; si no, unirlo automáticamente
    membership, _ = RoomMember.objects.get_or_create(room=room, user=request.user)

    # Participantes de la sala con sus perfiles de puntuación
    members = RoomMember.objects.filter(room=room).select_related('user', 'user__profile')
    
    # Ordenar participantes por puntos
    leaderboard = []
    for m in members:
        prof, _ = UserProfile.objects.get_or_create(user=m.user)
        leaderboard.append({
            'user': m.user,
            'profile': prof,
            'joined_at': m.joined_at,
        })
    leaderboard.sort(key=lambda x: (x['profile'].total_points, x['profile'].exact_hits), reverse=True)

    # Agregar posición
    for idx, item in enumerate(leaderboard, start=1):
        item['rank'] = idx

    context = {
        'room': room,
        'leaderboard': leaderboard,
        'member_count': len(leaderboard),
    }
    return render(request, 'room_detail.html', context)


@login_required
@require_POST
def create_room_view(request):
    """Crea una nueva sala con código de invitación único."""
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()

    if not name:
        messages.error(request, "El nombre de la sala es obligatorio.")
        return redirect('rooms')

    room = Room.objects.create(
        name=name,
        description=description,
        created_by=request.user
    )
    # El creador se une automáticamente
    RoomMember.objects.create(room=room, user=request.user)
    messages.success(request, f"¡Sala '{room.name}' creada con éxito! Código: {room.code}")
    return redirect('room_detail', room_id=room.id)


@login_required
@require_POST
def join_room_view(request):
    """Unirse a una sala mediante código de invitación."""
    code = request.POST.get('code', '').strip().upper()
    try:
        room = Room.objects.get(code=code)
    except Room.DoesNotExist:
        messages.error(request, f"No existe ninguna sala con el código '{code}'.")
        return redirect('rooms')

    membership, created = RoomMember.objects.get_or_create(room=room, user=request.user)
    if created:
        messages.success(request, f"¡Te has unido exitosamente a la sala '{room.name}'!")
    else:
        messages.info(request, f"Ya eres miembro de la sala '{room.name}'.")

    return redirect('room_detail', room_id=room.id)


def leaderboard_view(request):
    """Tabla de posiciones global de todos los participantes."""
    leaderboard = UserProfile.objects.select_related('user').order_by('-total_points', '-exact_hits', '-winner_hits')
    context = {
        'leaderboard': leaderboard,
    }
    return render(request, 'leaderboard.html', context)


def monitor_view(request):
    """Panel visual en tiempo real para demostración de pruebas de estrés y balanceo de carga en video."""
    return render(request, 'monitor.html')


@login_required
@require_POST
def submit_prediction_view(request, match_id):
    """Registrar o actualizar predicción de un partido."""
    match = get_object_or_404(Match, id=match_id)
    if match.status == 'FINISHED':
        messages.error(request, "No se pueden realizar predicciones para partidos finalizados.")
        return redirect('index')

    try:
        home_pred = int(request.POST.get('home_score_pred'))
        away_pred = int(request.POST.get('away_score_pred'))
    except (TypeError, ValueError):
        messages.error(request, "Por favor ingrese marcadores válidos (números enteros).")
        return redirect('index')

    pred, created = Prediction.objects.update_or_create(
        user=request.user,
        match=match,
        defaults={
            'home_score_pred': home_pred,
            'away_score_pred': away_pred,
        }
    )
    action_text = "registrada" if created else "actualizada"
    messages.success(request, f"Predicción para {match.team_home} vs {match.team_away} {action_text} con éxito ({home_pred} - {away_pred}).")
    return redirect('index')


@login_required
@require_POST
def simulate_match_score_view(request, match_id):
    """
    Herramienta de Demostración/Admin:
    Permite establecer o simular el marcador real de un partido y activa inmediatamente
    el recálculo global de las 5 reglas de puntuación para ver los puntos en vivo.
    """
    match = get_object_or_404(Match, id=match_id)
    try:
        home_score = int(request.POST.get('home_score', 0))
        away_score = int(request.POST.get('away_score', 0))
    except (TypeError, ValueError):
        messages.error(request, "Marcadores inválidos.")
        return redirect('index')

    match.home_score = home_score
    match.away_score = away_score
    match.status = 'FINISHED'
    match.save()

    # Recalcular puntos con las 5 reglas
    recalculate_all_scores()

    messages.success(request, f"Resultado de {match.team_home} vs {match.team_away} guardado como {home_score}-{away_score}. ¡Puntuaciones recalculadas según las 5 reglas!")
    return redirect('index')


def ai_match_analysis_view(request, match_id):
    """Retorna análisis predictivo con IA en formato JSON para el frontend."""
    match = get_object_or_404(Match, id=match_id)
    data = generate_match_ai_analysis(match.team_home, match.team_away)
    data['match_id'] = match.id
    data['match_date'] = match.match_date.isoformat()
    data['stadium'] = match.stadium
    return JsonResponse(data)


# Autenticación Web
def register_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, "Usuario y contraseña requeridos.")
            return render(request, 'register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "El nombre de usuario ya está registrado.")
            return render(request, 'register.html')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name
        )
        UserProfile.objects.create(user=user)
        login(request, user)
        messages.success(request, f"¡Bienvenido a la Polla Mundialista, {username}!")
        return redirect('index')

    return render(request, 'register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Sesión iniciada como {username}.")
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)
        else:
            messages.error(request, "Credenciales incorrectas.")

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    messages.info(request, "Has cerrado sesión.")
    return redirect('login')


# ============================================================================
# VISTAS REST API (PARA CLIENTES EXTERNOS / PRUEBAS DE ESTRÉS)
# ============================================================================

class SystemHealthAPIView(APIView):
    """
    Endpoint de salud para el balanceador de carga (Nginx / Docker).
    Retorna métricas del nodo, PID y hora local para verificar Round-Robin.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'status': 'healthy',
            'server_id': getattr(request, 'server_id', socket.gethostname()),
            'process_pid': getattr(request, 'process_pid', os.getpid()),
            'timestamp': timezone.now().isoformat(),
            'total_users': User.objects.count(),
            'total_matches': Match.objects.count(),
            'total_predictions': Prediction.objects.count(),
        })


class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all().order_by('match_date')
    serializer_class = MatchSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def set_score(self, request, pk=None):
        """Actualiza el marcador del partido y recalcula puntos."""
        match = self.get_object()
        home = request.data.get('home_score')
        away = request.data.get('away_score')

        if home is None or away is None:
            return Response({'error': 'home_score and away_score are required'}, status=status.HTTP_400_BAD_REQUEST)

        match.home_score = int(home)
        match.away_score = int(away)
        match.status = 'FINISHED'
        match.save()

        # Recalcular puntuaciones
        results = recalculate_all_scores()
        return Response({
            'message': 'Score updated and predictions recalculated',
            'match': MatchSerializer(match).data,
            'users_updated': len(results)
        })


class PredictionViewSet(viewsets.ModelViewSet):
    queryset = Prediction.objects.all()
    serializer_class = PredictionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.request.query_params.get('user_id')
        if user_id:
            return self.queryset.filter(user_id=user_id)
        if self.request.user.is_authenticated:
            return self.queryset.filter(user=self.request.user)
        return self.queryset

    def create(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None
        user_id = request.data.get('user_id')
        if not user and user_id:
            user = get_object_or_404(User, id=user_id)
        
        if not user:
            return Response({'error': 'User must be authenticated or user_id provided'}, status=status.HTTP_400_BAD_REQUEST)

        match_id = request.data.get('match') or request.data.get('match_id')
        match = get_object_or_404(Match, id=match_id)

        home_pred = int(request.data.get('home_score_pred'))
        away_pred = int(request.data.get('away_score_pred'))

        pred, created = Prediction.objects.update_or_create(
            user=user,
            match=match,
            defaults={
                'home_score_pred': home_pred,
                'away_score_pred': away_pred
            }
        )
        return Response(PredictionSerializer(pred).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def join_by_code(self, request):
        code = request.data.get('code', '').strip().upper()
        user_id = request.data.get('user_id')
        user = request.user if request.user.is_authenticated else None
        if not user and user_id:
            user = get_object_or_404(User, id=user_id)

        if not user:
            return Response({'error': 'User authentication or user_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            room = Room.objects.get(code=code)
        except Room.DoesNotExist:
            return Response({'error': f"Sala con código '{code}' no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        membership, created = RoomMember.objects.get_or_create(room=room, user=user)
        return Response({
            'message': 'Joined successfully',
            'room': RoomSerializer(room).data,
            'created': created
        })

    @action(detail=True, methods=['get'])
    def leaderboard(self, request, pk=None):
        room = self.get_object()
        members = RoomMember.objects.filter(room=room).select_related('user', 'user__profile')
        ranking = []
        for m in members:
            prof, _ = UserProfile.objects.get_or_create(user=m.user)
            ranking.append(UserProfileSerializer(prof).data)
        ranking.sort(key=lambda x: (x['total_points'], x['exact_hits']), reverse=True)
        return Response({
            'room': room.name,
            'code': room.code,
            'leaderboard': ranking
        })


class GlobalLeaderboardAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        profiles = UserProfile.objects.select_related('user').order_by('-total_points', '-exact_hits')
        return Response(UserProfileSerializer(profiles, many=True).data)


class AIMatchAnalysisAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, match_id):
        match = get_object_or_404(Match, id=match_id)
        data = generate_match_ai_analysis(match.team_home, match.team_away)
        data['match_id'] = match.id
        return Response(data)
