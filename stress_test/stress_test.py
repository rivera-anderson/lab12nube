"""
Script Automatizado de Pruebas de Estrés y Medición de Rendimiento
Diseñado para evaluar:
1. Concurrencia masiva (50 - 200 usuarios simultáneos).
2. Throughput / Rendimiento (Peticiones por Segundo - RPS).
3. Latencias (Min, Media, P50, P90, P95, P99, Max).
4. Distribución del Balanceador de Carga (Round-Robin entre réplicas).
"""

import time
import concurrent.futures
import urllib.request
import urllib.error
from collections import Counter
import statistics
import argparse
import json
import sys

# Asegurar codificación utf-8 en salida estándar si es posible
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

def make_request(base_url, endpoint_info):
    path, method = endpoint_info
    url = f"{base_url.rstrip('/')}{path}"
    start_time = time.time()
    server_node = "unknown"
    status_code = 0
    success = False

    try:
        req = urllib.request.Request(url, method=method)
        req.add_header('User-Agent', 'StressTester-Mundial/1.0')
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency_ms = (time.time() - start_time) * 1000.0
            status_code = resp.status
            success = (200 <= status_code < 400)
            server_node = resp.headers.get('X-Served-By') or resp.headers.get('X-Upstream-Node') or 'backend-1'
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - start_time) * 1000.0
        status_code = e.code
        server_node = e.headers.get('X-Served-By') or 'error'
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        status_code = 599

    return {
        'url': path,
        'status_code': status_code,
        'success': success,
        'latency_ms': latency_ms,
        'server_node': server_node
    }

def run_stress_test(base_url="http://127.0.0.1:8000", total_requests=500, concurrency=25):
    print("=" * 75)
    print(f"[*] INICIANDO PRUEBA DE ESTRES: {base_url}")
    print(f"[*] Solicitudes Totales: {total_requests} | Concurrencia: {concurrency} hilos simultaneos")
    print("=" * 75)

    tasks = []
    for i in range(total_requests):
        endpoint = ENDPOINTS[i % len(ENDPOINTS)]
        tasks.append((base_url, endpoint))

    start_all = time.time()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, t[0], t[1]) for t in tasks]
        for idx, future in enumerate(concurrent.futures.as_completed(futures), 1):
            results.append(future.result())
            if idx % 50 == 0 or idx == total_requests:
                print(f"[*] Progreso: {idx}/{total_requests} peticiones completadas...")

    total_duration = time.time() - start_all
    latencies = [r['latency_ms'] for r in results]
    successes = sum(1 for r in results if r['success'])
    failures = total_requests - successes
    node_distribution = Counter(r['server_node'] for r in results)
    status_codes = Counter(r['status_code'] for r in results)

    latencies.sort()
    avg_latency = statistics.mean(latencies)
    p50 = statistics.median(latencies)
    p90 = latencies[int(len(latencies) * 0.90)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    rps = total_requests / total_duration

    print("\n" + "=" * 75)
    print("RESULTADOS DE LA PRUEBA DE ESTRES Y RENDIMIENTO")
    print("=" * 75)
    print(f"  - Tiempo Total de Ejecucion:      {total_duration:.2f} segundos")
    print(f"  - Peticiones Totales:             {total_requests}")
    print(f"  - Peticiones Exitosas (2xx/3xx):  {successes} ({successes/total_requests*100:.1f}%)")
    print(f"  - Peticiones Fallidas:            {failures}")
    print(f"  - Rendimiento (Throughput):       {rps:.2f} req/seg (RPS)")
    print("-" * 75)
    print("LATENCIAS DE RESPUESTA:")
    print(f"  - Minima:        {min(latencies):.2f} ms")
    print(f"  - Promedio:      {avg_latency:.2f} ms")
    print(f"  - Mediana (P50): {p50:.2f} ms")
    print(f"  - Percentil 90:  {p90:.2f} ms")
    print(f"  - Percentil 95:  {p95:.2f} ms")
    print(f"  - Percentil 99:  {p99:.2f} ms")
    print(f"  - Maxima:        {max(latencies):.2f} ms")
    print("-" * 75)
    print("DISTRIBUCION DEL BALANCEADOR DE CARGA POR NODO/REPLICA:")
    for node, count in sorted(node_distribution.items()):
        pct = (count / total_requests) * 100
        bar = "#" * int(pct / 4)
        print(f"  - {node:<22} : {count:>4} peticiones ({pct:>5.1f}%) [{bar}]")
    print("=" * 75)

    summary = {
        'target_url': base_url,
        'total_requests': total_requests,
        'concurrency': concurrency,
        'duration_seconds': round(total_duration, 2),
        'throughput_rps': round(rps, 2),
        'success_rate_pct': round((successes / total_requests) * 100, 2),
        'latency_min_ms': round(min(latencies), 2),
        'latency_avg_ms': round(avg_latency, 2),
        'latency_p50_ms': round(p50, 2),
        'latency_p95_ms': round(p95, 2),
        'latency_p99_ms': round(p99, 2),
        'latency_max_ms': round(max(latencies), 2),
        'node_distribution': dict(node_distribution),
        'status_codes': dict(status_codes)
    }

    with open("stress_test_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Stress test runner for World Cup Predictor")
    parser.add_argument('--url', default="http://127.0.0.1:8000", help="Target URL")
    parser.add_argument('--requests', type=int, default=300, help="Total requests to send")
    parser.add_argument('--concurrency', type=int, default=20, help="Concurrent worker threads")
    args = parser.parse_args()

    run_stress_test(base_url=args.url, total_requests=args.requests, concurrency=args.concurrency)
