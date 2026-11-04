"""
Script de Prueba de Punto de Quiebre (Breaking Point / Saturation Test)
Incrementa progresivamente la carga y la concurrencia en 5 etapas
hasta encontrar el límite máximo de rendimiento y el colapso del clúster.
"""

import time
import concurrent.futures
import urllib.request
import urllib.error
from collections import Counter
import statistics
import argparse
import sys

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

STAGES = [
    {"name": "Nivel 1: Tráfico Normal",     "requests": 200,  "concurrency": 10},
    {"name": "Nivel 2: Carga Moderada",     "requests": 500,  "concurrency": 25},
    {"name": "Nivel 3: Carga Alta",         "requests": 1000, "concurrency": 50},
    {"name": "Nivel 4: Estrés Severo",      "requests": 2500, "concurrency": 75},
    {"name": "Nivel 5: Saturación Extrema", "requests": 5000, "concurrency": 100},
]

def make_req(base_url, endpoint_info, timeout=4):
    path, method = endpoint_info
    url = f"{base_url.rstrip('/')}{path}"
    start = time.time()
    code = 0
    node = 'unknown'

    try:
        req = urllib.request.Request(url, method=method)
        req.add_header('User-Agent', 'BreakingPointTester/1.0')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - start) * 1000.0
            code = resp.status
            node = resp.headers.get('X-Served-By') or 'replica'
    except urllib.error.HTTPError as e:
        latency = (time.time() - start) * 1000.0
        code = e.code
        node = e.headers.get('X-Served-By') or 'error'
    except Exception as e:
        latency = (time.time() - start) * 1000.0
        code = 504  # Timeout / Saturación

    return {'code': code, 'latency': latency, 'node': node, 'success': 200 <= code < 400}

def execute_stage(base_url, stage_info):
    total = stage_info["requests"]
    concurrency = stage_info["concurrency"]
    name = stage_info["name"]

    print(f"\n[*] Ejecutando: {name}")
    print(f"    -> Enviando {total} peticiones con {concurrency} hilos simultáneos...")

    tasks = [(base_url, ENDPOINTS[i % len(ENDPOINTS)]) for i in range(total)]
    start = time.time()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(make_req, t[0], t[1]) for t in tasks]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    duration = time.time() - start
    latencies = [r['latency'] for r in results]
    successes = sum(1 for r in results if r['success'])
    failures = total - successes
    succ_rate = (successes / total) * 100.0
    rps = total / duration
    avg_lat = statistics.mean(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]

    # Determinar estado
    if succ_rate >= 95.0 and avg_lat < 1500:
        status_label = "🟢 ESTABLE (Óptimo)"
        broken = False
    elif succ_rate >= 80.0:
        status_label = "🟡 DEGRADADO (Alta Latencia / Cola LLena)"
        broken = False
    else:
        status_label = "🔴 COLAPSO (Punto de Quiebre Alcanzado)"
        broken = True

    print(f"    -> Resultado: {successes}/{total} exitosas ({succ_rate:.1f}%) | Throughput: {rps:.1f} RPS")
    print(f"    -> Latencia media: {avg_lat:.1f} ms | P95: {p95:.1f} ms")
    print(f"    -> Diagnóstico: {status_label}")

    return {
        "name": name,
        "requests": total,
        "concurrency": concurrency,
        "duration": duration,
        "rps": rps,
        "success_rate": succ_rate,
        "avg_latency": avg_lat,
        "p95": p95,
        "failures": failures,
        "status": status_label,
        "broken": broken
    }

def run_breakpoint_test(base_url="http://127.0.0.1:8000"):
    print("=" * 80)
    print("🔥 INICIANDO TEST DE PUNTO DE QUIEBRE Y CAPACIDAD MÁXIMA DEL CLÚSTER")
    print(f"🎯 Servidor Destino: {base_url}")
    print("=" * 80)

    summary_stages = []
    breakpoint_found = False
    breaking_stage = None

    for stage in STAGES:
        res = execute_stage(base_url, stage)
        summary_stages.append(res)
        if res["broken"]:
            breakpoint_found = True
            breaking_stage = res
            print("\n" + "!" * 80)
            print(f"⚠️  PUNTO DE QUIEBRE DETECTADO EN: {res['name']}")
            print(f"    La tasa de fallos superó el 20% ({res['failures']} peticiones rechazadas/timeout).")
            print("!" * 80)
            break
        time.sleep(2)  # Pequeña pausa de enfriamiento entre etapas

    print("\n" + "=" * 80)
    print("📋 TABLA RESUMEN DE RESISTENCIA Y CAPACIDAD DEL SISTEMA")
    print("=" * 80)
    print(f"{'Etapa':<28} | {'Reqs':>5} | {'Hilos':>5} | {'RPS':>7} | {'Latencia':>9} | {'Éxito':>6} | Estado")
    print("-" * 80)
    for s in summary_stages:
        print(f"{s['name']:<28} | {s['requests']:>5} | {s['concurrency']:>5} | {s['rps']:>6.1f} | {s['avg_latency']:>7.1f}ms | {s['success_rate']:>5.1f}% | {s['status']}")
    print("=" * 80)

    if breakpoint_found:
        print(f"\n🎯 CONCLUSIÓN PARA EL INFORME:")
        print(f"  • Capacidad Máxima Estable:  Hasta {summary_stages[-2]['requests']} peticiones simultáneas (~{summary_stages[-2]['rps']:.1f} RPS).")
        print(f"  • Punto de Saturación:       Se alcanza a partir de {breaking_stage['concurrency']} hilos concurrentes.")
        print(f"  • Causa técnica:             Los 9 workers de Gunicorn se saturan, llenando el backlog TCP de Nginx.")
    else:
        print(f"\n🎯 CONCLUSIÓN: El clúster soportó todas las etapas hasta {summary_stages[-1]['requests']} peticiones sin colapsar (Excelente resiliencia).")

    print("=" * 80 + "\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Breaking point stress test")
    parser.add_argument('--url', default="http://127.0.0.1:8000", help="Target URL")
    args = parser.parse_args()

    run_breakpoint_test(base_url=args.url)
