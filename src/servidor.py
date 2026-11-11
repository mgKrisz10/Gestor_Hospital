"""Servidor HTTP del gestor de citas."""
from __future__ import annotations

import json
import mimetypes
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .autenticacion import AutenticacionService, AccesoDenegado, SinSesion
from .gestor_citas import Cita, HORARIO_LABORAL, buscar_disponibilidad, formatear_hora, resultado_a_dict
from .mvp import HospitalService, ReglaNegocioError

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
DATA = ROOT / 'data' / 'citas_ficticias.json'
SERVICE = None
AUTH = None


def servicio():
    global SERVICE
    if SERVICE is None:
        SERVICE = HospitalService()
    return SERVICE


def autenticacion():
    global AUTH
    if AUTH is None:
        AUTH = AutenticacionService(servicio().db_path)
    return AUTH


def datos_ejemplo():
    return json.loads(DATA.read_text(encoding='utf-8'))


def disponibilidad_etapa_1(doctor_id, duracion):
    """API histórica del primer parcial: solo datos ficticios del JSON."""
    doctor = next((d for d in datos_ejemplo()['doctores'] if d['id'] == doctor_id), None)
    if doctor is None:
        raise ReglaNegocioError('Doctor no encontrado')
    try:
        duracion = int(duracion)
    except (ValueError, TypeError) as exc:
        raise ReglaNegocioError('La duración debe ser un número entero') from exc
    citas = tuple(Cita(int(c['inicio']), int(c['duracion'])) for c in doctor['citas'])
    result = resultado_a_dict(buscar_disponibilidad(citas, HORARIO_LABORAL, duracion))
    result.update({'doctor': {k: doctor[k] for k in ('id','nombre','especialidad')},
                   'citas_ocupadas': [{'inicio': c.inicio, 'fin': c.inicio+c.duracion,
                       'inicio_texto': formatear_hora(c.inicio),
                       'fin_texto': formatear_hora(c.inicio+c.duracion)} for c in citas]})
    return result


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload, content_type):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(payload)

    def enviar(self, status, obj):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode('utf-8'),
                   'application/json; charset=utf-8')

    def _token(self):
        authorization = self.headers.get('Authorization', '')
        return authorization[7:].strip() if authorization.startswith('Bearer ') else None

    def _usuario(self):
        return autenticacion().validar(self._token())

    def _error(self, exc):
        if isinstance(exc, SinSesion):
            return self.enviar(401, {'ok':False, 'error':str(exc)})
        if isinstance(exc, AccesoDenegado):
            return self.enviar(403, {'ok':False, 'error':str(exc)})
        if isinstance(exc, (ReglaNegocioError, ValueError, UnicodeError, json.JSONDecodeError)):
            return self.enviar(400, {'ok':False, 'error':str(exc)})
        print('[ERROR]', repr(exc))
        return self.enviar(500, {'ok':False, 'error':'Error interno del servidor'})

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        param = lambda name, default='': qs.get(name, [default])[0]
        try:
            if parsed.path.startswith('/api/mvp/'):
                usuario = self._usuario()
                auth = autenticacion()
                svc = servicio()
                if parsed.path == '/api/mvp/auth/me':
                    return self.enviar(200, {'ok':True, 'usuario':asdict(usuario)})
                if parsed.path == '/api/mvp/doctores':
                    return self.enviar(200, {'ok':True, 'doctores':svc.listar_doctores()})
                if parsed.path == '/api/mvp/disponibilidad':
                    doctor_id = param('doctor')
                    if usuario.rol == 'doctor' and doctor_id != usuario.doctor_id:
                        raise AccesoDenegado('Solo puedes consultar la disponibilidad propia')
                    return self.enviar(200,svc.disponibilidad(doctor_id,param('fecha'),param('duracion','30')))
                if parsed.path == '/api/mvp/citas':
                    auth.exigir(usuario,'administrador','recepcion','doctor','paciente')
                    doctor_id = param('doctor') or None
                    if usuario.rol == 'doctor':
                        doctor_id = usuario.doctor_id
                    citas = svc.listar_citas(param('fecha') or None, doctor_id)
                    if usuario.rol == 'paciente':
                        citas = [c for c in citas if c['paciente_id'] == usuario.paciente_id]
                    return self.enviar(200, {'ok':True, 'citas':citas})
                if parsed.path == '/api/mvp/usuarios':
                    auth.exigir(usuario,'administrador')
                    return self.enviar(200, {'ok':True,'usuarios':auth.usuarios()})
                if parsed.path == '/api/mvp/resumen':
                    auth.exigir(usuario,'administrador')
                    return self.enviar(200, {'ok':True, 'resumen':svc.resumen()})
                if parsed.path == '/api/mvp/paciente-demo':
                    auth.exigir(usuario,'recepcion','administrador')
                    # Identificador del paciente ficticio ligado a una cuenta de demostración.
                    demo = next(u for u in auth.usuarios() if u['usuario']=='paciente')
                    return self.enviar(200, {'ok':True,'paciente':{'id':demo['paciente_id'],
                                                        'nombre':demo['nombre']}})
                return self.enviar(404, {'ok':False, 'error':'Ruta desconocida'})
            if parsed.path == '/api/doctores':
                return self.enviar(200,[{k:d[k] for k in ('id','nombre','especialidad')}
                                       for d in datos_ejemplo()['doctores']])
            if parsed.path == '/api/disponibilidad':
                return self.enviar(200,disponibilidad_etapa_1(param('doctor'),param('duracion','30')))
            if parsed.path in ('/','/mvp.html'):
                return self._static('mvp.html')
            if parsed.path == '/index.html':
                return self._static('index.html')
            name = parsed.path.lstrip('/')
            if name.startswith('frontend/'):
                name=name[len('frontend/'):]
            return self._static(name)
        except Exception as exc:
            self._error(exc)

    def _json(self):
        size = int(self.headers.get('Content-Length','-1'))
        if size < 0 or size > 8192:
            raise ReglaNegocioError('JSON inválido o demasiado grande')
        payload = json.loads(self.rfile.read(size).decode('utf-8'))
        if not isinstance(payload, dict):
            raise ReglaNegocioError('Se esperaba un objeto JSON')
        return payload

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == '/api/mvp/auth/login':
                data=self._json()
                return self.enviar(200,autenticacion().login(data.get('usuario'), data.get('password')))
            if not parsed.path.startswith('/api/mvp/'):
                return self.enviar(404,{'ok':False,'error':'Ruta desconocida'})
            usuario=self._usuario()
            auth=autenticacion()
            svc=servicio()
            data=self._json()
            if parsed.path == '/api/mvp/auth/logout':
                return self.enviar(200, auth.logout(self._token()))
            if parsed.path == '/api/mvp/citas':
                auth.exigir(usuario,'administrador','recepcion')
                return self.enviar(201,svc.agendar(data.get('doctor_id'),data.get('fecha'),
                    data.get('inicio'),data.get('duracion'),data.get('paciente_nombre'),
                    data.get('paciente_telefono',''),data.get('paciente_id')))
            if parsed.path == '/api/mvp/doctores':
                auth.exigir(usuario,'administrador')
                return self.enviar(201,svc.registrar_doctor(data.get('id'),
                                   data.get('nombre'),data.get('especialidad')))
            parts=parsed.path.strip('/').split('/')
            if len(parts)==5 and parts[:3]==['api','mvp','citas'] and parts[4]=='cancelar':
                auth.exigir(usuario,'administrador','recepcion')
                return self.enviar(200,svc.cancelar(parts[3]))
            return self.enviar(404,{'ok':False,'error':'Ruta desconocida'})
        except Exception as exc:
            self._error(exc)

    def _static(self, name):
        path=(FRONTEND/name).resolve()
        if path == FRONTEND or FRONTEND not in path.parents or not path.is_file():
            return self._send(404,b'Not found','text/plain; charset=utf-8')
        mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if mime.startswith('text/') or mime in ('application/javascript','text/javascript'):
            mime+='; charset=utf-8'
        return self._send(200,path.read_bytes(),mime)

    def log_message(self, fmt, *args):
        print(f'[servidor] {self.address_string()} - {fmt % args}')


def main(host='127.0.0.1',port=8000):
    server=ThreadingHTTPServer((host,port),Handler)
    print('MedAgenda - Gestor de citas médicas')
    print(f'Servidor: http://{host}:{port}')
    print('Ctrl+C para detener el servidor.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
