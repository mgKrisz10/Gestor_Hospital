"""Casos solicitados en la revisión de laboratorio."""
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

class PruebasMaestra(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.svc=HospitalService(Path(self.tmp.name)/'hospital.sqlite3',DATA)
        self.auth=AutenticacionService(self.svc.db_path)
        self.fecha=(self.svc.hoy()+timedelta(days=2)).isoformat()
        self.anterior=(self.svc.hoy()-timedelta(days=1)).isoformat()
        self.oldsvc,self.oldauth=api.SERVICE,api.AUTH
        api.SERVICE,api.AUTH=self.svc,self.auth
        self.server=ThreadingHTTPServer(('127.0.0.1',0),api.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.tokens={role:self.auth.login(role,'Demo2026!')['token'] for role in ('admin','recepcion','paciente','consulta','doctora')}

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
        api.SERVICE,api.AUTH=self.oldsvc,self.oldauth
        self.tmp.cleanup()

    def call(self,path,role='recepcion',data=None):
        headers={'Authorization':f'Bearer {self.tokens[role]}','Accept':'application/json'}
        body=None if data is None else json.dumps(data).encode()
        if body is not None:headers['Content-Type']='application/json'
        req=Request(self.url+path,headers=headers,data=body,method='POST' if data is not None else 'GET')
        try:
            with urlopen(req,timeout=5) as response:return response.status,json.loads(response.read())
        except HTTPError as exc:return exc.code,json.loads(exc.read())

    def pedir_cita(self,**kwargs):
        data={'doctor_id':'MED001','fecha':self.fecha,'inicio':540,'duracion':30,'paciente_nombre':'Paciente Prueba'}
        data.update(kwargs)
        return data

    def test_01_no_puede_agendar_horario_ocupado(self):
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],201)
        status,msg=self.call('/api/mvp/citas',data=self.pedir_cita(paciente_nombre='Otra persona'))
        self.assertEqual(status,400)
        self.assertIn('ocupado',msg['error'])
        self.assertEqual(len(self.svc.listar_citas(self.fecha)),1)

    def test_02_cancela_y_vuelve_a_agendar(self):
        _,c=self.call('/api/mvp/citas',data=self.pedir_cita())
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],400)
        self.assertEqual(self.call(f"/api/mvp/citas/{c['id']}/cancelar",data={})[0],200)
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],201)
        self.assertEqual([r['estado'] for r in self.svc.listar_citas(self.fecha)],['cancelada','programada'])

    def test_03_bloquea_el_dia_anterior_en_servidor(self):
        status,r=self.call('/api/mvp/citas',data=self.pedir_cita(fecha=self.anterior))
        self.assertEqual(status,400)
        self.assertIn('anteriores',r['error'])
        self.assertFalse(self.svc.listar_citas(self.anterior))

    def test_04_reprogramar_al_pasado_prohibido(self):
        c=self.svc.agendar('MED001',self.fecha,540,30,'Paciente Prueba')
        status,_=self.call(f"/api/mvp/citas/{c['id']}/reprogramar",data={
            'doctor_id':'MED001','fecha':self.anterior,'inicio':540,'duracion':30})
        self.assertEqual(status,400)
        self.assertEqual(self.svc.confirmacion(c['id'])['fecha'],self.fecha)

    def test_05_ausencia_no_disponible_y_liberar_fecha(self):
        _,r=self.call('/api/mvp/ausencias','doctora',{'fecha':self.fecha,'motivo':'Salida de servicio'})
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],400)
        st,dis=self.call(f'/api/mvp/disponibilidad?doctor=MED001&fecha={self.fecha}&duracion=30')
        self.assertTrue(dis['ausencia'])
        self.assertEqual(dis['intervalos'],[])
        st,ar=self.call('/api/mvp/ausencias','doctora')
        absence=next(a for a in ar['ausencias'] if a['fecha']==self.fecha)
        st,data=self.call(f"/api/mvp/ausencias/{absence['id']}/levantar",'doctora',{})
        self.assertEqual(st,200)
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],201)

    def test_06_baja_medico_con_citas_preserva_historial(self):
        a=self.svc.agendar('MED001',self.fecha,540,30,'Laura')
        old_date=(self.svc.hoy()-timedelta(days=60)).isoformat()
        with self.svc._conexion() as con:
            pid=con.execute("INSERT INTO pacientes(nombre,telefono,correo) VALUES ('Antiguo','', '')").lastrowid
            con.execute('INSERT INTO citas(doctor_id,paciente_id,fecha,inicio,duracion,estado) VALUES (?,?,?,?,?,?)',
                        ('MED001',pid,old_date,480,30,'programada'))
        status,impact=self.call('/api/mvp/doctores/MED001/impacto','admin')
        self.assertEqual(status,200)
        self.assertEqual(impact['citas_historicas'],2)
        self.assertEqual(impact['citas_por_reagendar'],1)
        status,r=self.call('/api/mvp/doctores/MED001/baja','admin',{})
        self.assertEqual(status,200)
        self.assertEqual(r['pendientes_reagendar'],[a['id']])
        self.assertEqual([c['estado'] for c in self.svc.listar_citas(self.fecha)],['pendiente_reagendar'])
        self.assertEqual([c['estado'] for c in self.svc.listar_citas(old_date)],['programada'])
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],400)
        self.assertEqual(self.call('/api/mvp/disponibilidad?doctor=MED001&fecha='+self.fecha+'&duracion=30')[0],400)
        self.assertNotIn('MED001',[d['id'] for d in self.svc.listar_doctores()])
        with self.assertRaises(SinSesion):self.auth.login('doctora','Demo2026!')
        self.assertEqual(self.call('/api/mvp/doctores/MED001/impacto','recepcion')[0],403)
        self.assertEqual(self.call('/api/mvp/doctores/MED001/baja','recepcion',{})[0],403)
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita(doctor_id='MED002'))[0],201)

    def test_07_reactivacion_permite_nuevas_citas_sin_restaurar_canceladas(self):
        a=self.svc.agendar('MED001',self.fecha,540,30,'Laura')
        self.svc.dar_baja_doctor('MED001')
        self.assertEqual(self.call('/api/mvp/doctores/MED001/reactivar','admin',{})[0],200)
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],201)
        self.assertEqual([r['estado'] for r in self.svc.listar_citas(self.fecha)],['pendiente_reagendar','programada'])
        self.auth.login('doctora','Demo2026!')

    def test_08_intentar_baja_doble_y_medico_inexistente(self):
        self.assertEqual(self.call('/api/mvp/doctores/MED999/baja','admin',{})[0],400)
        self.assertEqual(self.call('/api/mvp/doctores/MED001/baja','admin',{})[0],200)
        self.assertEqual(self.call('/api/mvp/doctores/MED001/baja','admin',{})[0],400)
        self.assertEqual(self.call('/api/mvp/doctores/MED001/reactivar','recepcion',{})[0],403)

    def test_09_ausencia_liberada_no_revive_citas_canceladas(self):
        a=self.svc.agendar('MED001',self.fecha,540,30,'Laura')
        self.svc.notificar_ausencia('MED001',self.fecha,'Ausencia médica')
        aus=self.svc.listar_ausencias('MED001')[0]
        self.svc.levantar_ausencia(aus['id'])
        self.assertEqual(self.svc.confirmacion(a['id'])['estado'],'cancelada')
        self.assertEqual(self.call('/api/mvp/citas',data=self.pedir_cita())[0],201)

if __name__=='__main__':unittest.main()
