"""
Clúster Local de Escalamiento Horizontal y Balanceo de Carga Multi-Instancia
Permite ejecutar y demostrar el balanceo de carga sin necesidad de Docker:
- Instancia Réplica 1: http://localhost:8001 (backend-node-1)
- Instancia Réplica 2: http://localhost:8002 (backend-node-2)
- Instancia Réplica 3: http://localhost:8003 (backend-node-3)
- Balanceador de Carga Round-Robin: http://localhost:8000
"""

import subprocess
import sys
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

BACKEND_NODES = [
    {"port": 8001, "server_id": "backend-replica-1"},
    {"port": 8002, "server_id": "backend-replica-2"},
    {"port": 8003, "server_id": "backend-replica-3"},
]

current_node_index = 0
lock = threading.Lock()

def get_next_node():
    global current_node_index
    with lock:
        node = BACKEND_NODES[current_node_index]
        current_node_index = (current_node_index + 1) % len(BACKEND_NODES)
        return node

class LoadBalancerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.proxy_request('GET')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else None
        self.proxy_request('POST', body=post_data)

    def proxy_request(self, method, body=None):
        target_node = get_next_node()
        target_url = f"http://127.0.0.1:{target_node['port']}{self.path}"

        req = urllib.request.Request(target_url, data=body, method=method)
        for header, value in self.headers.items():
            if header.lower() not in ['host', 'content-length']:
                req.add_header(header, value)

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                self.send_response(response.status)
                for header, value in response.getheaders():
                    if header.lower() not in ['transfer-encoding', 'connection']:
                        self.send_header(header, value)
                self.send_header('X-Load-Balancer', 'Local-Round-Robin')
                self.send_header('X-Upstream-Node', target_node['server_id'])
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for header, value in e.headers.items():
                if header.lower() not in ['transfer-encoding', 'connection']:
                    self.send_header(header, value)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"502 Bad Gateway - Error comunicando con réplica {target_node['server_id']}: {e}".encode())

def start_worker(port, server_id):
    env = os.environ.copy()
    env['SERVER_ID'] = server_id
    env['CLUSTERED'] = 'True'
    cmd = [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"]
    return subprocess.Popen(cmd, env=env)

def main():
    print("=" * 70)
    print("🚀 INICIANDO CLÚSTER LOCAL DE ESCALAMIENTO HORIZONTAL (3 RÉPLICAS)")
    print("=" * 70)

    workers = []
    for node in BACKEND_NODES:
        print(f"[*] Levantando réplica: {node['server_id']} en http://127.0.0.1:{node['port']} ...")
        proc = start_worker(node['port'], node['server_id'])
        workers.append(proc)

    time.sleep(2)
    lb_port = 8000
    server_address = ('127.0.0.1', lb_port)
    httpd = HTTPServer(server_address, LoadBalancerHandler)

    print("\n" + "=" * 70)
    print(f"✔ BALANCEADOR DE CARGA ACTIVO EN: http://127.0.0.1:{lb_port}")
    print(f"✔ Estrategia: Round-Robin entre las 3 réplicas")
    print(f"✔ Presione Ctrl + C para detener el clúster")
    print("=" * 70 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Apagando clúster de réplicas...")
        for proc in workers:
            proc.terminate()
        httpd.server_close()
        print("[DONE] Clúster detenido.")

if __name__ == '__main__':
    main()
