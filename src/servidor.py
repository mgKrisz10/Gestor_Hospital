"""Servidor local: conserva la API inicial y agrega el MVP del segundo parcial."""
from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .gestor_citas import Cita, HORARIO_LABORAL, buscar_disponibilidad, formatear_hora, resultado_a_dict
from .mvp import HospitalService, ReglaNegocioError

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
DATA = ROOT / 'data' / 'citas_ficticias.json'
SERVICE = None


def cargar_datos():
    return json.loads(DATA.read_text(encoding='utf-8'))


def preparar_respuesta(doctor_id, duracion):
    doctor = next((d for d in cargar_datos()['doctores'] if d['id'] == doctor_id), None)
    if doctor is None:
        return {'ok': False, 'error': 'Doctor no encontrado', 'status': 404}
    try:
        duracion = int(duracion)
    except (ValueError, TypeError):
        return {'ok': False, 'error': 'La duracion debe ser un numero entero', 'status': 400}
    citas = tuple(Cita(int(c['inicio']), int(c['duracion'])) for c in doctor['citas'])
    respuesta = resultado_a_dict(buscar_disponibilidad(citas, HORARIO_LABORAL, duracion))
    respuesta.update({'doctor': {key: doctor[key] for key in ('id','nombre','especialidad')},
        'citas_ocupadas': [{'inicio': c.inicio, 'fin': c.inicio + c.duracion,
            'inicio_texto': formatear_hora(c.inicio), 'fin_texto': formatear_hora(c.inicio + c.duracion)} for c in citas],
        'status': 200 if respuesta['ok'] else 400})
    return respuesta


def servicio():
    global SERVICE
    if SERVICE is None:
        SERVICE = HospitalService()
    return SERVICE


class Handler(BaseHTTPRequestHandler):
    def enviar(self, status, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self._send(status, payload, 'application/json; charset=utf-8')

    def _send(self, status, payload, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        param = lambda name, default='': qs.get(name, [default])[0]
        try:
            if parsed.path == '/api/mvp/doctores':
                return self.enviar(200, {'ok': True, 'doctores': servicio().listar_doctores()})
            if parsed.path == '/api/mvp/disponibilidad':
                data = servicio().disponibilidad(param('doctor'), param('fecha'), param('duracion', '30'))
                return self.enviar(200, data)
            if parsed.path == '/api/mvp/citas':
                return self.enviar(200, {'ok': True, 'citas': servicio().listar_citas(
                    param('fecha') or None, param('doctor') or None)})
            if parsed.path == '/api/doctores':
                return self.enviar(200, [{key: d[key] for key in ('id','nombre','especialidad')}
                                          for d in cargar_datos()['doctores']])
            if parsed.path == '/api/disponibilidad':
                respuesta = preparar_respuesta(param('doctor'), param('duracion', '30'))
                return self.enviar(respuesta.pop('status', 200), respuesta)
            if parsed.path == '/':
                return self._serve_static('mvp.html')
            if parsed.path == '/index.html':
                return self._serve_static('index.html')
            name = parsed.path.lstrip('/')
            if name.startswith('frontend/'):
                name = name[len('frontend/'):]
            return self._serve_static(name)
        except ReglaNegocioError as exc:
            return self.enviar(400, {'ok': False, 'error': str(exc)})
        except Exception as exc:
            print('[ERROR]', repr(exc))
            return self.enviar(500, {'ok': False, 'error': 'Error interno del servidor'})

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith('/api/mvp/citas'):
            return self.enviar(404, {'ok': False, 'error': 'Ruta desconocida'})
        try:
            size = int(self.headers.get('Content-Length', '-1'))
            if size < 0 or size > 4096:
                return self.enviar(413, {'ok': False, 'error': 'El cuerpo JSON es demasiado grande o falta'})
            content = json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(content, dict):
                raise ReglaNegocioError('Se esperaba un objeto JSON')
            if parsed.path == '/api/mvp/citas':
                result = servicio().agendar(content.get('doctor_id'), content.get('fecha'),
                    content.get('inicio'), content.get('duracion'),
                    content.get('paciente_nombre'), content.get('paciente_telefono', ''))
                return self.enviar(201, result)
            parts = parsed.path.strip('/').split('/')
            if len(parts) == 5 and parts[:3] == ['api','mvp','citas']:
                cita_id, accion = parts[3], parts[4]
                if accion == 'cancelar':
                    return self.enviar(200, servicio().cancelar(cita_id))
            return self.enviar(404, {'ok': False, 'error': 'Ruta desconocida'})
        except (ValueError, UnicodeError, json.JSONDecodeError, ReglaNegocioError) as exc:
            return self.enviar(400, {'ok': False, 'error': str(exc)})
        except Exception as exc:
            print('[ERROR]', repr(exc))
            return self.enviar(500, {'ok': False, 'error': 'Error interno del servidor'})

    def _serve_static(self, name):
        path = (FRONTEND / name).resolve()
        if FRONTEND not in path.parents or not path.is_file():
            return self._send(404, b'Not found', 'text/plain; charset=utf-8')
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        return self._send(200, path.read_bytes(), mime + ('; charset=utf-8' if mime.startswith('text/') or mime == 'application/javascript' else ''))

    def log_message(self, fmt, *args):
        print(f'[servidor] {self.address_string()} - {fmt % args}')


def main(host='127.0.0.1', port=8000):
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'Gestor de Citas Medicas - Segundo parcial\nhttp://{host}:{port}')
    print('Presiona Ctrl+C para terminar')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
