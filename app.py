"""Inicia el servidor del hospital."""
import socket
import threading
import webbrowser
from src.servidor import main

HOST, PORT = '127.0.0.1', 8000


def puerto_disponible(host, inicio, intentos=20):
    for port in range(inicio, inicio+intentos):
        with socket.socket() as sock:
            try:
                sock.bind((host,port))
                return port
            except OSError:
                continue
    raise OSError('No hay puertos libres entre 8000 y 8019')


if __name__ == '__main__':
    port = puerto_disponible(HOST, PORT)
    threading.Timer(.8, lambda: webbrowser.open(f'http://{HOST}:{port}')).start()
    main(HOST,port)
