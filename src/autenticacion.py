"""Autenticación y permisos para las cuentas de prueba.

Las contraseñas se guardan mediante PBKDF2-HMAC-SHA256 y las sesiones en memoria.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .mvp import ReglaNegocioError

ROLES = ('administrador', 'doctor', 'paciente', 'recepcion', 'personal_autorizado')
SESION_SEGUNDOS = 60 * 60 * 2
ITERACIONES = 210_000


class AccesoDenegado(PermissionError):
    pass


class SinSesion(AccesoDenegado):
    pass


@dataclass(frozen=True)
class Usuario:
    id: int
    usuario: str
    nombre: str
    rol: str
    doctor_id: str | None
    paciente_id: int | None


class AutenticacionService:
    """Una cuenta tiene exactamente un perfil y vínculos de agenda cuando aplica."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._sesiones: dict[str, tuple[int, float]] = {}
        self._inicializar()

    def _con(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys = ON')
        return con

    @staticmethod
    def _hash(password: str, salt: bytes):
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERACIONES)

    def _inicializar(self):
        with self._con() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                rol TEXT NOT NULL CHECK (rol IN
                    ('administrador','doctor','paciente','recepcion','personal_autorizado')),
                salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                doctor_id TEXT REFERENCES doctores(id),
                paciente_id INTEGER REFERENCES pacientes(id),
                activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)))''')
            existentes = con.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]
            if existentes:
                return
            # Un paciente ficticio vinculado a una cuenta; las otras citas pueden
            # registrarse para pacientes sin cuenta y no serán visibles en ella.
            patient_id = con.execute(
                'INSERT INTO pacientes(nombre,telefono) VALUES (?,?)',
                ('Paciente Demo', '5500000000')).lastrowid
            perfiles = [
                ('admin', 'Administración', 'administrador', None, None),
                ('doctora', 'Dra. Ana López', 'doctor', 'MED001', None),
                ('paciente', 'Paciente Demo', 'paciente', None, patient_id),
                ('recepcion', 'Personal de recepción', 'recepcion', None, None),
                ('consulta', 'Personal autorizado', 'personal_autorizado', None, None),
            ]
            for login, nombre, rol, doctor_id, paciente in perfiles:
                salt = secrets.token_bytes(16)
                con.execute('''INSERT INTO usuarios
                    (usuario,nombre,rol,salt,password_hash,doctor_id,paciente_id)
                    VALUES (?,?,?,?,?,?,?)''',
                    (login, nombre, rol, salt, self._hash('Demo2026!', salt), doctor_id, paciente))

    @staticmethod
    def _public(row: sqlite3.Row):
        return Usuario(row['id'], row['usuario'], row['nombre'], row['rol'],
                       row['doctor_id'], row['paciente_id'])

    def login(self, usuario: str, password: str):
        if not isinstance(usuario, str) or not isinstance(password, str):
            raise SinSesion('Usuario o contraseña incorrectos')
        with self._con() as con:
            row = con.execute('SELECT * FROM usuarios WHERE usuario=? AND activo=1',
                              (usuario.strip().lower(),)).fetchone()
        # Mismo mensaje para no revelar qué cuenta existe.
        if row is None or not hmac.compare_digest(self._hash(password, row['salt']), row['password_hash']):
            raise SinSesion('Usuario o contraseña incorrectos')
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sesiones[token] = (row['id'], time.monotonic() + SESION_SEGUNDOS)
        return {'ok': True, 'token': token, 'usuario': asdict(self._public(row))}

    def validar(self, token: str | None) -> Usuario:
        if not token:
            raise SinSesion('Inicia sesión para continuar')
        with self._lock:
            entry = self._sesiones.get(token)
            if entry is None:
                raise SinSesion('Sesión inválida; vuelve a iniciar sesión')
            user_id, vence = entry
            if time.monotonic() >= vence:
                del self._sesiones[token]
                raise SinSesion('La sesión expiró; inicia sesión nuevamente')
        with self._con() as con:
            row = con.execute('SELECT * FROM usuarios WHERE id=? AND activo=1',
                              (user_id,)).fetchone()
        if row is None:
            self.logout(token)
            raise SinSesion('Usuario desactivado')
        return self._public(row)

    def logout(self, token: str | None):
        with self._lock:
            self._sesiones.pop(token or '', None)
        return {'ok': True}

    @staticmethod
    def exigir(user: Usuario, *roles: str):
        if user.rol not in roles:
            raise AccesoDenegado('No tienes permiso para realizar esta operación')

    def usuarios(self):
        """Ningún campo de contraseña o token se expone en esta consulta."""
        with self._con() as con:
            rows = con.execute('''SELECT id,usuario,nombre,rol,doctor_id,paciente_id,activo
                                  FROM usuarios ORDER BY id''').fetchall()
        return [dict(row) for row in rows]
