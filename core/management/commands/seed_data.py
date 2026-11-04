from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.models import Match, Room, RoomMember, Prediction, UserProfile
from core.scoring import recalculate_all_scores

class Command(BaseCommand):
    help = "Puebla la base de datos con partidos del Mundial, usuarios demo, salas y predicciones de prueba"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("[*] Iniciando sembrado de datos del Mundial 2026..."))

        # 1. Crear Superusuario y Usuarios Demo
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@mundial.pe', 'first_name': 'Administrador', 'is_staff': True, 'is_superuser': True}
        )
        admin_user.set_password('admin123')
        admin_user.save()

        demo_users_data = [
            ('anderson', 'Anderson', 'anderson@uni.edu.pe', '1234'),
            ('carlos_g', 'Carlos Gonzales', 'carlos@pucp.edu.pe', '1234'),
            ('maria_dev', 'María Rodriguez', 'maria@utec.edu.pe', '1234'),
            ('profesor', 'Profesor Calificador', 'docente@universidad.edu.pe', '1234'),
        ]

        users = {}
        for uname, fname, email, pwd in demo_users_data:
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={'first_name': fname, 'email': email}
            )
            u.set_password(pwd)
            u.save()
            UserProfile.objects.get_or_create(user=u)
            users[uname] = u

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(users) + 1} usuarios creados o actualizados."))

        # 2. Crear Partidos del Mundial (Finalizados y Programados)
        now = timezone.now()

        matches_data = [
            # Partidos Finalizados (para verificar las 5 reglas en vivo)
            {
                'team_home': 'Perú', 'team_away': 'Chile',
                'home_flag': '🇵🇪', 'away_flag': '🇨🇱',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo A',
                'stadium': 'Estadio Azteca, CDMX',
                'match_date': now - timedelta(days=4),
                'status': 'FINISHED', 'home_score': 2, 'away_score': 0
            },
            {
                'team_home': 'Argentina', 'team_away': 'Francia',
                'home_flag': '🇦🇷', 'away_flag': '🇫🇷',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo B',
                'stadium': 'MetLife Stadium, New Jersey',
                'match_date': now - timedelta(days=3),
                'status': 'FINISHED', 'home_score': 2, 'away_score': 1
            },
            {
                'team_home': 'Brasil', 'team_away': 'Alemania',
                'home_flag': '🇧🇷', 'away_flag': '🇩🇪',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo C',
                'stadium': 'SoFi Stadium, Los Ángeles',
                'match_date': now - timedelta(days=2),
                'status': 'FINISHED', 'home_score': 3, 'away_score': 1
            },
            {
                'team_home': 'España', 'team_away': 'Portugal',
                'home_flag': '🇪🇸', 'away_flag': '🇵🇹',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo D',
                'stadium': 'Hard Rock Stadium, Miami',
                'match_date': now - timedelta(days=1),
                'status': 'FINISHED', 'home_score': 2, 'away_score': 2
            },

            # Partidos Programados (Próximos para que el usuario prediga)
            {
                'team_home': 'Perú', 'team_away': 'Uruguay',
                'home_flag': '🇵🇪', 'away_flag': '🇺🇾',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo A',
                'stadium': 'Estadio Akron, Guadalajara',
                'match_date': now + timedelta(days=2, hours=3),
                'status': 'SCHEDULED', 'home_score': None, 'away_score': None
            },
            {
                'team_home': 'Argentina', 'team_away': 'Brasil',
                'home_flag': '🇦🇷', 'away_flag': '🇧🇷',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo B',
                'stadium': 'AT&T Stadium, Dallas',
                'match_date': now + timedelta(days=3, hours=5),
                'status': 'SCHEDULED', 'home_score': None, 'away_score': None
            },
            {
                'team_home': 'Colombia', 'team_away': 'Japón',
                'home_flag': '🇨🇴', 'away_flag': '🇯🇵',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo E',
                'stadium': 'Mercedes-Benz Stadium, Atlanta',
                'match_date': now + timedelta(days=4),
                'status': 'SCHEDULED', 'home_score': None, 'away_score': None
            },
            {
                'team_home': 'Inglaterra', 'team_away': 'Países Bajos',
                'home_flag': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'away_flag': '🇳🇱',
                'stage': 'Fase de Grupos', 'group_name': 'Grupo F',
                'stadium': 'Lumen Field, Seattle',
                'match_date': now + timedelta(days=5),
                'status': 'SCHEDULED', 'home_score': None, 'away_score': None
            },
        ]

        created_matches = []
        for m_data in matches_data:
            match, _ = Match.objects.update_or_create(
                team_home=m_data['team_home'],
                team_away=m_data['team_away'],
                defaults=m_data
            )
            created_matches.append(match)

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(created_matches)} partidos registrados."))

        # 3. Crear Salas de Prediccion con Codigos de Invitacion
        room1, _ = Room.objects.get_or_create(
            code="WC26-UNISYS",
            defaults={
                'name': 'Facultad de Ingenieria de Sistemas',
                'description': 'Sala oficial del laboratorio de sistemas distribuidos y arquitectura.',
                'created_by': users['anderson']
            }
        )

        room2, _ = Room.objects.get_or_create(
            code="WC26-VIP26",
            defaults={
                'name': 'Polla Amigos & Gamers',
                'description': 'Grupo privado de apuestas y predicciones del Mundial 2026.',
                'created_by': users['carlos_g']
            }
        )

        # Asociar participantes a salas
        for u in [users['anderson'], users['carlos_g'], users['maria_dev'], users['profesor']]:
            RoomMember.objects.get_or_create(room=room1, user=u)

        for u in [users['carlos_g'], users['maria_dev']]:
            RoomMember.objects.get_or_create(room=room2, user=u)

        self.stdout.write(self.style.SUCCESS("[OK] Salas de prediccion con codigos de invitacion configuradas."))

        # 4. Crear Predicciones de Ejemplo para Probar las 5 Reglas
        # Partido 1: Peru 2 - 0 Chile
        m1 = created_matches[0]
        # anderson predijo 2-0 (Exacto: 5 pts + anticipada: 1 pt = 6 pts)
        p1, _ = Prediction.objects.get_or_create(
            user=users['anderson'], match=m1,
            defaults={'home_score_pred': 2, 'away_score_pred': 0}
        )
        p1.created_at = m1.match_date - timedelta(hours=30)
        p1.save()

        # carlos_g predijo 3-1 (Ganador correcto: 3 pts + Diferencia de +2 goles correcta: 2 pts = 5 pts)
        p2, _ = Prediction.objects.get_or_create(
            user=users['carlos_g'], match=m1,
            defaults={'home_score_pred': 3, 'away_score_pred': 1}
        )
        p2.created_at = m1.match_date - timedelta(hours=5)  # No anticipada
        p2.save()

        # maria_dev predijo 1-0 (Ganador correcto: 3 pts, diferente margen = 3 pts)
        p3, _ = Prediction.objects.get_or_create(
            user=users['maria_dev'], match=m1,
            defaults={'home_score_pred': 1, 'away_score_pred': 0}
        )
        p3.save()

        # Partido 2: Argentina 2 - 1 Francia
        m2 = created_matches[1]
        p4, _ = Prediction.objects.get_or_create(
            user=users['anderson'], match=m2,
            defaults={'home_score_pred': 2, 'away_score_pred': 1}  # Exacto (5 pts)
        )
        p4.save()

        # Partido 3: Brasil 3 - 1 Alemania
        m3 = created_matches[2]
        p5, _ = Prediction.objects.get_or_create(
            user=users['anderson'], match=m3,
            defaults={'home_score_pred': 2, 'away_score_pred': 0}  # Ganador y dif correcta (3+2=5 pts)
        )
        p5.save()

        # Partido 4: Espana 2 - 2 Portugal
        m4 = created_matches[3]
        p6, _ = Prediction.objects.get_or_create(
            user=users['anderson'], match=m4,
            defaults={'home_score_pred': 1, 'away_score_pred': 1}  # Empate y dif 0
        )
        p6.save()

        # 5. Ejecutar motor de calculo de las 5 reglas
        recalculate_all_scores()
        self.stdout.write(self.style.SUCCESS("[OK] Motor de puntuacion (5 Reglas) evaluado con exito."))
        self.stdout.write(self.style.SUCCESS("[DONE] Datos iniciales listos para el laboratorio."))
