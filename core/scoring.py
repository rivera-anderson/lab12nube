"""
Módulo del Sistema de Puntuación (Scoring Engine)
Implementa rigurosamente las 5 reglas del Laboratorio Calificado:

1) Resultado exacto (5 puntos): acierta marcador exacto (ej. 2-1 y termina 2-1).
2) Ganador correcto (3 puntos): acierta qué equipo gana (o empate) sin marcador exacto.
3) Diferencia de goles correcta (2 puntos): acierta el margen de victoria a favor del mismo equipo.
   (Ej. predice 3-1 y termina 2-0: gana 3 pts por ganador + 2 pts por diferencia de goles = 5 pts base).
4) Bonus por racha (+2 puntos): por cada 3 partidos consecutivos acertados (al menos ganador).
5) Predicción anticipada (+1 punto): si se registra con > 24 horas de anticipación al partido.
"""

from datetime import timedelta
from typing import Dict, Any, Tuple


def calculate_match_points(
    pred_home: int,
    pred_away: int,
    actual_home: int,
    actual_away: int,
    is_early_prediction: bool = False
) -> Dict[str, Any]:
    """
    Calcula los puntos base y bonus individual (reglas 1, 2, 3 y 5) para una predicción frente al resultado real.
    
    Retorna un diccionario con el desglose exacto de cada regla.
    """
    breakdown = {
        'rule_1_exact_score': 0,
        'rule_2_correct_winner': 0,
        'rule_3_correct_diff': 0,
        'rule_4_streak_bonus': 0,  # Se calcula a nivel de racha de usuario
        'rule_5_early_bonus': 0,
        'base_points': 0,
        'total_points': 0,
        'is_hit': False,           # Indica si acertó al menos el ganador o resultado exacto
        'explanation': []
    }

    # Determinación de ganadores: 'HOME', 'AWAY', 'DRAW'
    actual_outcome = 'HOME' if actual_home > actual_away else ('AWAY' if actual_home < actual_away else 'DRAW')
    pred_outcome = 'HOME' if pred_home > pred_away else ('AWAY' if pred_home < pred_away else 'DRAW')

    actual_diff = actual_home - actual_away
    pred_diff = pred_home - pred_away

    # Regla 1: Resultado exacto (5 puntos)
    if pred_home == actual_home and pred_away == actual_away:
        breakdown['rule_1_exact_score'] = 5
        breakdown['base_points'] = 5
        breakdown['is_hit'] = True
        breakdown['explanation'].append("Regla 1: Marcador exacto (+5 pts)")
    else:
        # Si no fue exacto, verificar Ganador (Regla 2) y Diferencia de goles (Regla 3)
        if pred_outcome == actual_outcome:
            breakdown['is_hit'] = True
            # Regla 2: Ganador correcto (3 puntos)
            breakdown['rule_2_correct_winner'] = 3
            breakdown['base_points'] += 3
            breakdown['explanation'].append("Regla 2: Ganador/empate correcto (+3 pts)")

            # Regla 3: Diferencia de goles correcta (2 puntos a favor del mismo equipo o empate)
            if pred_diff == actual_diff:
                breakdown['rule_3_correct_diff'] = 2
                breakdown['base_points'] += 2
                breakdown['explanation'].append(f"Regla 3: Margen de victoria correcto ({pred_diff:+d} goles) (+2 pts)")
        else:
            breakdown['is_hit'] = False
            breakdown['explanation'].append("No acertó ganador ni marcador (0 pts)")

    # Regla 5: Predicción anticipada (1 punto extra si fue > 24 horas antes)
    if is_early_prediction and breakdown['is_hit']:
        breakdown['rule_5_early_bonus'] = 1
        breakdown['explanation'].append("Regla 5: Predicción anticipada > 24h (+1 pt)")

    breakdown['total_points'] = breakdown['base_points'] + breakdown['rule_5_early_bonus']
    return breakdown


