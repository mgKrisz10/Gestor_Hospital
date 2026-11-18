"""Reglas de identificación y colisión de citas por paciente y doctor."""
import json
import tempfile
import threading
import unittest
from datetime import timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.autenticacion import AutenticacionService, SinSesion
from src.mvp import ReglaNegocioError
from src.operaciones_extra import HospitalService
import src.servidor as api

DATA=Path(__file__).resolve().parents[1]/'data'/'citas_ficticias.json'
BASE=Path(__file__).resolve().parents[1]


class IdentidadesYEmpalmes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'hospital.sqlite3'
        self.svc=HospitalService(self.db,DATA)
        self.auth=AutenticacionService(self.db)
        self.fecha=(self.svc.hoy()+timedelta(days=4)).isoformat()
        self.pid=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id']

    def test_clave_paciente_unica_y_persistente(self):
        paciente=self.svc.registrar_paciente('Rosa Uno','555','rosa@ejemplo.com')['paciente']
        otro=self.svc.registrar_paciente('Rosa Dos')['paciente']
        self.assertNotEqual(paciente['clave'],otro['clave'])
        self.assertEqual(paciente['clave'],f"PAC-{paciente['id']:06d}")
        self.assertEqual([p['clave'] for p in self.svc.listar_pacientes() if p['id']==paciente['id']],
                         [paciente['clave']])
        reiniciado=HospitalService(self.db,DATA)
        self.assertIn(paciente['clave'],[p['clave'] for p in reiniciado.listar_pacientes()])

    def test_paciente_login_por_clave_requiere_contrasena(self):
        login=self.auth.login(f'PAC-{self.pid:06d}','Demo2026!')['usuario']
        self.assertEqual(login['paciente_id'],self.pid)
        self.assertEqual(login['clave_paciente'],f'PAC-{self.pid:06d}')
        with self.assertRaises(SinSesion):
            self.auth.login(f'PAC-{self.pid:06d}','contraseña-incorrecta')

    def test_doctor_login_por_id_y_contrasena(self):
        for doctor_id in ('MED001','MED002','MED003'):
            usuario=self.auth.login(None,'Demo2026!',doctor_id)['usuario']
            self.assertEqual(usuario['rol'],'doctor')
            self.assertEqual(usuario['doctor_id'],doctor_id)
        with self.assertRaises(SinSesion):
            self.auth.login(None,'incorrecta','MED002')
        with self.assertRaises(SinSesion):
            self.auth.login(None,'Demo2026!','MED999')

    def test_rechaza_mismo_paciente_con_distintos_medicos_en_horario_igual_y_cruzado(self):
        self.svc.agendar('MED001',self.fecha,540,60,paciente_id=self.pid)
        for inicio in (540,570,590):
            with self.subTest(inicio=inicio):
                with self.assertRaisesRegex(ReglaNegocioError,'paciente'):
                    self.svc.agendar('MED002',self.fecha,inicio,30,paciente_id=self.pid)
        self.assertEqual(len([c for c in self.svc.listar_citas(self.fecha) if c['estado']=='programada']),1)
        self.svc.agendar('MED002',self.fecha,600,30,paciente_id=self.pid)
        self.svc.agendar('MED003',self.fecha,570,30,'Otra persona')

    def test_cancelar_libera_la_agenda_del_paciente(self):
        c=self.svc.agendar('MED001',self.fecha,540,30,paciente_id=self.pid)
        with self.assertRaisesRegex(ReglaNegocioError,'paciente'):
            self.svc.agendar('MED002',self.fecha,540,30,paciente_id=self.pid)
        self.svc.cancelar(c['id'])
        nueva=self.svc.agendar('MED002',self.fecha,540,30,paciente_id=self.pid)
        self.assertEqual(nueva['estado'],'programada')

    def test_reprogramar_conflicto_no_modifica_cita(self):
        primera=self.svc.agendar('MED001',self.fecha,540,60,paciente_id=self.pid)
        segunda=self.svc.agendar('MED002',self.fecha,660,30,paciente_id=self.pid)
        with self.assertRaisesRegex(ReglaNegocioError,'paciente'):
            self.svc.reprogramar(segunda['id'],'MED002',self.fecha,570,30)
        self.assertEqual(self.svc.confirmacion(segunda['id'])['inicio'],660)
        self.assertEqual(self.svc.confirmacion(primera['id'])['estado'],'programada')

    def test_baja_medico_y_reparacion_de_registros_antiguos(self):
        cita=self.svc.agendar('MED001',self.fecha,540,30,paciente_id=self.pid)
        self.svc.dar_baja_doctor('MED001')
        self.assertEqual(self.svc.confirmacion(cita['id'])['estado'],'pendiente_reagendar')
        # Simula una base antigua que conservó programada después de una baja.
        with self.svc._conexion() as con:
            con.execute("UPDATE citas SET estado='programada' WHERE id=?",(cita['id'],))
        nuevo=HospitalService(self.db,DATA)
        self.assertEqual(nuevo.confirmacion(cita['id'])['estado'],'pendiente_reagendar')
        self.assertIn(cita['id'],[c['id'] for c in nuevo.proximas_citas(self.pid)])

    def test_interfaz_calendario_muestra_pendientes_y_un_acceso_doctor(self):
        html=(BASE/'frontend/mvp.html').read_text(encoding='utf-8')
        js=(BASE/'frontend/mvp.js').read_text(encoding='utf-8')
        self.assertEqual(html.count('data-demo="doctor"'),1)
        self.assertNotIn('data-demo="doctora"',html)
        self.assertIn('id="doctor-id-login"',html)
        self.assertIn('id="patient-key"',html)
        self.assertIn("['programada','pendiente_reagendar'].includes(c.estado)",js)
        self.assertIn('clave_paciente',js)


