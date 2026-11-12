"""Pruebas de las operaciones agregadas en la segunda entrega."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.autenticacion import AutenticacionService, SinSesion
from src.mvp import ReglaNegocioError
from src.operaciones_extra import HospitalService
import src.servidor as api

DATA=Path(__file__).resolve().parents[1]/'data'/'citas_ficticias.json'
FUTURE=(date.today()+timedelta(days=15)).isoformat()
FUTURE2=(date.today()+timedelta(days=16)).isoformat()

class RequisitosCompletosTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'hospital.sqlite3'
        self.svc=HospitalService(self.path,DATA)
        self.auth=AutenticacionService(self.path)
        self.oldsvc,self.oldauth=api.SERVICE,api.AUTH
        api.SERVICE,api.AUTH=self.svc,self.auth
        self.server=ThreadingHTTPServer(('127.0.0.1',0),api.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.root=f'http://127.0.0.1:{self.server.server_port}'
        self.tokens={k:self.auth.login(k,'Demo2026!')['token'] for k in ('admin','doctora','paciente','recepcion','consulta')}

    def tearDown(self):
        self.server.shutdown();self.thread.join(timeout=5);self.server.server_close()
        api.SERVICE,api.AUTH=self.oldsvc,self.oldauth
        self.tmp.cleanup()

    def call(self,path,user=None,body=None):
        headers={'Accept':'application/json'}
        if user:headers['Authorization']=f'Bearer {self.tokens[user]}'
        payload=None if body is None else json.dumps(body).encode()
        if payload is not None:headers['Content-Type']='application/json'
        req=Request(self.root+path,headers=headers,data=payload,method='POST' if payload is not None else 'GET')
        try:
            with urlopen(req,timeout=4) as response:return response.status,json.loads(response.read())
        except HTTPError as exc:return exc.code,json.loads(exc.read())

    def test_r01_registrar_pacientes(self):
        code,p=self.call('/api/mvp/pacientes','recepcion',{'nombre':'Elena Rocha','telefono':'123456','correo':'elena@example.com'})
        self.assertEqual(code,201)
        code,l=self.call('/api/mvp/pacientes','recepcion')
        self.assertIn(p['paciente']['id'],[x['id'] for x in l['pacientes']])
        self.assertEqual(self.call('/api/mvp/pacientes','paciente')[0],403)
        self.assertEqual(self.call('/api/mvp/pacientes','consulta',{'nombre':'Carlos'} )[0],403)

    def test_r05_r06_conflicto_y_fecha_distinta(self):
        c={'doctor_id':'MED001','fecha':FUTURE,'inicio':480,'duracion':30,'paciente_nombre':'Mario Prado'}
        self.assertEqual(self.call('/api/mvp/citas','recepcion',c)[0],201)
        self.assertEqual(self.call('/api/mvp/citas','recepcion',{**c,'inicio':495})[0],400)
        self.assertEqual(self.call('/api/mvp/citas','recepcion',{**c,'fecha':FUTURE2})[0],201)
        self.assertEqual(self.call('/api/mvp/citas','recepcion',{**c,'doctor_id':'MED002'})[0],201)

    def test_r08_reprogramacion_y_conflicto(self):
        a=self.svc.agendar('MED001',FUTURE,480,30,'Alma Sánchez')
        b=self.svc.agendar('MED001',FUTURE,540,30,'Bea Solís')
        url=f"/api/mvp/citas/{a['id']}/reprogramar"
        self.assertEqual(self.call(url,'recepcion',{'doctor_id':'MED001','fecha':FUTURE,'inicio':550,'duracion':30})[0],400)
        self.assertEqual(self.call(url,'recepcion',{'doctor_id':'MED002','fecha':FUTURE2,'inicio':540,'duracion':30})[0],200)
        self.assertEqual(self.svc.confirmacion(a['id'])['doctor_id'],'MED002')
        self.assertEqual(self.call(url,'paciente',{'doctor_id':'MED001','fecha':FUTURE,'inicio':480,'duracion':30})[0],403)

    def test_r08_reprogramar_no_permite_ausencia(self):
        a=self.svc.agendar('MED001',FUTURE,480,30,'A B')
        self.svc.notificar_ausencia('MED002',FUTURE2,'Congreso médico')
        self.assertEqual(self.call(f"/api/mvp/citas/{a['id']}/reprogramar",'admin',
                     {'doctor_id':'MED002','fecha':FUTURE2,'inicio':480,'duracion':30})[0],400)

    def test_r09_citas_proximas_y_privacidad(self):
        paciente=next(x for x in self.auth.usuarios() if x['usuario']=='paciente')
        self.svc.agendar('MED001',FUTURE,480,30,paciente_id=paciente['paciente_id'])
        self.svc.agendar('MED001',FUTURE,540,30,'Otra Persona')
        # Registro histórico existente: la API ya no permite crear citas en el pasado.
        with self.svc._conexion() as con:
            con.execute("INSERT INTO citas(doctor_id,paciente_id,fecha,inicio,duracion) VALUES (?,?,?,?,?)",
                        ('MED001', paciente['paciente_id'], '2020-01-02', 480, 30))
        c,p=self.call('/api/mvp/citas-proximas','paciente')
        self.assertEqual(c,200)
        self.assertEqual(len(p['citas']),1)
        self.assertEqual(self.call('/api/mvp/citas-proximas','consulta')[0],403)

    def test_r11_crear_modificar_eliminar_usuario(self):
        req={'usuario':'nueva_recep','nombre':'Rocío Bello','rol':'recepcion','password':'ClaveNueva9!'}
        c,r=self.call('/api/mvp/usuarios','admin',req)
        self.assertEqual(c,201)
        uid=r['id']
        self.assertEqual(self.call('/api/mvp/usuarios','recepcion',req)[0],403)
        self.assertEqual(self.call('/api/mvp/usuarios','admin',req)[0],400)
        change={**req,'nombre':'Rocío Blanco','password':'ClaveCambiada9!'}
        self.assertEqual(self.call(f'/api/mvp/usuarios/{uid}/editar','admin',change)[0],200)
        self.assertEqual(self.auth.login('nueva_recep','ClaveCambiada9!')['usuario']['nombre'],'Rocío Blanco')
        self.assertEqual(self.call(f'/api/mvp/usuarios/{uid}/eliminar','admin',{})[0],200)
        with self.assertRaises(SinSesion):self.auth.login('nueva_recep','ClaveCambiada9!')

    def test_r11_no_se_elimina_el_admin_unico(self):
        admin=next(x for x in self.auth.usuarios() if x['usuario']=='admin')
        self.assertEqual(self.call(f"/api/mvp/usuarios/{admin['id']}/eliminar",'admin',{})[0],400)

    def test_r11_usuario_doctor_con_enlace(self):
        req={'usuario':'doctor_2','nombre':'Dr. Pérez','rol':'doctor','password':'Password2026!', 'doctor_id':'MED002'}
        self.assertEqual(self.call('/api/mvp/usuarios','admin',req)[0],201)
        t=self.auth.login('doctor_2','Password2026!')['token']
        self.assertEqual(self.auth.validar(t).doctor_id,'MED002')

    def test_r12_confirmacion_y_bandeja(self):
        pid=next(x for x in self.auth.usuarios() if x['usuario']=='paciente')['paciente_id']
        c,r=self.call('/api/mvp/citas','recepcion',{'doctor_id':'MED001','fecha':FUTURE,'inicio':480,'duracion':30,'paciente_id':pid})
        self.assertEqual(c,201)
        self.assertIn('Cita #',r['confirmacion'])
        code,notifs=self.call('/api/mvp/notificaciones','paciente')
        self.assertEqual(code,200)
        self.assertEqual(notifs['notificaciones'][0]['tipo'],'confirmacion')
        nid=notifs['notificaciones'][0]['id']
        self.assertEqual(self.call(f'/api/mvp/notificaciones/{nid}/leida','paciente',{})[0],200)
        self.assertEqual(self.call('/api/mvp/notificaciones','consulta')[0],403)
        self.assertEqual(self.call('/api/mvp/confirmacion/'+str(r['id']),'paciente')[0],200)

    def test_r12_confirmacion_no_expuesta_a_otros_pacientes(self):
        c=self.svc.agendar('MED001',FUTURE,480,30,'No Vinculado')
        self.assertEqual(self.call('/api/mvp/confirmacion/'+str(c['id']),'paciente')[0],403)

    def test_r14_ausencia_cancela_lista_y_bloquea_horarios(self):
        pid=next(x for x in self.auth.usuarios() if x['usuario']=='paciente')['paciente_id']
        a=self.svc.agendar('MED001',FUTURE,480,30,paciente_id=pid)
        b=self.svc.agendar('MED001',FUTURE,570,30,'Andrés Silva')
        self.svc.agendar('MED001',FUTURE2,480,30,'Otro Día')
        code,r=self.call('/api/mvp/ausencias','doctora',{'fecha':FUTURE,'motivo':'Incapacidad médica'})
        self.assertEqual(code,201)
        self.assertEqual(set(r['canceladas']),{a['id'],b['id']})
        c,res=self.call('/api/mvp/disponibilidad?doctor=MED001&fecha='+FUTURE+'&duracion=30','doctora')
        self.assertEqual(c,200)
        self.assertTrue(res['ausencia'])
        self.assertEqual(res['intervalos'],[])
        self.assertEqual(self.call('/api/mvp/citas','recepcion',
            {'doctor_id':'MED001','fecha':FUTURE,'inicio':480,'duracion':30,'paciente_nombre':'Nuevo Paciente'})[0],400)
        self.assertEqual(self.call('/api/mvp/ausencias','paciente',{'fecha':FUTURE,'motivo':'Prueba'} )[0],403)
        self.assertEqual(len(self.svc.proximas_citas(pid)),0)
        self.assertEqual(self.call('/api/mvp/ausencias','doctora',{'fecha':FUTURE,'motivo':'Otra ausencia'})[0],400)
        self.assertEqual(self.svc.listar_citas(FUTURE2)[0]['estado'],'programada')

    def test_r14_no_permite_doctor_ajeno(self):
        code,r=self.call('/api/mvp/ausencias','doctora',{'doctor_id':'MED002','fecha':FUTURE,'motivo':'Incapacidad médica'})
        self.assertEqual(code,201)
        self.assertEqual(r['doctor_id'],'MED001')

if __name__=='__main__':unittest.main()
