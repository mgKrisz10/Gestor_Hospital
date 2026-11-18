"""Pruebas de cuentas médicas y de la separación de pantallas."""
import json
import tempfile
import threading
import unittest
from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from src.autenticacion import AutenticacionService
from src.operaciones_extra import HospitalService
import src.servidor as servidor

DATA=Path(__file__).resolve().parents[1]/'data'/'citas_ficticias.json'
BASE=Path(__file__).resolve().parents[1]


class TestVistasCalendario(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.servicio=HospitalService(Path(self.tmp.name)/'hospital.sqlite3', DATA)
        self.auth=AutenticacionService(self.servicio.db_path)
        self.fecha=(self.servicio.hoy()+timedelta(days=3)).isoformat()

    def test_hay_tres_medicos_que_pueden_iniciar_sesion(self):
        for usuario, medico in [('doctora','MED001'),('doctor_carlos','MED002'),('doctora_sofia','MED003')]:
            cuenta=self.auth.login(usuario,'Demo2026!')['usuario']
            self.assertEqual(cuenta['rol'],'doctor')
            self.assertEqual(cuenta['doctor_id'],medico)

    def test_agrega_cuentas_a_base_existente_sin_duplicarlas(self):
        with self.auth._con() as con:
            con.execute("DELETE FROM usuarios WHERE usuario IN ('doctor_carlos','doctora_sofia')")
        self.assertEqual(len(self.auth.usuarios()),5)
        AutenticacionService(self.servicio.db_path)
        AutenticacionService(self.servicio.db_path)
        self.assertEqual(len(self.auth.usuarios()),7)
        self.assertEqual(self.auth.login('doctor_carlos','Demo2026!')['usuario']['doctor_id'],'MED002')

    def test_doctor_solo_ve_su_agenda_y_paciente_solo_sus_citas(self):
        original_svc,original_auth=servidor.SERVICE,servidor.AUTH
        servidor.SERVICE,servidor.AUTH=self.servicio,self.auth
        server=ThreadingHTTPServer(('127.0.0.1',0),servidor.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join(timeout=5),setattr(servidor,'SERVICE',original_svc),setattr(servidor,'AUTH',original_auth)))
        pid=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id']
        cita1=self.servicio.agendar('MED001',self.fecha,540,30,paciente_id=pid)
        cita2=self.servicio.agendar('MED002',self.fecha,600,30,paciente_id=pid)
        self.servicio.agendar('MED003',self.fecha,660,30,'Otro paciente')
        def agenda(login):
            token=self.auth.login(login,'Demo2026!')['token']
            r=Request(f'http://127.0.0.1:{server.server_port}/api/mvp/citas',headers={'Authorization':f'Bearer {token}'})
            with urlopen(r,timeout=5) as resp:return json.loads(resp.read())['citas']
        self.assertEqual({c['doctor_id'] for c in agenda('doctora')},{'MED001'})
        self.assertEqual({c['doctor_id'] for c in agenda('doctor_carlos')},{'MED002'})
        self.assertEqual({c['doctor_id'] for c in agenda('doctora_sofia')},{'MED003'})
        self.assertEqual({c['id'] for c in agenda('paciente')},{cita1['id'],cita2['id']})
        self.assertEqual({c['doctor_nombre'] for c in agenda('paciente')},{'Dra. Ana Lopez','Dr. Carlos Martinez'})

    def test_interfaz_sin_ausencias_y_con_calendario(self):
        html=(BASE/'frontend/mvp.html').read_text(encoding='utf8')
        js=(BASE/'frontend/mvp.js').read_text(encoding='utf8')
        self.assertNotIn('Ausencias médicas',html)
        self.assertNotIn('id="absences-area"',html)
        self.assertIn('id="patient-calendar-area"',html)
        self.assertIn('id="calendar-days"',html)
        self.assertIn('id="calendar-selected-citas"',html)
        self.assertIn('data-demo="doctor"',html)
        self.assertNotIn('data-demo="doctor_carlos"',html)
        self.assertIn('id="doctor-id-login"',html)
        self.assertIn("$('availability-area').hidden = !puedeConsultar;",js)
        self.assertIn('const puedeConsultar = !soloDoctor && !soloPaciente',js)
        self.assertIn("if (soloPaciente) await cargarCalendarioPaciente()",js)
        self.assertIn("citasCalendario=r.citas.filter(c=>['programada','pendiente_reagendar'].includes(c.estado))",js)

if __name__=='__main__':unittest.main()
