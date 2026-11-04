# PROPUESTA DE ARQUITECTURA DEL SISTEMA
## Plataforma de Predicciones del Mundial de Fútbol (Quiniela / Polla Mundialista)

---

### 1. Resumen Ejecutivo
El presente documento describe la arquitectura de software propuesta para la aplicación de predicciones de partidos del Mundial de Fútbol. La solución está diseñada bajo un enfoque de **sistemas distribuidos**, **alta disponibilidad**, **desacoplamiento modular** y **escalabilidad horizontal elástica**.

El sistema permite a los participantes registrar pronósticos para los encuentros del torneo, organizarse en **Salas Privadas (Grupos)** mediante códigos alfanuméricos únicos de invitación, competir en una **Tabla de Posiciones Global y por Salas**, y consultar **estadísticas predictivas impulsadas por Inteligencia Artificial** (modelo bivariado de Poisson y cálculo de Expected Goals - xG). Asimismo, implementa con total rigor un motor de evaluación basado en **5 reglas de puntuación oficiales**.

---

### 2. Diagrama de Arquitectura Global del Sistema

El flujo general de componentes y el balanceo de carga se estructura en un modelo multicapa:

```mermaid
flowchart TD
    subgraph Clientes ["Capa de Clientes (Presentación)"]
        BrowserUser["Navegador Web / Mobile\n(Tailwind CSS + HTML5 + JS)"]
        StressClient["Agente de Pruebas de Estrés\n(Locust / Multi-thread Tester)"]
    end

    subgraph Perimetro ["Capa de Balanceo de Carga y Proxy Inverso"]
        NginxLB["Nginx Load Balancer\n(Puerto 80 / 8080)\nEstrategia: Round-Robin\nHealthcheck & Proxy Headers"]
    end

    subgraph BackendCluster ["Capa de Aplicación - Escalamiento Horizontal"]
        Node1["Backend Réplica 1\n(Django/Gunicorn - PID 101)\nX-Served-By: backend-1"]
        Node2["Backend Réplica 2\n(Django/Gunicorn - PID 102)\nX-Served-By: backend-2"]
        Node3["Backend Réplica 3\n(Django/Gunicorn - PID 103)\nX-Served-By: backend-3"]
    end

    subgraph ModulosCore ["Módulos de Negocio Internos"]
        ScoringEngine["Motor de 5 Reglas\nde Puntuación"]
        AIEngine["Motor Predictivo IA\n(Poisson + xG)"]
        RoomsModule["Gestor de Salas &\nCódigos de Invitación"]
    end

    subgraph Datos ["Capa de Persistencia y Estado"]
        PostgresDB[("Base de Datos Relacional\nPostgreSQL 16\n(Docker Volume Persistente)")]
    end

    BrowserUser -->|Peticiones HTTP/HTTPS| NginxLB
    StressClient -->|Carga Concurrente Masiva| NginxLB

    NginxLB -->|Balanceo Round-Robin 33%| Node1
    NginxLB -->|Balanceo Round-Robin 33%| Node2
    NginxLB -->|Balanceo Round-Robin 33%| Node3

    Node1 --> ModulosCore
    Node2 --> ModulosCore
    Node3 --> ModulosCore

    ModulosCore -->|Pool de Conexiones TCP 5432| PostgresDB
```

---

### 3. Componentes del Sistema

#### 3.1. Capa de Presentación (Frontend)
- **Tecnología**: Interfaz web responsiva con **HTML5**, **Tailwind CSS (Dark World Cup Theme)** y **JavaScript asíncrono**.
- **Características**:
  - Panel interactivo para el registro y actualización de marcadores pronosticados.
  - Indicador dinámico de nodo activo: muestra en cabecera y pie de página el servidor que atendió la petición (`X-Served-By: backend-replica-X`), comprobando el balanceo de carga en tiempo real.
  - Modal interactivo con telemetría de IA: gráficos y probabilidades para cada encuentro (Victoria Local %, Empate %, Victoria Visitante %, Top 3 marcadores Poisson).
  - Módulo de Salas con generación de códigos de invitación y copia en un clic.

#### 3.2. Capa de Balanceo de Carga y Proxy Inverso (Nginx)
- **Estrategia de balanceo**: **Round-Robin** equitativo entre las réplicas backend disponibles.
- **Funcionalidades clave**:
  - Terminación y enrutamiento HTTP en puertos 80 y 8080.
  - Inyección y preservación de cabeceras de trazabilidad: `X-Forwarded-For`, `X-Real-IP`, `X-Served-By`, `X-Process-PID`.
  - Servidor de archivos estáticos optimizado con directivas de caché `Cache-Control`.
  - Monitoreo continuo del estado de las réplicas mediante sondeo de salud (`/lb-health` y `/api/health/`). En caso de caída de una réplica, es excluida temporalmente sin interrumpir a los usuarios.

