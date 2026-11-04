from locust import HttpUser, task, between
import random

class MundialPredictorUser(HttpUser):
    """
    Simulación de comportamiento de usuario real en la Polla del Mundial:
    - Consulta el Dashboard de partidos
    - Revisa la tabla de posiciones global
    - Consulta salas y rankings
    - Consulta estadísticas con IA (Poisson/xG)
    - Consulta endpoint de salud del nodo (Load Balancer)
    """
    wait_time = between(1, 3)

    @task(4)
    def view_dashboard(self):
        self.client.get("/")

    @task(3)
    def view_leaderboard(self):
        self.client.get("/leaderboard/")

    @task(2)
    def view_rooms(self):
        self.client.get("/rooms/")

    @task(2)
    def view_ai_match_analysis(self):
        match_id = random.choice([1, 2, 3, 5, 6])
        self.client.get(f"/ai-analysis/{match_id}/")

    @task(1)
    def check_node_health(self):
        self.client.get("/api/health/")
