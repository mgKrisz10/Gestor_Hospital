"""MVP de citas: reglas, modelos y persistencia SQLite sin dependencias externas."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from .gestor_citas import Cita, Error, HORARIO_LABORAL, buscar_disponibilidad, formatear_hora

ROOT = Path(__file__).resolve().parents[1]


class ReglaNegocioError(ValueError):
    """Error de validación que puede mostrarse a quien utiliza el sistema."""


@dataclass(frozen=True)
class Doctor:
    id: str
    nombre: str
    especialidad: str


@dataclass(frozen=True)
class Paciente:
    id: int
    nombre: str
    telefono: str


@dataclass(frozen=True)
class CitaMedica:
    id: int
    doctor_id: str
    paciente_id: int
    fecha: str
    inicio: int
    duracion: int
    estado: str


class HospitalService:
    """Operaciones de consulta, registro y cancelación del MVP."""

    def __init__(self, db_path: str | Path | None = None, doctores_path: str | Path | None = None):
        self.db_path = str(db_path or ROOT / 'data' / 'hospital.sqlite3')
        self.doctores_path = Path(doctores_path or ROOT / 'data' / 'citas_ficticias.json')
        self._inicializar()

    @contextmanager
    def _conexion(self):
        con = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute('PRAGMA foreign_keys = ON')
            con.execute('PRAGMA busy_timeout = 10000')
            yield con
        finally:
            con.close()

    def _inicializar(self):
        with self._conexion() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS doctores (
                    id TEXT PRIMARY KEY, nombre TEXT NOT NULL, especialidad TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pacientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, telefono TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS citas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id TEXT NOT NULL REFERENCES doctores(id),
                    paciente_id INTEGER NOT NULL REFERENCES pacientes(id),
                    fecha TEXT NOT NULL, inicio INTEGER NOT NULL, duracion INTEGER NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'programada'
                       CHECK (estado IN ('programada', 'cancelada')));
                CREATE INDEX IF NOT EXISTS idx_citas_agenda ON citas(doctor_id, fecha, estado, inicio);
            ''')
            datos = json.loads(self.doctores_path.read_text(encoding='utf-8'))
            con.executemany('INSERT OR IGNORE INTO doctores(id,nombre,especialidad) VALUES (?,?,?)',
                [(d['id'], d['nombre'], d['especialidad']) for d in datos['doctores']])

    @staticmethod
    def _fecha(valor):
        if not isinstance(valor, str):
            raise ReglaNegocioError('La fecha debe tener formato AAAA-MM-DD')
        try:
            parsed = date.fromisoformat(valor)
        except ValueError as exc:
            raise ReglaNegocioError('Fecha inválida; utiliza AAAA-MM-DD') from exc
        if parsed.isoformat() != valor:
            raise ReglaNegocioError('La fecha debe tener formato AAAA-MM-DD')
        return valor

    @staticmethod
    def _entero(valor, nombre):
        if isinstance(valor, bool):
            raise ReglaNegocioError(f'{nombre} debe ser un número entero')
        try:
            numero = int(valor)
        except (ValueError, TypeError) as exc:
            raise ReglaNegocioError(f'{nombre} debe ser un número entero') from exc
        if str(valor).strip() != str(numero):
            raise ReglaNegocioError(f'{nombre} debe ser un número entero')
        return numero

    def listar_doctores(self):
        with self._conexion() as con:
            return [asdict(Doctor(**dict(r))) for r in con.execute('SELECT * FROM doctores ORDER BY id')]

    @staticmethod
    def _validar_horario(inicio, duracion):
        if duracion <= 0 or duracion > HORARIO_LABORAL.fin - HORARIO_LABORAL.inicio:
            raise ReglaNegocioError('Duración fuera del horario laboral')
        if inicio < HORARIO_LABORAL.inicio or inicio + duracion > HORARIO_LABORAL.fin:
            raise ReglaNegocioError('La cita debe estar entre 08:00 y 14:00')

    @staticmethod
    def _doctor_existe(con, doctor_id):
        if con.execute('SELECT 1 FROM doctores WHERE id = ?', (doctor_id,)).fetchone() is None:
            raise ReglaNegocioError('Doctor no encontrado')

    @staticmethod
    def _ocupadas(con, doctor_id, fecha, excluir_id=None):
        sql = '''SELECT inicio,duracion FROM citas
                 WHERE doctor_id=? AND fecha=? AND estado='programada' '''
        args = [doctor_id, fecha]
        if excluir_id is not None:
            sql += ' AND id<>?'
            args.append(excluir_id)
        sql += ' ORDER BY inicio'
        return tuple(Cita(r['inicio'], r['duracion']) for r in con.execute(sql, args))

    @staticmethod
    def _conflicto(citas, inicio, duracion):
        return any(inicio < c.inicio + c.duracion and c.inicio < inicio + duracion for c in citas)

    def disponibilidad(self, doctor_id, fecha, duracion):
        fecha = self._fecha(fecha)
        duracion = self._entero(duracion, 'Duración')
        self._validar_horario(HORARIO_LABORAL.inicio, duracion)
        with self._conexion() as con:
            self._doctor_existe(con, doctor_id)
            citas = self._ocupadas(con, doctor_id, fecha)
        resultado = buscar_disponibilidad(citas, HORARIO_LABORAL, duracion)
        if isinstance(resultado, Error):
            raise ReglaNegocioError(resultado.mensaje)
        return {
            'ok': True, 'doctor_id': doctor_id, 'fecha': fecha, 'duracion': duracion,
            'intervalos': [dict(inicio=i.inicio, fin=i.fin,
                                texto=f'{formatear_hora(i.inicio)} - {formatear_hora(i.fin)}')
                           for i in resultado.valor],
            'citas_ocupadas': [dict(inicio=c.inicio, fin=c.inicio+c.duracion) for c in citas],
        }

    @staticmethod
    def _cita_dict(row):
        return dict(row) if row else None

    def listar_citas(self, fecha=None, doctor_id=None):
        sql = '''SELECT c.id,c.fecha,c.inicio,c.duracion,c.estado,c.doctor_id,
                        d.nombre AS doctor_nombre, p.id AS paciente_id,
                        p.nombre AS paciente_nombre, p.telefono AS paciente_telefono
                 FROM citas c JOIN doctores d ON d.id=c.doctor_id
                 JOIN pacientes p ON p.id=c.paciente_id WHERE 1=1'''
        args = []
        if fecha is not None:
            sql += ' AND c.fecha=?'
            args.append(self._fecha(fecha))
        if doctor_id:
            sql += ' AND c.doctor_id=?'
            args.append(doctor_id)
        sql += ' ORDER BY c.fecha,c.inicio,c.id'
        with self._conexion() as con:
            return [self._cita_dict(row) for row in con.execute(sql, args)]

    @staticmethod
    def _obtener_cita(con, cita_id):
        row = con.execute('SELECT * FROM citas WHERE id=?', (cita_id,)).fetchone()
        if row is None:
            raise ReglaNegocioError('Cita no encontrada')
        if row['estado'] != 'programada':
            raise ReglaNegocioError('La cita ya está cancelada')
        return row

    def registrar_doctor(self, doctor_id, nombre, especialidad):
        doctor_id = str(doctor_id or '').strip().upper()
        nombre = str(nombre or '').strip()
        especialidad = str(especialidad or '').strip()
        if not (3 <= len(doctor_id) <= 12) or not doctor_id.isalnum():
            raise ReglaNegocioError('ID del médico: 3-12 letras o números')
        if not (3 <= len(nombre) <= 120) or not (3 <= len(especialidad) <= 100):
            raise ReglaNegocioError('Nombre y especialidad deben tener al menos 3 caracteres')
        with self._conexion() as con:
            try:
                con.execute('INSERT INTO doctores VALUES (?,?,?)', (doctor_id, nombre, especialidad))
            except sqlite3.IntegrityError as exc:
                raise ReglaNegocioError('Ya existe un médico con ese ID') from exc
        return {'ok': True, 'doctor': asdict(Doctor(doctor_id, nombre, especialidad))}

    def resumen(self):
        with self._conexion() as con:
            return {'doctores': con.execute('SELECT COUNT(*) FROM doctores').fetchone()[0],
                    'pacientes': con.execute('SELECT COUNT(*) FROM pacientes').fetchone()[0],
                    'citas_programadas': con.execute("SELECT COUNT(*) FROM citas WHERE estado='programada'").fetchone()[0],
                    'citas_canceladas': con.execute("SELECT COUNT(*) FROM citas WHERE estado='cancelada'").fetchone()[0]}

    def agendar(self, doctor_id, fecha, inicio, duracion, paciente_nombre='', paciente_telefono='', paciente_id=None):
        fecha = self._fecha(fecha)
        inicio = self._entero(inicio, 'Inicio')
        duracion = self._entero(duracion, 'Duración')
        self._validar_horario(inicio, duracion)
        nombre = str(paciente_nombre or '').strip()
        telefono = str(paciente_telefono or '').strip()
        if paciente_id is not None:
            paciente_id = self._entero(paciente_id, 'Paciente')
        if paciente_id is None and (len(nombre) < 2 or len(nombre) > 120):
            raise ReglaNegocioError('Escribe el nombre del paciente (2-120 caracteres)')
        if len(telefono) > 30:
            raise ReglaNegocioError('El teléfono supera los 30 caracteres')
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                self._doctor_existe(con, doctor_id)
                if self._conflicto(self._ocupadas(con, doctor_id, fecha), inicio, duracion):
                    raise ReglaNegocioError('Horario ocupado: existe otra cita para ese médico')
                if paciente_id is None:
                    paciente_id = con.execute('INSERT INTO pacientes(nombre,telefono) VALUES (?,?)',
                                              (nombre, telefono)).lastrowid
                elif con.execute('SELECT 1 FROM pacientes WHERE id=?', (paciente_id,)).fetchone() is None:
                    raise ReglaNegocioError('Paciente no encontrado')
                cita_id = con.execute('''INSERT INTO citas(doctor_id,paciente_id,fecha,inicio,duracion)
                                         VALUES (?,?,?,?,?)''',
                                      (doctor_id, paciente_id, fecha, inicio, duracion)).lastrowid
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return {'ok': True, 'id': cita_id, 'paciente_id': paciente_id, 'estado': 'programada'}

    def cancelar(self, cita_id):
        cita_id = self._entero(cita_id, 'ID de cita')
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                self._obtener_cita(con, cita_id)
                con.execute("UPDATE citas SET estado='cancelada' WHERE id=?", (cita_id,))
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return {'ok': True, 'id': cita_id, 'estado': 'cancelada'}