class PruebasAPIIdentidades(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'hospital.sqlite3'
        self.svc=HospitalService(self.db,DATA)
        self.auth=AutenticacionService(self.db)
        self.fecha=(self.svc.hoy()+timedelta(days=3)).isoformat()
        self.before_svc,self.before_auth=api.SERVICE,api.AUTH
        api.SERVICE,api.AUTH=self.svc,self.auth
        self.server=ThreadingHTTPServer(('127.0.0.1',0),api.Handler)
        self.t=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.t.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.t.join(timeout=5)
        api.SERVICE,api.AUTH=self.before_svc,self.before_auth
        self.tmp.cleanup()

    def req(self,path,data=None,token=None):
        headers={'Accept':'application/json'}
        if token: headers['Authorization']='Bearer '+token
        b=json.dumps(data).encode('utf-8') if data is not None else None
        if b is not None:headers['Content-Type']='application/json'
        request=Request(self.base+path,headers=headers,data=b,
                        method='POST' if b is not None else 'GET')
        try:
            with urlopen(request,timeout=6) as r:return r.status,json.loads(r.read())
        except HTTPError as e:
            return e.code,json.loads(e.read())

    def token(self,login):
        return self.auth.login(login,'Demo2026!')['token']

    def test_login_doctor_y_contra_chequeo_de_agenda(self):
        status,data=self.req('/api/mvp/auth/login',{'doctor_id':'MED002','password':'Demo2026!'})
        self.assertEqual(status,200)
        self.assertEqual(data['usuario']['doctor_id'],'MED002')
        self.assertEqual(data['usuario']['rol'],'doctor')
        st,agenda=self.req('/api/mvp/citas',token=data['token'])
        self.assertEqual(st,200)
        self.assertTrue(all(c['doctor_id']=='MED002' for c in agenda['citas']))

    def test_personal_autorizado_solo_consulta_directorio(self):
        tok=self.token('consulta')
        self.assertEqual(self.req('/api/mvp/doctores/directorio',token=tok)[0],200)
        self.assertEqual(self.req('/api/mvp/doctores',token=tok)[0],200)
        self.assertEqual(self.req('/api/mvp/citas',token=tok)[0],403)
        self.assertEqual(self.req('/api/mvp/pacientes',token=tok)[0],403)
        self.assertEqual(self.req('/api/mvp/usuarios',token=tok)[0],403)

    def test_eliminar_ultima_cuenta_medica_deja_cita_pendiente(self):
        pacid=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id']
        cita=self.svc.agendar('MED002',self.fecha,600,30,paciente_id=pacid)
        medico=next(u for u in self.auth.usuarios() if u['usuario']=='doctor_carlos')
        st,result=self.req(f"/api/mvp/usuarios/{medico['id']}/eliminar",{},self.token('admin'))
        self.assertEqual(st,200,result)
        self.assertEqual(self.svc.confirmacion(cita['id'])['estado'],'pendiente_reagendar')
        _,r=self.req('/api/mvp/citas',token=self.token('paciente'))
        visible=next(c for c in r['citas'] if c['id']==cita['id'])
        self.assertEqual(visible['estado'],'pendiente_reagendar')


if __name__=='__main__':unittest.main()
