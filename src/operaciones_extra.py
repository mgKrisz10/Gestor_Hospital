"""Pacientes, agenda, ausencias, confirmaciones y cambios de horario."""
from __future__ import annotations

import os
import smtplib
import sqlite3
import ssl
from datetime import date, datetime, timezone, timedelta
from email.message import EmailMessage
from dataclasses import asdict

from .gestor_citas import HORARIO_LABORAL, formatear_hora
from .mvp import HospitalService as BaseHospital, Doctor, ReglaNegocioError


class HospitalService(BaseHospital):
    def _inicializar(self):
        super()._inicializar()
        with self._conexion() as con:
            fields = {row['name'] for row in con.execute('PRAGMA table_info(pacientes)')}
            if 'correo' not in fields:
                con.execute("ALTER TABLE pacientes ADD COLUMN correo TEXT NOT NULL DEFAULT ''")
            fields = {row['name'] for row in con.execute('PRAGMA table_info(citas)')}
            if 'cancelacion_motivo' not in fields:
                con.execute("ALTER TABLE citas ADD COLUMN cancelacion_motivo TEXT NOT NULL DEFAULT ''")
            fields = {row['name'] for row in con.execute('PRAGMA table_info(doctores)')}
            if 'activo' not in fields:
                con.execute('ALTER TABLE doctores ADD COLUMN activo INTEGER NOT NULL DEFAULT 1')
            con.executescript('''
                CREATE TABLE IF NOT EXISTS ausencias (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  doctor_id TEXT NOT NULL REFERENCES doctores(id),
                  fecha TEXT NOT NULL, motivo TEXT NOT NULL,
                  creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(doctor_id,fecha)
                );
                CREATE TABLE IF NOT EXISTS notificaciones (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  paciente_id INTEGER NOT NULL REFERENCES pacientes(id),
                  cita_id INTEGER NOT NULL REFERENCES citas(id),
                  tipo TEXT NOT NULL, mensaje TEXT NOT NULL,
                  creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  leida INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_notificaciones_paciente
                  ON notificaciones(paciente_id,creado_en);
                CREATE TABLE IF NOT EXISTS suspensiones_doctor (
                  doctor_id TEXT NOT NULL REFERENCES doctores(id),
                  usuario_id INTEGER NOT NULL ,
                  PRIMARY KEY(doctor_id,usuario_id)
                );
            ''')
        self._actualizar_estados_citas()

    def _actualizar_estados_citas(self):
        # SQLite does not support ALTER TABLE to expand a CHECK constraint.
        # Keep every appointment id and dependent notification in the original database.
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('PRAGMA foreign_keys=OFF')
            schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='citas'").fetchone()['sql']
            if 'pendiente_reagendar' not in schema:
                conn.execute('BEGIN IMMEDIATE')
                try:
                    conn.execute('''CREATE TABLE citas_upgrade (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doctor_id TEXT NOT NULL REFERENCES doctores(id),
                        paciente_id INTEGER NOT NULL REFERENCES pacientes(id),
                        fecha TEXT NOT NULL, inicio INTEGER NOT NULL, duracion INTEGER NOT NULL,
                        estado TEXT NOT NULL DEFAULT 'programada'
                          CHECK(estado IN ('programada','cancelada','pendiente_reagendar')),
                        cancelacion_motivo TEXT NOT NULL DEFAULT ''
                    )''')
                    conn.execute('''INSERT INTO citas_upgrade
                        (id,doctor_id,paciente_id,fecha,inicio,duracion,estado,cancelacion_motivo)
                        SELECT id,doctor_id,paciente_id,fecha,inicio,duracion,estado,
                               cancelacion_motivo FROM citas''')
                    conn.execute('DROP TABLE citas')
                    conn.execute('ALTER TABLE citas_upgrade RENAME TO citas')
                    conn.execute('CREATE INDEX idx_citas_agenda ON citas(doctor_id,fecha,estado,inicio)')
                    conn.execute('COMMIT')
                except Exception:
                    conn.execute('ROLLBACK')
                    raise
            conn.execute('PRAGMA foreign_keys=ON')
            if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise RuntimeError('Citas con referencias inválidas después de migrar')
            # Existing offboarding cancellations scheduled for the future remain actionable.
            conn.execute('''UPDATE citas SET estado='pendiente_reagendar'
                WHERE estado='cancelada' AND cancelacion_motivo='Baja del médico'
                AND fecha>=?''', (self.hoy().isoformat(),))
        finally:
            conn.close()

    @staticmethod
    def ahora():
        # Ciudad de México no usa horario de verano desde 2022 (UTC-06:00).
        # No depender de ZoneInfo: en Windows Python puede no traer tzdata.
        return datetime.now(timezone(timedelta(hours=-6)))

    @classmethod
    def hoy(cls):
        return cls.ahora().date()

    @classmethod
    def _no_pasado(cls, fecha, inicio=None):
        ahora = cls.ahora()
        elegida = date.fromisoformat(fecha)
        if elegida < ahora.date():
            raise ReglaNegocioError('No se pueden agendar citas para fechas anteriores a hoy')
        if elegida == ahora.date() and inicio is not None:
            minutos = ahora.hour * 60 + ahora.minute
            if inicio <= minutos:
                raise ReglaNegocioError('No se pueden agendar citas en horarios que ya pasaron')

    @staticmethod
    def _doctor_existe(con, doctor_id):
        doctor = con.execute('SELECT activo FROM doctores WHERE id=?',(doctor_id,)).fetchone()
        if doctor is None:
            raise ReglaNegocioError('Doctor no encontrado')
        if not doctor['activo']:
            raise ReglaNegocioError('El médico está dado de baja y no admite citas')

    def listar_doctores(self):
        with self._conexion() as con:
            return [dict(r) for r in con.execute('SELECT id,nombre,especialidad FROM doctores WHERE activo=1 ORDER BY id')]

    def _doctor_activo(self, doctor_id):
        with self._conexion() as con:
            row=con.execute('SELECT activo FROM doctores WHERE id=?',(doctor_id,)).fetchone()
            return bool(row and row['activo'])

    def listar_doctores_todos(self):
        with self._conexion() as con:
            return [dict(row) for row in con.execute('''SELECT d.id,d.nombre,d.especialidad,d.activo,
                (SELECT COUNT(*) FROM citas c WHERE c.doctor_id=d.id AND c.estado='programada') citas_programadas
                FROM doctores d ORDER BY d.id''')]

    def directorio_medicos(self):
        with self._conexion() as con:
            return [dict(r) for r in con.execute('''                SELECT d.id,d.nombre,d.especialidad,d.activo,
                    (SELECT COUNT(*) FROM citas c WHERE c.doctor_id=d.id
                        AND c.estado='programada') AS citas_programadas,
                    (SELECT COUNT(*) FROM citas c WHERE c.doctor_id=d.id
                        AND c.estado='pendiente_reagendar') AS citas_por_reagendar
                FROM doctores d ORDER BY d.nombre''')]

    def resumen(self):
        datos=super().resumen()
        with self._conexion() as con:
            datos['citas_pendientes_reagendar'] = con.execute(
                "SELECT COUNT(*) FROM citas WHERE estado='pendiente_reagendar'").fetchone()[0]
        return datos

    def impacto_doctor(self, doctor_id):
        with self._conexion() as con:
            row=con.execute('SELECT id,nombre,especialidad,activo FROM doctores WHERE id=?',(doctor_id,)).fetchone()
            if row is None: raise ReglaNegocioError('Doctor no encontrado')
            cnt=con.execute('''SELECT COUNT(*) total,
                    COALESCE(SUM(CASE WHEN estado='programada' AND fecha>=? THEN 1 ELSE 0 END),0) futuras
                    FROM citas WHERE doctor_id=?''',(self.hoy().isoformat(),doctor_id)).fetchone()
            return {'ok':True,'doctor':dict(row),'citas_historicas':cnt['total'],'citas_por_reagendar':cnt['futuras']}

    def dar_baja_doctor(self, doctor_id):
        hoy=self.hoy().isoformat()
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                self._doctor_existe(con,doctor_id)
                rows=con.execute('''SELECT c.id,c.paciente_id,c.fecha FROM citas c
                    WHERE c.doctor_id=? AND c.estado='programada' AND c.fecha>=?''',
                    (doctor_id,hoy)).fetchall()
                con.execute("UPDATE citas SET estado='pendiente_reagendar',cancelacion_motivo='Baja del médico' "
                            "WHERE doctor_id=? AND estado='programada' AND fecha>=?",(doctor_id,hoy))
                for r in rows:
                    self._avisar(con,r['paciente_id'],r['id'],'baja_medico',
                                f'Cita #{r["id"]} pendiente de reagendar: el médico dejó de prestar servicio.')
                con.execute('UPDATE doctores SET activo=0 WHERE id=?',(doctor_id,))
                # Guardar las cuentas activas suspendidas por esta baja, para restaurar solo esas cuentas.
                con.execute('''INSERT OR IGNORE INTO suspensiones_doctor(doctor_id,usuario_id)
                    SELECT ?,id FROM usuarios WHERE doctor_id=? AND activo=1''',(doctor_id,doctor_id))
                con.execute('UPDATE usuarios SET activo=0 WHERE doctor_id=?',(doctor_id,))
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return {'ok':True,'doctor_id':doctor_id,'pendientes_reagendar':[r['id'] for r in rows],
                'citas_conservadas':True}

    def reactivar_doctor(self, doctor_id):
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                row=con.execute('SELECT activo FROM doctores WHERE id=?',(doctor_id,)).fetchone()
                if row is None: raise ReglaNegocioError('Doctor no encontrado')
                if row['activo']: raise ReglaNegocioError('El médico ya está activo')
                con.execute('UPDATE doctores SET activo=1 WHERE id=?',(doctor_id,))
                con.execute('''UPDATE usuarios SET activo=1 WHERE id IN
                    (SELECT usuario_id FROM suspensiones_doctor WHERE doctor_id=?)''',(doctor_id,))
                con.execute('DELETE FROM suspensiones_doctor WHERE doctor_id=?',(doctor_id,))
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return {'ok':True,'doctor_id':doctor_id,'activo':True}

    def levantar_ausencia(self, ausencia_id):
        ausencia_id=self._entero(ausencia_id,'ID de ausencia')
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                row=con.execute('SELECT doctor_id,fecha FROM ausencias WHERE id=?',(ausencia_id,)).fetchone()
                if row is None: raise ReglaNegocioError('Ausencia no encontrada')
                self._doctor_existe(con,row['doctor_id'])
                con.execute('DELETE FROM ausencias WHERE id=?',(ausencia_id,))
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return {'ok':True,'doctor_id':row['doctor_id'],'fecha':row['fecha'],
                'mensaje':'Médico disponible de nuevo; las citas canceladas no se restauraron'}

    @staticmethod
    def _datos_paciente(nombre, telefono='', correo=''):
        nombre = str(nombre or '').strip()
        telefono = str(telefono or '').strip()
        correo = str(correo or '').strip().lower()
        if not 2 <= len(nombre) <= 120:
            raise ReglaNegocioError('Nombre del paciente: 2 a 120 caracteres')
        if len(telefono) > 30:
            raise ReglaNegocioError('El teléfono no puede superar 30 caracteres')
        if correo and (len(correo) > 254 or '@' not in correo or correo.startswith('@') or correo.endswith('@') or ' ' in correo):
            raise ReglaNegocioError('Correo electrónico inválido')
        return nombre, telefono, correo

    def registrar_paciente(self, nombre, telefono='', correo=''):
        nombre, telefono, correo = self._datos_paciente(nombre, telefono, correo)
        with self._conexion() as con:
            row_id = con.execute('INSERT INTO pacientes(nombre,telefono,correo) VALUES (?,?,?)',
                                 (nombre, telefono, correo)).lastrowid
        return {'ok':True,'paciente':{'id':row_id,'nombre':nombre,'telefono':telefono,'correo':correo}}

    def listar_pacientes(self):
        with self._conexion() as con:
            return [dict(row) for row in con.execute('SELECT id,nombre,telefono,correo FROM pacientes ORDER BY id')]

    @staticmethod
    def _comprobar_asistencia(con, doctor_id, fecha):
        if con.execute('SELECT 1 FROM ausencias WHERE doctor_id=? AND fecha=?', (doctor_id,fecha)).fetchone():
            raise ReglaNegocioError('El médico no estará disponible en esa fecha')

    @staticmethod
    def _avisar(con, paciente_id, cita_id, tipo, mensaje):
        con.execute('INSERT INTO notificaciones(paciente_id,cita_id,tipo,mensaje) VALUES (?,?,?,?)',
                    (paciente_id,cita_id,tipo,mensaje))

    @staticmethod
    def _texto_confirmacion(cita_id, nombre, medico, fecha, inicio, duracion, accion='registrada'):
        return (f'Cita #{cita_id} {accion}. Paciente: {nombre}. Médico: {medico}. '
                f'Fecha: {fecha}. Horario: {formatear_hora(inicio)}–{formatear_hora(inicio+duracion)}.')

    def _intentar_correo(self, email, asunto, mensaje):
        """Opcional: envía correo solo si hay servidor SMTP configurado. No registra contraseñas."""
        host = os.environ.get('MEDAGENDA_SMTP_HOST', '').strip()
        remitente = os.environ.get('MEDAGENDA_SMTP_FROM', '').strip()
        if not host or not remitente or not email:
            return 'no_configurado'
        username = os.environ.get('MEDAGENDA_SMTP_USER', '')
        password = os.environ.get('MEDAGENDA_SMTP_PASSWORD', '')
        try: puerto = int(os.environ.get('MEDAGENDA_SMTP_PORT', '465'))
        except ValueError:
            return 'fallido'
        msg = EmailMessage()
        msg['Subject'] = asunto
        msg['From'] = remitente
        msg['To'] = email
        msg.set_content(mensaje)
        try:
            if puerto == 465:
                with smtplib.SMTP_SSL(host, puerto, timeout=8, context=ssl.create_default_context()) as smtp:
                    if username: smtp.login(username,password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, puerto, timeout=8) as smtp:
                    smtp.starttls(context=ssl.create_default_context())
                    if username: smtp.login(username,password)
                    smtp.send_message(msg)
            return 'enviado'
        except (OSError, smtplib.SMTPException) as exc:
            print('Correo no enviado:', type(exc).__name__)
            return 'fallido'

    def disponibilidad(self, doctor_id, fecha, duracion):
        fecha = self._fecha(fecha)
        with self._conexion() as con:
            self._doctor_existe(con,doctor_id)
            ausencia = con.execute('SELECT motivo FROM ausencias WHERE doctor_id=? AND fecha=?',
                                   (doctor_id,fecha)).fetchone()
        if ausencia:
            # Mantener el contrato de respuesta incluso cuando hay ausencia.
            value = self._entero(duracion, 'Duración')
            self._validar_horario(HORARIO_LABORAL.inicio,value)
            return {'ok':True,'doctor_id':doctor_id,'fecha':fecha,'duracion':value,
                    'intervalos':[],'citas_ocupadas':[],'ausencia':True,'motivo':ausencia['motivo']}
        value = super().disponibilidad(doctor_id,fecha,duracion)
        if date.fromisoformat(fecha) == self.hoy():
            actual = self.ahora()
            minutos = actual.hour * 60 + actual.minute
            value['intervalos'] = [slot for slot in value['intervalos'] if slot['inicio'] > minutos]
        value['ausencia']=False
        return value

    def agendar(self, doctor_id, fecha, inicio, duracion, paciente_nombre='',
                paciente_telefono='', paciente_id=None, paciente_correo=''):
        fecha=self._fecha(fecha)
        inicio=self._entero(inicio,'Inicio')
        self._no_pasado(fecha, inicio)
        duracion=self._entero(duracion,'Duración')
        self._validar_horario(inicio,duracion)
        if paciente_id is None:
            nombre, telefono, correo = self._datos_paciente(paciente_nombre,paciente_telefono,paciente_correo)
        else:
            paciente_id=self._entero(paciente_id,'Paciente')
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                self._doctor_existe(con, doctor_id)
                self._comprobar_asistencia(con,doctor_id,fecha)
                if self._conflicto(self._ocupadas(con,doctor_id,fecha),inicio,duracion):
                    raise ReglaNegocioError('Ese horario ya está ocupado')
                if paciente_id is None:
                    paciente_id=con.execute('INSERT INTO pacientes(nombre,telefono,correo) VALUES (?,?,?)',
                                            (nombre,telefono,correo)).lastrowid
                else:
                    patient=con.execute('SELECT nombre,telefono,correo FROM pacientes WHERE id=?',
                                        (paciente_id,)).fetchone()
                    if patient is None: raise ReglaNegocioError('Paciente no encontrado')
                    nombre,telefono,correo=patient['nombre'],patient['telefono'],patient['correo']
                medico=con.execute('SELECT nombre FROM doctores WHERE id=?',(doctor_id,)).fetchone()['nombre']
                cita_id=con.execute('INSERT INTO citas(doctor_id,paciente_id,fecha,inicio,duracion) VALUES (?,?,?,?,?)',
                                    (doctor_id,paciente_id,fecha,inicio,duracion)).lastrowid
                mensaje=self._texto_confirmacion(cita_id,nombre,medico,fecha,inicio,duracion)
                self._avisar(con,paciente_id,cita_id,'confirmacion',mensaje)
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        envio=self._intentar_correo(correo,'Confirmación de cita',mensaje)
        return {'ok':True,'id':cita_id,'paciente_id':paciente_id,'estado':'programada',
                'confirmacion':mensaje,'correo':envio}

    def reprogramar(self, cita_id, doctor_id, fecha, inicio, duracion):
        cita_id=self._entero(cita_id,'ID de cita')
        fecha=self._fecha(fecha)
        inicio=self._entero(inicio,'Inicio')
        self._no_pasado(fecha, inicio)
        duracion=self._entero(duracion,'Duración')
        self._validar_horario(inicio,duracion)
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                cita=con.execute('SELECT * FROM citas WHERE id=?',(cita_id,)).fetchone()
                if cita is None:
                    raise ReglaNegocioError('Cita no encontrada')
                if cita['estado'] not in ('programada','pendiente_reagendar'):
                    raise ReglaNegocioError('La cita ya está cancelada')
                self._doctor_existe(con,doctor_id)
                self._comprobar_asistencia(con,doctor_id,fecha)
                ocupadas=self._ocupadas(con,doctor_id,fecha,excluir_id=cita_id)
                if self._conflicto(ocupadas,inicio,duracion):
                    raise ReglaNegocioError('El nuevo horario ya está ocupado')
                con.execute("""UPDATE citas SET doctor_id=?,fecha=?,inicio=?,duracion=?,
                            estado='programada',cancelacion_motivo='' WHERE id=?""",
                            (doctor_id,fecha,inicio,duracion,cita_id))
                patient=con.execute('SELECT nombre,correo FROM pacientes WHERE id=?',
                                    (cita['paciente_id'],)).fetchone()
                medico=con.execute('SELECT nombre FROM doctores WHERE id=?',(doctor_id,)).fetchone()['nombre']
                mensaje=self._texto_confirmacion(cita_id,patient['nombre'],medico,fecha,inicio,duracion,'reprogramada')
                self._avisar(con,cita['paciente_id'],cita_id,'reprogramacion',mensaje)
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        estado=self._intentar_correo(patient['correo'],'Cita reprogramada',mensaje)
        return {'ok':True,'id':cita_id,'estado':'programada','confirmacion':mensaje,'correo':estado}

    def cancelar(self, cita_id, motivo='Cancelada por recepción'):
        cita_id=self._entero(cita_id,'ID de cita')
        motivo=str(motivo or '').strip()[:250]
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                cita=self._obtener_cita(con,cita_id)
                con.execute("UPDATE citas SET estado='cancelada',cancelacion_motivo=? WHERE id=?",(motivo,cita_id))
                mensaje=f'Cita #{cita_id} cancelada. {motivo}'
                self._avisar(con,cita['paciente_id'],cita_id,'cancelacion',mensaje)
                patient=con.execute('SELECT correo FROM pacientes WHERE id=?',(cita['paciente_id'],)).fetchone()
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        self._intentar_correo(patient['correo'],'Cita cancelada',mensaje)
        return {'ok':True,'id':cita_id,'estado':'cancelada','confirmacion':mensaje}

    def notificar_ausencia(self, doctor_id, fecha, motivo):
        fecha=self._fecha(fecha)
        self._no_pasado(fecha)
        motivo=str(motivo or '').strip()
        if not 5 <= len(motivo) <= 250:
            raise ReglaNegocioError('Escribe el motivo de ausencia (5 a 250 caracteres)')
        with self._conexion() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                self._doctor_existe(con,doctor_id)
                try:
                    con.execute('INSERT INTO ausencias(doctor_id,fecha,motivo) VALUES (?,?,?)',
                                (doctor_id,fecha,motivo))
                except sqlite3.IntegrityError as exc:
                    raise ReglaNegocioError('La ausencia de ese día ya está registrada') from exc
                rows=con.execute("SELECT id,paciente_id FROM citas WHERE doctor_id=? AND fecha=? AND estado='programada'",
                                 (doctor_id,fecha)).fetchall()
                con.execute("UPDATE citas SET estado='cancelada',cancelacion_motivo='Ausencia del médico' "
                            "WHERE doctor_id=? AND fecha=? AND estado='programada'",(doctor_id,fecha))
                for c in rows:
                    self._avisar(con,c['paciente_id'],c['id'],'ausencia',
                                f'Cita #{c["id"]} cancelada porque el médico no estará disponible el {fecha}.')
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return {'ok':True,'doctor_id':doctor_id,'fecha':fecha,'canceladas':[r['id'] for r in rows]}

    def listar_ausencias(self, doctor_id=None):
        with self._conexion() as con:
            q='SELECT a.id,a.doctor_id,d.nombre AS doctor_nombre,a.fecha,a.motivo,a.creado_en FROM ausencias a JOIN doctores d ON d.id=a.doctor_id'
            args=[]
            if doctor_id:
                q+=' WHERE a.doctor_id=?'; args.append(doctor_id)
            q+=' ORDER BY a.fecha DESC,a.id DESC'
            return [dict(row) for row in con.execute(q,args)]

    def notificaciones(self, paciente_id):
        if paciente_id is None: return []
        with self._conexion() as con:
            return [dict(row) for row in con.execute('SELECT id,cita_id,tipo,mensaje,creado_en,leida FROM notificaciones WHERE paciente_id=? ORDER BY id DESC',(paciente_id,))]

    def marcar_leida(self, paciente_id, id_notificacion):
        id_notificacion=self._entero(id_notificacion,'ID de notificación')
        with self._conexion() as con:
            result=con.execute('UPDATE notificaciones SET leida=1 WHERE id=? AND paciente_id=?',
                               (id_notificacion,paciente_id))
            if result.rowcount != 1: raise ReglaNegocioError('Notificación no encontrada')
        return {'ok':True}

    def proximas_citas(self,paciente_id):
        if paciente_id is None: return []
        return [c for c in self.listar_citas() if c['paciente_id']==paciente_id and
                c['estado'] in ('programada','pendiente_reagendar')
                and c['fecha']>=self.hoy().isoformat()]

    def confirmacion(self,cita_id):
        cita_id=self._entero(cita_id,'ID de cita')
        with self._conexion() as con:
            row=con.execute('''SELECT c.id,c.fecha,c.inicio,c.duracion,c.estado,c.doctor_id,c.paciente_id,
                                      d.nombre medico,p.nombre paciente
                               FROM citas c JOIN doctores d ON d.id=c.doctor_id
                               JOIN pacientes p ON p.id=c.paciente_id WHERE c.id=?''',(cita_id,)).fetchone()
            if row is None: raise ReglaNegocioError('Cita no encontrada')
        r=dict(row)
        r['texto']=self._texto_confirmacion(cita_id,r['paciente'],r['medico'],r['fecha'],r['inicio'],r['duracion'],r['estado'])
        return r
