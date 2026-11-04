"""
Pruebas Unitarias para el Sistema de Puntuación (5 Reglas de Negocio)
Ejecutable mediante: python manage.py test tests
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from core.models import Match, Prediction, UserProfile, Room, RoomMember
from core.scoring import calculate_match_points, evaluate_user_predictions, recalculate_all_scores
from core.ai_engine import generate_match_ai_analysis, calculate_xg


class ScoringRulesTestCase(TestCase):
    """
    Pruebas automatizadas de las 5 reglas de puntuación solicitadas en el laboratorio:
    1) Marcador exacto (5 pts)
    2) Ganador correcto (3 pts)
    3) Diferencia de goles correcta (2 pts)
    4) Bonus por racha (+2 pts cada 3 aciertos consecutivos)
    5) Predicción anticipada (+1 pt extra si > 24h)
    """

    def setUp(self):
        self.user = User.objects.create_user(username='test_user', password='password123')
        self.profile = UserProfile.objects.create(user=self.user)
        self.base_time = timezone.now()

    def test_rule_1_exact_score(self):
        """Regla 1: Marcador exacto otorga 5 puntos."""
        # Predicción 2 - 1, Resultado 2 - 1
        res = calculate_match_points(pred_home=2, pred_away=1, actual_home=2, actual_away=1)
        self.assertEqual(res['rule_1_exact_score'], 5)
        self.assertEqual(res['base_points'], 5)
        self.assertEqual(res['total_points'], 5)
        self.assertTrue(res['is_hit'])

    def test_rule_2_correct_winner_only(self):
        """Regla 2: Ganador correcto sin margen de goles otorga 3 puntos."""
        # Predicción 3 - 0 (gana Local, dif +3), Resultado 2 - 0 (gana Local, dif +2)
        res = calculate_match_points(pred_home=3, pred_away=0, actual_home=2, actual_away=0)
        self.assertEqual(res['rule_1_exact_score'], 0)
        self.assertEqual(res['rule_2_correct_winner'], 3)
        self.assertEqual(res['rule_3_correct_diff'], 0)
        self.assertEqual(res['base_points'], 3)
        self.assertEqual(res['total_points'], 3)
        self.assertTrue(res['is_hit'])

    def test_rule_3_correct_winner_and_goal_diff(self):
        """
        Regla 3: Diferencia de goles correcta (ejemplo oficial del enunciado:
        predice 3-1 y termina 2-0, ambos con diferencia de 2 a favor del mismo equipo).
        Gana 3 pts (ganador) + 2 pts (margen) = 5 pts.
        """
        res = calculate_match_points(pred_home=3, pred_away=1, actual_home=2, actual_away=0)
        self.assertEqual(res['rule_1_exact_score'], 0)
        self.assertEqual(res['rule_2_correct_winner'], 3)
        self.assertEqual(res['rule_3_correct_diff'], 2)
        self.assertEqual(res['base_points'], 5)
        self.assertEqual(res['total_points'], 5)
        self.assertTrue(res['is_hit'])

    def test_draw_predictions(self):
        """Prueba de empates: Exacto (1-1 vs 1-1) y Acierto de Empate (2-2 vs 1-1)."""
        # Exacto: 1-1 vs 1-1
        exact_res = calculate_match_points(pred_home=1, pred_away=1, actual_home=1, actual_away=1)
        self.assertEqual(exact_res['total_points'], 5)

        # No exacto pero acierta empate (ambos diff=0): 2-2 vs 1-1 -> 3 (ganador/empate) + 2 (dif 0) = 5 pts
        draw_res = calculate_match_points(pred_home=2, pred_away=2, actual_home=1, actual_away=1)
        self.assertEqual(draw_res['rule_2_correct_winner'], 3)
        self.assertEqual(draw_res['rule_3_correct_diff'], 2)
        self.assertEqual(draw_res['total_points'], 5)

    def test_wrong_prediction_zero_points(self):
        """Predicción incorrecta otorga 0 puntos."""
        # Predicción 2-1 (Gana local), Resultado 0-2 (Gana visitante)
        res = calculate_match_points(pred_home=2, pred_away=1, actual_home=0, actual_away=2)
        self.assertEqual(res['base_points'], 0)
        self.assertEqual(res['total_points'], 0)
        self.assertFalse(res['is_hit'])

    def test_rule_5_early_prediction_bonus(self):
        """Regla 5: Predicción anticipada con más de 24h otorga +1 punto extra."""
        # Predicción acertada anticipada
        res_early = calculate_match_points(pred_home=2, pred_away=1, actual_home=2, actual_away=1, is_early_prediction=True)
        self.assertEqual(res_early['rule_1_exact_score'], 5)
        self.assertEqual(res_early['rule_5_early_bonus'], 1)
        self.assertEqual(res_early['total_points'], 6)

        # Predicción de último minuto (no anticipada)
        res_late = calculate_match_points(pred_home=2, pred_away=1, actual_home=2, actual_away=1, is_early_prediction=False)
        self.assertEqual(res_late['rule_5_early_bonus'], 0)
        self.assertEqual(res_late['total_points'], 5)

    def test_rule_4_streak_bonus_comprehensive(self):
        """
        Regla 4: Por cada 3 partidos consecutivos acertados (al menos el ganador),
        suma 2 puntos adicionales como recompensa a la constancia.
        """
        # Crear 5 partidos finalizados cronológicos
        matches = []
        for i in range(5):
            m = Match.objects.create(
                team_home=f"TeamA_{i}",
                team_away=f"TeamB_{i}",
                match_date=self.base_time + timedelta(days=i),
                status='FINISHED',
                home_score=2,
                away_score=1
            )
            matches.append(m)

        # Partido 0: Acertado exacto 2-1 (+5 pts) -> Racha = 1
        p0 = Prediction.objects.create(user=self.user, match=matches[0], home_score_pred=2, away_score_pred=1)
        p0.created_at = matches[0].match_date - timedelta(hours=2) # sin bonus anticipacion
        p0.save()

        # Partido 1: Acertado ganador 3-1 (+3 pts) -> Racha = 2
        p1 = Prediction.objects.create(user=self.user, match=matches[1], home_score_pred=3, away_score_pred=1)
        p1.created_at = matches[1].match_date - timedelta(hours=2)
        p1.save()

        # Partido 2: Acertado ganador 1-0 (+3 pts) -> Racha = 3 -> ¡Activa Regla 4: +2 pts bonus!
        p2 = Prediction.objects.create(user=self.user, match=matches[2], home_score_pred=1, away_score_pred=0)
        p2.created_at = matches[2].match_date - timedelta(hours=2)
        p2.save()

        # Partido 3: Falló 0-2 (0 pts) -> Racha se reinicia a 0
        p3 = Prediction.objects.create(user=self.user, match=matches[3], home_score_pred=0, away_score_pred=2)
        p3.created_at = matches[3].match_date - timedelta(hours=2)
        p3.save()

        # Partido 4: Acertó ganador 2-1 (+5 pts) -> Racha = 1
        p4 = Prediction.objects.create(user=self.user, match=matches[4], home_score_pred=2, away_score_pred=1)
        p4.created_at = matches[4].match_date - timedelta(hours=2)
        p4.save()

        # Evaluar
        stats = evaluate_user_predictions(self.user)

        # Verificación:
        # P0: 5 pts (exacto 2-1 vs 2-1)
        # P1: 3 pts (ganador 3-1 vs 2-1, dif +2 != +1)
        # P2: 3 pts (ganador 1-0 vs 2-1) + 2 pts (dif +1 == +1) + 2 pts (bonus racha 3) = 7 pts
        # P3: 0 pts (falló 0-2 vs 2-1)
        # P4: 5 pts (exacto 2-1 vs 2-1)
        # Total esperado = 5 + 3 + (3 + 2 + 2) + 0 + 5 = 20 puntos
        self.assertEqual(stats['total_points'], 20)
        self.assertEqual(stats['streak_bonuses'], 1)
        self.assertEqual(stats['max_streak'], 3)
        self.assertEqual(stats['current_streak'], 1)


class RoomsAndInvitationsTestCase(TestCase):
    """Pruebas del sistema de Salas (Grupos) con invitaciones."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='anderson_host', password='password')
        self.user2 = User.objects.create_user(username='carlos_guest', password='password')

    def test_create_room_generates_unique_code(self):
        """Crear sala debe generar código único con prefijo WC26."""
        room = Room.objects.create(name="Sala de Prueba", created_by=self.user1)
        self.assertTrue(room.code.startswith("WC26-"))
        self.assertEqual(len(room.code), 10)  # WC26-XXXXX

    def test_join_room_via_code(self):
        """Unirse a una sala mediante código de invitación."""
        room = Room.objects.create(name="Copa Amigos", created_by=self.user1)
        # Host es miembro
        RoomMember.objects.create(room=room, user=self.user1)
        self.assertEqual(room.member_count, 1)

        # Guest se une por código
        target_room = Room.objects.get(code=room.code)
        membership, created = RoomMember.objects.get_or_create(room=target_room, user=self.user2)
        self.assertTrue(created)
        self.assertEqual(room.member_count, 2)


class AIAssistantTestCase(TestCase):
    """Pruebas del motor predictivo con Inteligencia Artificial (Poisson y xG)."""

    def test_ai_probabilities_sum_to_100(self):
        """La suma de probabilidades de victoria local, empate y visitante debe ser 100%."""
        analysis = generate_match_ai_analysis('Argentina', 'Francia')
        probs = analysis['probabilities']
        total = probs['home_win'] + probs['draw'] + probs['away_win']
        self.assertAlmostEqual(total, 100.0, delta=0.5)

    def test_ai_top_scores_generated(self):
        """El motor debe generar los marcadores más probables y recomendación táctica."""
        analysis = generate_match_ai_analysis('Perú', 'Chile')
        self.assertGreater(len(analysis['top_scores']), 0)
        self.assertIn('recommended_prediction', analysis)
        self.assertIn('tactical_summary', analysis)
        self.assertGreater(analysis['home_xg'], 0)
