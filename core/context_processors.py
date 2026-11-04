import os
import socket

SERVER_ID = os.environ.get('SERVER_ID', socket.gethostname())
PROCESS_PID = str(os.getpid())

def server_info(request):
    """Context processor para mostrar en la interfaz la réplica activa del balanceador de carga."""
    return {
        'SERVER_ID': getattr(request, 'server_id', SERVER_ID),
        'PROCESS_PID': getattr(request, 'process_pid', PROCESS_PID),
        'IS_CLUSTERED': os.environ.get('CLUSTERED', 'True').lower() in ('true', '1'),
    }
