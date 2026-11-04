"""
Middleware para identificación de instancias en arquitecturas de escalamiento horizontal y balanceo de carga.
Agrega las cabeceras HTTP:
- X-Served-By: Hostname o ID de la réplica que procesó la solicitud.
- X-Process-PID: Identificador del proceso del sistema operativo.
"""

import os
import socket

SERVER_ID = os.environ.get('SERVER_ID', socket.gethostname())
PROCESS_PID = str(os.getpid())

class ServerIdentityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.server_name = SERVER_ID
        self.pid = PROCESS_PID

    def __call__(self, request):
        request.server_id = self.server_name
        request.process_pid = self.pid

        response = self.get_response(request)

        # Inyectar cabeceras en cada respuesta HTTP para verificación del balanceador de carga
        response['X-Served-By'] = self.server_name
        response['X-Process-PID'] = self.pid
        return response
