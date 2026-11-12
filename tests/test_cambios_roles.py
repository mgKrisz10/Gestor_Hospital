"""Cobertura de las agendas médicas, bajas y directorio de personal autorizado."""
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.autenticacion import AutenticacionService, SinSesion
from src.mvp import HospitalService as HospitalInicial, ReglaNegocioError
from src.operaciones_extra import HospitalService
import src.servidor as api

DATA = Path(__file__).resolve().parents[1] / 'data' / 'citas_ficticias.json'


class BajaYDirectorioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'hospital.db'
        self.svc = HospitalService(self.path, DATA)
        self.auth = AutenticacionService(self.path)
        self.fecha = (self.svc.hoy() + timedelta(days=3)).isoformat()

    def test_baja_deja_pendientes_y_conserva_folio_y_paciente(self):
        cita = self.svc.agendar('MED001', self.fecha, 540, 30, paciente_id=1)
        efecto = self.svc.dar_baja_doctor('MED001')
        self.assertEqual(efecto['pendientes_reagendar'], [cita['id']])
        anterior = self.svc.confirmacion(cita['id'])
        self.assertEqual(anterior['estado'], 'pendiente_reagendar')
        self.assertEqual(anterior['paciente_id'], 1)
        self.assertEqual(self.svc.resumen()['citas_pendientes_reagendar'], 1)
        self.assertEqual(self.svc.resumen()['citas_canceladas'], 0)
        self.assertTrue(any('pendiente de reagendar' in x['mensaje'] for x in self.svc.notificaciones(1)))
        with self.assertRaises(SinSesion):
            self.auth.login('doctora', 'Demo2026!')
        nuevo = self.svc.reprogramar(cita['id'], 'MED002', self.fecha, 600, 30)
        self.assertEqual(nuevo['estado'], 'programada')
        posterior = self.svc.confirmacion(cita['id'])
        self.assertEqual(posterior['id'], cita['id'])
        self.assertEqual(posterior['doctor_id'], 'MED002')
        self.assertEqual(posterior['estado'], 'programada')
        self.assertEqual(self.svc.resumen()['citas_pendientes_reagendar'], 0)

    def test_baja_no_reprograma_si_nuevo_horario_esta_ocupado(self):
        cita = self.svc.agendar('MED001', self.fecha, 540, 30, paciente_id=1)
        self.svc.agendar('MED002', self.fecha, 540, 30, paciente_nombre='Otra persona')
        self.svc.dar_baja_doctor('MED001')
        with self.assertRaisesRegex(ReglaNegocioError, 'ocupado'):
            self.svc.reprogramar(cita['id'], 'MED002', self.fecha, 540, 30)
        self.assertEqual(self.svc.confirmacion(cita['id'])['estado'], 'pendiente_reagendar')

    def test_pendiente_puede_cancelarse_por_peticion(self):
        cita = self.svc.agendar('MED001', self.fecha, 540, 30, paciente_id=1)
        self.svc.dar_baja_doctor('MED001')
        result = self.svc.cancelar(cita['id'], motivo='El paciente no desea reprogramar')
        self.assertEqual(result['estado'], 'cancelada')

    def test_directorio_no_revela_informacion_personal(self):
        self.svc.agendar('MED001', self.fecha, 540, 30, paciente_nombre='Nombre Confidencial', paciente_telefono='5555123456')
        self.svc.dar_baja_doctor('MED001')
        d = self.svc.directorio_medicos()
        med = next(x for x in d if x['id']=='MED001')
        self.assertEqual(med['activo'], 0)
        self.assertEqual(med['citas_por_reagendar'], 1)
        self.assertEqual(med['citas_programadas'], 0)
        self.assertNotIn('Nombre Confidencial', json.dumps(d))
        self.assertNotIn('5555123456', json.dumps(d))

    def test_doctora_ve_solo_su_agenda_y_personal_solo_directorio(self):
        self.svc.agendar('MED001', self.fecha, 540, 30, paciente_nombre='Paciente Uno')
        self.svc.agendar('MED002', self.fecha, 540, 30, paciente_nombre='Paciente Dos')
        viejo_svc, viejo_auth = api.SERVICE, api.AUTH
        api.SERVICE, api.AUTH = self.svc, self.auth
        server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5),
                                 setattr(api, 'SERVICE', viejo_svc), setattr(api, 'AUTH', viejo_auth)))
        base = f'http://127.0.0.1:{server.server_port}'

        def req(path, role):
            token = self.auth.login(role, 'Demo2026!')['token']
            request = Request(base+path,headers={'Authorization':'Bearer '+token})
            try:
                with urlopen(request, timeout=5) as res:
                    return res.status, json.loads(res.read())
            except HTTPError as err:
                return err.code, json.loads(err.read())

        status, doc = req('/api/mvp/citas', 'doctora')
        self.assertEqual(status, 200)
        self.assertEqual(len(doc['citas']), 1)
        self.assertEqual(doc['citas'][0]['doctor_id'], 'MED001')
        status, directory = req('/api/mvp/doctores/directorio', 'consulta')
        self.assertEqual(status, 200)
        self.assertTrue(all('paciente_nombre' not in d for d in directory['doctores']))
        self.assertEqual(req('/api/mvp/citas', 'consulta')[0], 403)
        self.assertEqual(req('/api/mvp/doctores/admin', 'consulta')[0], 403)
        self.assertEqual(req('/api/mvp/doctores/directorio', 'paciente')[0], 403)

    def test_migracion_desde_db_antigua_conserva_fks_y_citas(self):
        # Emulate a database created before the third status was introduced.
        with sqlite3.connect(self.path) as con:
            con.execute('PRAGMA foreign_keys=OFF')
            con.execute('''CREATE TABLE citas_old (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id TEXT NOT NULL REFERENCES doctores(id),
                paciente_id INTEGER NOT NULL REFERENCES pacientes(id),
                fecha TEXT NOT NULL,inicio INTEGER NOT NULL,duracion INTEGER NOT NULL,
                estado TEXT NOT NULL DEFAULT 'programada'
                     CHECK (estado IN ('programada','cancelada')),
                cancelacion_motivo TEXT NOT NULL DEFAULT '')''')
            con.execute('INSERT INTO citas_old(id,doctor_id,paciente_id,fecha,inicio,duracion,estado,cancelacion_motivo) SELECT id,doctor_id,paciente_id,fecha,inicio,duracion,estado,cancelacion_motivo FROM citas')
            con.execute('DROP TABLE citas')
            con.execute('ALTER TABLE citas_old RENAME TO citas')
            con.execute('CREATE INDEX idx_citas_agenda ON citas(doctor_id,fecha,estado,inicio)')
            con.commit()
        old = HospitalInicial(self.path, DATA)
        cita = old.agendar('MED001', self.fecha, 540, 30, paciente_id=1)
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE citas SET estado='cancelada',cancelacion_motivo='Baja del médico' WHERE id=?", (cita['id'],))
            con.execute("INSERT INTO notificaciones(paciente_id,cita_id,tipo,mensaje) VALUES (?,?,?,?)",
                        (1,cita['id'],'baja_medico','Aviso antiguo'))
        new = HospitalService(self.path, DATA)
        self.assertEqual(new.confirmacion(cita['id'])['estado'],'pendiente_reagendar')
        self.assertEqual(new.confirmacion(cita['id'])['paciente_id'],1)
        self.assertTrue(new.notificaciones(1))
        with new._conexion() as con:
            self.assertFalse(con.execute('PRAGMA foreign_key_check').fetchall())
        # Initialization is idempotent, including schema upgrades.
        new2 = HospitalService(self.path, DATA)
        self.assertEqual(new2.confirmacion(cita['id'])['estado'],'pendiente_reagendar')


if __name__ == '__main__':
    unittest.main()