def evaluate_user_predictions(user) -> Dict[str, Any]:
    """
    Evalúa todas las predicciones de un usuario en orden cronológico de partidos finalizados.
    Aplica rigurosamente la Regla 4 (Bonus por racha de cada 3 partidos acertados).
    Actualiza el perfil y las predicciones en la base de datos.
    """
    from .models import Prediction, UserProfile, Match

    profile, _ = UserProfile.objects.get_or_create(user=user)

    # Obtener todas las predicciones del usuario sobre partidos finalizados ordenados por fecha
    predictions = (
        Prediction.objects
        .filter(user=user, match__status='FINISHED', match__home_score__isnull=False, match__away_score__isnull=False)
        .select_related('match')
        .order_by('match__match_date', 'match__id')
    )

    current_streak = 0
    max_streak = 0
    total_points = 0
    exact_count = 0
    winner_count = 0
    diff_count = 0
    streak_bonuses_total = 0
    early_bonuses_total = 0

    for pred in predictions:
        match = pred.match
        
        # Evaluar si fue anticipada con > 24h
        time_diff = match.match_date - pred.created_at
        is_early = time_diff >= timedelta(hours=24)

        eval_result = calculate_match_points(
            pred_home=pred.home_score_pred,
            pred_away=pred.away_score_pred,
            actual_home=match.home_score,
            actual_away=match.away_score,
            is_early_prediction=is_early
        )

        # Regla 4: Bonus por racha
        streak_bonus = 0
        if eval_result['is_hit']:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
            
            # Cada 3 partidos consecutivos acertados suma 2 puntos adicionales
            if current_streak % 3 == 0:
                streak_bonus = 2
                eval_result['rule_4_streak_bonus'] = 2
                eval_result['explanation'].append(f"Regla 4: Racha de {current_streak} partidos consecutivos acertados (+2 pts)")
        else:
            current_streak = 0

        eval_result['total_points'] = eval_result['base_points'] + eval_result['rule_5_early_bonus'] + streak_bonus

        # Guardar en la predicción
        pred.exact_score_points = eval_result['rule_1_exact_score']
        pred.winner_points = eval_result['rule_2_correct_winner']
        pred.diff_points = eval_result['rule_3_correct_diff']
        pred.streak_bonus_points = streak_bonus
        pred.early_bonus_points = eval_result['rule_5_early_bonus']
        pred.total_points = eval_result['total_points']
        pred.is_evaluated = True
        pred.rule_breakdown = eval_result
        pred.save(update_fields=[
            'exact_score_points', 'winner_points', 'diff_points',
            'streak_bonus_points', 'early_bonus_points', 'total_points',
            'is_evaluated', 'rule_breakdown'
        ])

        # Acumular estadísticas del usuario
        total_points += eval_result['total_points']
        if eval_result['rule_1_exact_score'] > 0:
            exact_count += 1
        if eval_result['rule_2_correct_winner'] > 0:
            winner_count += 1
        if eval_result['rule_3_correct_diff'] > 0:
            diff_count += 1
        if streak_bonus > 0:
            streak_bonuses_total += 1
        if eval_result['rule_5_early_bonus'] > 0:
            early_bonuses_total += 1

    # Actualizar perfil
    profile.total_points = total_points
    profile.exact_hits = exact_count
    profile.winner_hits = winner_count
    profile.diff_hits = diff_count
    profile.streak_bonuses = streak_bonuses_total
    profile.early_bonuses = early_bonuses_total
    profile.current_streak = current_streak
    profile.max_streak = max_streak
    profile.save()

    return {
        'user': user.username,
        'total_points': total_points,
        'current_streak': current_streak,
        'max_streak': max_streak,
        'exact_hits': exact_count,
        'winner_hits': winner_count,
        'diff_hits': diff_count,
        'streak_bonuses': streak_bonuses_total,
        'early_bonuses': early_bonuses_total,
    }


def recalculate_all_scores():
    """
    Recalcula todas las predicciones y perfiles de todos los usuarios registrados.
    Se ejecuta tras actualizar el marcador de un partido.
    """
    from django.contrib.auth.models import User
    users = User.objects.all()
    results = []
    for u in users:
        results.append(evaluate_user_predictions(u))
    return results
