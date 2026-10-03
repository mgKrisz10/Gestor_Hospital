"""Punto de entrada: python app.py"""
import socket
import threading
import webbrowser

from src.servidor import main

HOST = "127.0.0.1"
PORT = 8000

def puerto_disponible(host: str, inicio: int, intentos: int = 20) -> int:
    for port in range(inicio, inicio + intentos):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise OSError("No se encontro un puerto disponible en el rango configurado")

if __name__ == "__main__":
    port = puerto_disponible(HOST, PORT)
    url = f"http://{HOST}:{port}/"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    main(HOST, port)
