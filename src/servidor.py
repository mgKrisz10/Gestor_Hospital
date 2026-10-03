"""Servidor web local sin dependencias externas."""
from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .gestor_citas import Cita, HORARIO_LABORAL, buscar_disponibilidad, formatear_hora, resultado_a_dict

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DATA = ROOT / "data" / "citas_ficticias.json"


def cargar_datos() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def obtener_doctor(doctor_id: str) -> dict | None:
    return next((d for d in cargar_datos()["doctores"] if d["id"] == doctor_id), None)


def preparar_respuesta(doctor_id: str, duracion: int) -> dict:
    doctor = obtener_doctor(doctor_id)
    if doctor is None:
        return {"ok": False, "error": "Doctor no encontrado", "status": 404}

    try:
        duracion_int = int(duracion)
    except (TypeError, ValueError):
        return {"ok": False, "error": "La duracion debe ser un numero entero", "status": 400}

    citas = tuple(Cita(int(c["inicio"]), int(c["duracion"])) for c in doctor["citas"])
    resultado = resultado_a_dict(buscar_disponibilidad(citas, HORARIO_LABORAL, duracion_int))
    resultado.update(
        {
            "doctor": {
                "id": doctor["id"],
                "nombre": doctor["nombre"],
                "especialidad": doctor["especialidad"],
            },
            "citas_ocupadas": [
                {
                    "inicio": c.inicio,
                    "fin": c.inicio + c.duracion,
                    "inicio_texto": formatear_hora(c.inicio),
                    "fin_texto": formatear_hora(c.inicio + c.duracion),
                }
                for c in citas
            ],
            "status": 200,
        }
    )
    return resultado


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/doctores":
            datos = [
                {"id": d["id"], "nombre": d["nombre"], "especialidad": d["especialidad"]}
                for d in cargar_datos()["doctores"]
            ]
            self._send(200, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return

        if parsed.path == "/api/disponibilidad":
            params = parse_qs(parsed.query)
            doctor_id = params.get("doctor", [""])[0]
            duracion = params.get("duracion", ["30"])[0]
            result = preparar_respuesta(doctor_id, duracion)
            self._send(result.pop("status", 200), json.dumps(result, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            return

        if parsed.path == "/" or parsed.path == "/index.html":
            self._serve_static("index.html")
            return

        safe_name = parsed.path.lstrip("/")
        if safe_name.startswith("frontend/"):
            safe_name = safe_name[len("frontend/"):]
        if safe_name:
            self._serve_static(safe_name)
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def _serve_static(self, name: str) -> None:
        path = (FRONTEND / name).resolve()
        if FRONTEND not in path.parents and path != FRONTEND:
            self._send(403, b"Forbidden", "text/plain; charset=utf-8")
            return
        if not path.is_file():
            self._send(404, b"File not found", "text/plain; charset=utf-8")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)

    def log_message(self, format: str, *args) -> None:
        print(f"[servidor] {self.address_string()} - {format % args}")


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print("Gestor de Citas Medicas")
    print(f"Servidor iniciado en http://{host}:{port}")
    print("Presiona Ctrl+C para detenerlo.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()
