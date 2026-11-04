from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import secrets
import string

def generate_room_code():
    chars = string.ascii_uppercase + string.digits
    # Generate format: POL-XXXXX (e.g. POL-7F92K)
    suffix = ''.join(secrets.choice(chars) for _ in range(5))
    return f"WC26-{suffix}"

class Room(models.Model):
    """
    Sala o Grupo de amigos para competir en las predicciones del Mundial.
    Permite invitar mediante un código único de sala.
    """
    name = models.CharField(max_length=100, verbose_name="Nombre de la Sala")
    description = models.TextField(blank=True, verbose_name="Descripción")
    code = models.CharField(max_length=16, unique=True, default=generate_room_code, db_index=True, verbose_name="Código de Invitación")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_rooms", verbose_name="Creado por")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Sala"
        verbose_name_plural = "Salas"

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def member_count(self):
        return self.memberships.count()


class RoomMember(models.Model):
    """
    Membresía de un participante dentro de una sala.
    """
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="room_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('room', 'user')
        ordering = ['joined_at']
        verbose_name = "Miembro de Sala"
        verbose_name_plural = "Miembros de Sala"

    def __str__(self):
        return f"{self.user.username} en {self.room.name}"


class Match(models.Model):
    """
    Partido del Mundial de Fútbol.
    """
    STATUS_CHOICES = [
        ('SCHEDULED', 'Programado'),
        ('LIVE', 'En Vivo'),
        ('FINISHED', 'Finalizado'),
    ]

    team_home = models.CharField(max_length=60, verbose_name="Equipo Local")
    team_away = models.CharField(max_length=60, verbose_name="Equipo Visitante")
    home_flag = models.CharField(max_length=10, default="⚽", verbose_name="Bandera Local")
    away_flag = models.CharField(max_length=10, default="⚽", verbose_name="Bandera Visitante")
    stage = models.CharField(max_length=50, default="Fase de Grupos", verbose_name="Etapa")
    group_name = models.CharField(max_length=20, default="Grupo A", verbose_name="Grupo")
    stadium = models.CharField(max_length=120, default="Estadio Azteca, CDMX", verbose_name="Estadio")
    match_date = models.DateTimeField(verbose_name="Fecha y Hora del Partido")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='SCHEDULED', db_index=True)
    home_score = models.IntegerField(null=True, blank=True, verbose_name="Goles Local")
    away_score = models.IntegerField(null=True, blank=True, verbose_name="Goles Visitante")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['match_date']
        verbose_name = "Partido"
        verbose_name_plural = "Partidos"

    def __str__(self):
        score = f"{self.home_score} - {self.away_score}" if self.status == 'FINISHED' else "vs"
        return f"{self.team_home} {score} {self.team_away} ({self.get_status_display()})"

    @property
    def is_finished(self):
        return self.status == 'FINISHED' and self.home_score is not None and self.away_score is not None

    @property
    def outcome(self):
        """Devuelve 'HOME', 'AWAY' o 'DRAW' si ya finalizó."""
        if not self.is_finished:
            return None
        if self.home_score > self.away_score:
            return 'HOME'
        elif self.home_score < self.away_score:
            return 'AWAY'
        return 'DRAW'

    @property
    def goal_difference(self):
        """Diferencia de goles (Local - Visitante)"""
        if not self.is_finished:
            return None
        return self.home_score - self.away_score


class Prediction(models.Model):
    """
    Predicción de un participante para un partido.
    Almacena el desglose detallado de las 5 reglas de puntuación.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="predictions")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")
    home_score_pred = models.IntegerField(verbose_name="Predicción Goles Local")
    away_score_pred = models.IntegerField(verbose_name="Predicción Goles Visitante")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Desglose de puntos según las 5 reglas
    exact_score_points = models.IntegerField(default=0, verbose_name="Regla 1: Marcador Exacto (5 pts)")
    winner_points = models.IntegerField(default=0, verbose_name="Regla 2: Ganador Correcto (3 pts)")
    diff_points = models.IntegerField(default=0, verbose_name="Regla 3: Diferencia de Goles (2 pts)")
    streak_bonus_points = models.IntegerField(default=0, verbose_name="Regla 4: Bonus por Racha (2 pts)")
    early_bonus_points = models.IntegerField(default=0, verbose_name="Regla 5: Predicción Anticipada (+1 pt)")
    total_points = models.IntegerField(default=0, verbose_name="Puntos Totales")
    is_evaluated = models.BooleanField(default=False)
    rule_breakdown = models.JSONField(default=dict, blank=True, verbose_name="Detalle de Evaluación")

    class Meta:
        unique_together = ('user', 'match')
        ordering = ['-match__match_date']
        verbose_name = "Predicción"
        verbose_name_plural = "Predicciones"

    def __str__(self):
        return f"{self.user.username}: {self.match.team_home} {self.home_score_pred}-{self.away_score_pred} {self.match.team_away} ({self.total_points} pts)"

    @property
    def predicted_outcome(self):
        if self.home_score_pred > self.away_score_pred:
            return 'HOME'
        elif self.home_score_pred < self.away_score_pred:
            return 'AWAY'
        return 'DRAW'

    @property
    def predicted_goal_diff(self):
        return self.home_score_pred - self.away_score_pred


class UserProfile(models.Model):
    """
    Perfil y estadísticas acumuladas del usuario.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    total_points = models.IntegerField(default=0, db_index=True)
    exact_hits = models.IntegerField(default=0)
    winner_hits = models.IntegerField(default=0)
    diff_hits = models.IntegerField(default=0)
    streak_bonuses = models.IntegerField(default=0)
    early_bonuses = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    max_streak = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_points', '-exact_hits', 'user__username']
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

    def __str__(self):
        return f"{self.user.username} - {self.total_points} pts"