#### 3.3. Capa de Aplicación (Backend Replicable)
- **Tecnología**: **Python 3.12 / 3.14** con **Django Framework**, **Django REST Framework** y servidor de producción **Gunicorn** (con 3 workers por contenedor).
- **Escalabilidad Horizontal**: Cada réplica se ejecuta como un contenedor sin estado (*stateless*). Cualquier réplica puede procesar cualquier solicitud, ya que las sesiones y autenticaciones se resuelven a nivel de base de datos compartida.
- **Middleware de Identidad**: `ServerIdentityMiddleware` inspecciona el entorno y adjunta a las cabeceras HTTP la identificación única del contenedor y su PID del sistema operativo.

#### 3.4. Capa de Datos (Persistencia Relacional)
- **Tecnología**: **PostgreSQL 16 Alpine** (en contenedor Docker con volumen montado para persistencia entre reinicios). Para entornos de desarrollo local rápido sin dependencias externas, el sistema conmuta automáticamente a **SQLite3**.
- **Integridad**: Llaves foráneas con restricciones en cascada, índices únicos compuestos en `(user_id, match_id)` para garantizar una única predicción por partido, e índices de alto rendimiento en códigos de sala y puntajes acumulados.

---

### 4. Modelo de Datos (Diagrama Entidad-Relación)

```mermaid
erDiagram
    USER ||--o{ ROOM_MEMBER : participa
    USER ||--o{ ROOM : crea
    USER ||--o{ PREDICTION : pronostica
    USER ||--|| USER_PROFILE : posee
    ROOM ||--o{ ROOM_MEMBER : contiene
    MATCH ||--o{ PREDICTION : recibe

    USER {
        int id PK
        string username UK
        string email
        string password
    }

    USER_PROFILE {
        int id PK
        int user_id FK
        int total_points
        int exact_hits
        int winner_hits
        int diff_hits
        int streak_bonuses
        int early_bonuses
        int current_streak
        int max_streak
    }

    ROOM {
        int id PK
        string name
        string code UK
        text description
        int created_by_id FK
        datetime created_at
    }

    ROOM_MEMBER {
        int id PK
        int room_id FK
        int user_id FK
        datetime joined_at
    }

    MATCH {
        int id PK
        string team_home
        string team_away
        datetime match_date
        string status
        int home_score
        int away_score
        string stadium
        string stage
    }

    PREDICTION {
        int id PK
        int user_id FK
        int match_id FK
        int home_score_pred
        int away_score_pred
        int exact_score_points
        int winner_points
        int diff_points
        int streak_bonus_points
        int early_bonus_points
        int total_points
        boolean is_evaluated
        json rule_breakdown
        datetime created_at
    }
```

---

### 5. Diagrama de Secuencia: Envío y Evaluación de Predicciones

```mermaid
sequenceDiagram
    autonumber
    actor U as Participante
    participant LB as Nginx Load Balancer
    participant W as Backend Réplica (Node-X)
    participant S as Motor de 5 Reglas
    participant DB as PostgreSQL DB

    U->>LB: POST /predict/{match_id} (Marcador 2-1)
    LB->>W: Reenvío Round-Robin a Réplica X
    W->>DB: Guarda Predicción (Timestamp de creación)
    W-->>LB: HTTP 302 Redirección con cabecera X-Served-By
    LB-->>U: Confirmación de Pronóstico Registrado

    Note over W,DB: Se finaliza el partido oficial (ej. Perú 2 - 1 Chile)
    W->>S: Disparo de Recálculo Global (recalculate_all_scores)
    S->>DB: Obtiene Predicciones en orden cronológico
    S->>S: 1. Evalúa Marcador Exacto (+5 pts)
    S->>S: 2. Evalúa Ganador Correcto (+3 pts)
    S->>S: 3. Evalúa Margen de Victoria (+2 pts)
    S->>S: 4. Evalúa Racha de cada 3 aciertos (+2 pts)
    S->>S: 5. Evalúa Anticipación > 24h (+1 pt)
    S->>DB: Actualiza Puntos y Perfil de Usuario
    U->>LB: GET /leaderboard/
    LB->>W: Consulta de Tabla
    W->>DB: Query ranking ordenado por total_points DESC
    DB-->>W: Registros
    W-->>U: Renderizado de Tabla con desglose oficial
```

---

### 6. Estrategia de Escalamiento Horizontal

1. **Sin Estado (*Stateless Servers*)**: Los servidores de backend no almacenan estado en memoria ni en disco local; delegan la persistencia en la base de datos PostgreSQL. Esto permite añadir o remover réplicas sin desconectar usuarios.
2. **Elasticidad con Docker Compose**:
   ```bash
   docker-compose up --scale backend=3 -d
   ```
   El balanceador Nginx consulta dinámicamente al servicio `backend` a través del resolvedor DNS interno de Docker (127.0.0.11), distribuyendo las conexiones concurrentes.
3. **Resiliencia ante Fallos**: Si un contenedor sufre una detención imprevista, la política de salud de Nginx detecta el código de error y redirige inmediatamente el tráfico hacia los contenedores operativos.
