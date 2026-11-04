"""
Script Visualizador en Tiempo Real para Grabación de Video de Pruebas de Estrés
Ejecuta solicitudes concurrentes y muestra en pantalla cada petición en vivo
identificando la réplica backend exacta que la procesó a través del balanceador Nginx.
"""

import time
import concurrent.futures
import urllib.request
import urllib.error
from collections import Counter
import statistics
import argparse
import sys

# Ajuste de codificación
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ENDPOINTS = [
    ('/', 'GET'),
    ('/leaderboard/', 'GET'),
    ('/rooms/', 'GET'),
    ('/api/health/', 'GET'),
    ('/ai-analysis/1/', 'GET'),
]

counter_lock = 0

def make_request(request_id, base_url, endpoint_info):
    path, method = endpoint_info
    url = f"{base_url.rstrip('/')}{path}"
    start_time = time.time()
    server_node = "unknown"
    status_code = 0

    try:
        req = urllib.request.Request(url, method=method)
        req.add_header('User-Agent', 'VideoDemoStress/1.0')
        with urllib.request.urlopen(req, timeout=8) as resp:
            latency_ms = (time.time() - start_time) * 1000.0
            status_code = resp.status
            server_node = resp.headers.get('X-Served-By') or resp.headers.get('X-Upstream-Node') or 'backend-node'
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - start_time) * 1000.0
        status_code = e.code
        server_node = e.headers.get('X-Served-By') or 'error'
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        status_code = 500
        server_node = 'timeout'

    # Imprimir en consola en tiempo real para la grabación
    short_node = server_node[:12] if len(server_node) > 12 else server_node
    print(f"[{request_id:03d}] -> NODO: {short_node:<12} | HTTP {status_code} | {latency_ms:6.1f}ms | {method} {path}")

    return {
        'id': request_id,
        'url': path,
        'status_code': status_code,
        'latency_ms': latency_ms,
        'server_node': server_node
    }

def run_live_demo(base_url="http://127.0.0.1:8000", total_requests=120, concurrency=12):
    print("\n" + "=" * 80)
    print("🎬 INICIANDO DEMOSTRACIÓN DE PRUEBAS DE ESTRÉS Y BALANCEO EN TIEMPO REAL")
    print(f"🎯 URL Destino: {base_url} (Balanceador Nginx)")
    print(f"⚡ Peticiones:  {total_requests} solicitudes | Concurrencia: {concurrency} hilos simultáneos")
    print("=" * 80)
    print("REGISTRO DE PETICIONES EN TIEMPO REAL:")
    print("-" * 80)

    start_all = time.time()
    results = []

    tasks = []
    for i in range(1, total_requests + 1):
        endpoint = ENDPOINTS[i % len(ENDPOINTS)]
        tasks.append((i, base_url, endpoint))

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, t[0], t[1], t[2]) for t in tasks]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    total_duration = time.time() - start_all
    latencies = [r['latency_ms'] for r in results]
    successes = sum(1 for r in results if 200 <= r['status_code'] < 400)
    node_distribution = Counter(r['server_node'] for r in results)

    latencies.sort()
    avg_latency = statistics.mean(latencies)
    rps = total_requests / total_duration

    print("\n" + "=" * 80)
    print("📊 RESULTADOS FINALES DE LA PRUEBA DE ESTRÉS (EVIDENCIA DE BALANCEO)")
    print("=" * 80)
    print(f"  • Tiempo Total:             {total_duration:.2f} segundos")
    print(f"  • Peticiones Exitosas:      {successes}/{total_requests} ({(successes/total_requests)*100:.1f}%)")
    print(f"  • Throughput (Rendimiento): {rps:.2f} Peticiones/segundo (RPS)")
    print(f"  • Latencia Promedio:        {avg_latency:.2f} ms")
    print(f"  • Latencia Mínima / Máxima: {min(latencies):.2f} ms / {max(latencies):.2f} ms")
    print("-" * 80)
    print("⚖️  DISTRIBUCIÓN EQUITATIVA ENTRE RÉPLICAS BACKEND (ROUND-ROBIN):")
    for node, count in sorted(node_distribution.items()):
        pct = (count / total_requests) * 100
        bars = "█" * int(pct / 2.5)
        print(f"  • Réplica {node:<15} : {count:3d} peticiones ({pct:5.1f}%) [{bars}]")
    print("=" * 80 + "\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Live stress testing demo")
    parser.add_argument('--url', default="http://127.0.0.1:8000", help="Target URL")
    parser.add_argument('--requests', type=int, default=120, help="Total requests")
    parser.add_argument('--concurrency', type=int, default=12, help="Concurrency")
    args = parser.parse_args()

    run_live_demo(base_url=args.url, total_requests=args.requests, concurrency=args.concurrency)
