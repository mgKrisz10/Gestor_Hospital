"""Pruebas de roles y acceso al API desde HTTP real en localhost."""
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

from src.autenticacion import AutenticacionService, AccesoDenegado, SinSesion
from src.mvp import HospitalService
import src.servidor as api

DATA = Path(__file__).resolve().parents[1] / 'data' / 'citas_ficticias.json'


class BaseHospitalTest:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'test.sqlite3'
        self.service = HospitalService(self.db, DATA)
        self.auth = AutenticacionService(self.db)

    def tearDown(self):
        self.temp.cleanup()

class AutenticacionTests(BaseHospitalTest, unittest.TestCase):
    def test_cinco_cuentas_diferentes(self):
        self.assertEqual({u['rol'] for u in self.auth.usuarios()}, {
            'administrador', 'doctor', 'paciente', 'recepcion', 'personal_autorizado'})

    def test_credenciales_incorrectas(self):
        for username, pw in [('admin', 'incorrecto'), ('nadie', 'Demo2026!')]:
            with self.subTest(username=username), self.assertRaises(SinSesion):
                self.auth.login(username,pw)

    def test_cuenta_y_rol_distinguidos(self):
        r = self.auth.login('doctora','Demo2026!')
        self.assertEqual(r['usuario']['doctor_id'], 'MED001')
        self.assertEqual(self.auth.validar(r['token']).rol, 'doctor')
        self.assertNotIn('password_hash', str(r))

    def test_logout_revoca(self):
        t = self.auth.login('paciente','Demo2026!')['token']
        self.auth.logout(t)
        with self.assertRaises(SinSesion):
            self.auth.validar(t)

    def test_sesion_ausente(self):
        with self.assertRaises(SinSesion):
            self.auth.validar(None)

    def test_autorizacion_por_perfil(self):
        doctor=self.auth.validar(self.auth.login('doctora','Demo2026!')['token'])
        recep=self.auth.validar(self.auth.login('recepcion','Demo2026!')['token'])
        with self.assertRaises(AccesoDenegado):
            self.auth.exigir(doctor,'administrador','recepcion')
        self.auth.exigir(recep,'administrador','recepcion')

    def test_paciente_demo_perdurable(self):
        original=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id']
        another=AutenticacionService(self.db).login('paciente','Demo2026!')['usuario']['paciente_id']
        self.assertEqual(original, another)
        self.assertEqual(len(self.auth.usuarios()),5)

    def test_doctor_agregado_y_duplicado(self):
        from src.mvp import ReglaNegocioError
        self.service.registrar_doctor('MED004','Dr. Juan Pérez','Neurología')
        self.assertIn('MED004', {d['id'] for d in self.service.listar_doctores()})
        with self.assertRaises(ReglaNegocioError):
            self.service.registrar_doctor('MED004','Dr. Juan Pérez','Neurología')

    def test_citas_con_paciente_existente(self):
        pid=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id']
        self.service.agendar('MED001','2026-11-10',480,30,paciente_id=pid)
        self.assertEqual(self.service.listar_citas()[0]['paciente_id'],pid)
        with self.assertRaises(Exception):
            self.service.agendar('MED001','2026-11-11',480,30,paciente_id=999999)
        self.assertEqual(len(self.service.listar_citas()),1)


class APIAutorizacionTests(BaseHospitalTest, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.old_svc, self.old_auth = api.SERVICE,api.AUTH
        api.SERVICE,api.AUTH=self.service,self.auth
        self.server=ThreadingHTTPServer(('127.0.0.1',0),api.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.tokens={}
        for user in ('admin','doctora','paciente','recepcion','consulta'):
            self.tokens[user]=self.auth.login(user,'Demo2026!')['token']

    def tearDown(self):
        self.server.shutdown();self.thread.join(timeout=5);self.server.server_close()
        api.SERVICE,api.AUTH=self.old_svc,self.old_auth
        super().tearDown()

    def call(self,path,user=None,body=None):
        headers={'Accept':'application/json'}
        if user:headers['Authorization']=f'Bearer {self.tokens[user]}'
        data=None if body is None else json.dumps(body).encode('utf-8')
        if data is not None:headers['Content-Type']='application/json'
        req=Request(self.url+path, data=data,headers=headers, method='POST' if body is not None else 'GET')
        try:
            with urlopen(req, timeout=5) as r:
                return r.status,json.loads(r.read())
        except HTTPError as e:
            return e.code,json.loads(e.read())

    def test_sin_login_no_puede_ver_citas(self):
        self.assertEqual(self.call('/api/mvp/citas')[0],401)
        self.assertEqual(self.call('/api/mvp/doctores')[0],401)

    def test_cinco_roles_login_http(self):
        roles=set()
        for user in self.tokens:
            status, data=self.call('/api/mvp/auth/me',user=user)
            self.assertEqual(status,200)
            roles.add(data['usuario']['rol'])
        self.assertEqual(len(roles),5)

    def test_login_http_usuario_incorrecto(self):
        self.assertEqual(self.call('/api/mvp/auth/login',body={'usuario':'admin','password':'error'})[0],401)

    def test_perfil_consulta_no_lee_datos_personales(self):
        self.assertEqual(self.call('/api/mvp/doctores','consulta')[0],200)
        self.assertEqual(self.call('/api/mvp/citas','consulta')[0],403)
        self.assertEqual(self.call('/api/mvp/resumen','consulta')[0],403)
        self.assertEqual(self.call('/api/mvp/usuarios','consulta')[0],403)

    def test_paciente_y_doctor_no_agendan(self):
        body={'doctor_id':'MED001','fecha':'2026-11-10','inicio':480,'duracion':30,'paciente_nombre':'Prueba Uno'}
        for user in ('paciente','doctora','consulta'):
            with self.subTest(user=user):
                self.assertEqual(self.call('/api/mvp/citas',user,body)[0],403)

    def test_recepecion_agenda_y_cancela(self):
        body={'doctor_id':'MED001','fecha':'2026-11-10','inicio':480,'duracion':30,'paciente_nombre':'Prueba Uno'}
        status,data=self.call('/api/mvp/citas','recepcion',body)
        self.assertEqual(status,201)
        self.assertEqual(self.call('/api/mvp/citas','recepcion',body)[0],400)
        self.assertEqual(self.call(f"/api/mvp/citas/{data['id']}/cancelar",'recepcion',{})[0],200)
        self.assertEqual(self.call('/api/mvp/citas','recepcion',body)[0],201)

    def test_doctor_solo_su_agenda(self):
        self.service.agendar('MED001','2026-11-10',480,30,'Paciente A')
        self.service.agendar('MED002','2026-11-10',480,30,'Paciente B')
        status, data=self.call('/api/mvp/citas?doctor=MED002','doctora')
        self.assertEqual(status,200)
        self.assertEqual([c['doctor_id'] for c in data['citas']],['MED001'])
        self.assertEqual(self.call('/api/mvp/disponibilidad?doctor=MED002&fecha=2026-11-10&duracion=30','doctora')[0],403)

    def test_paciente_no_ve_citas_ajenas(self):
        pid=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id']
        self.service.agendar('MED001','2026-11-10',480,30,paciente_id=pid)
        self.service.agendar('MED002','2026-11-10',480,30,'Paciente Ajeno')
        status, data=self.call('/api/mvp/citas','paciente')
        self.assertEqual(status,200)
        self.assertEqual(len(data['citas']),1)
        self.assertEqual(data['citas'][0]['paciente_id'],pid)

    def test_admin_agrega_medico_otros_no(self):
        body={'id':'MED009','nombre':'Dra. María Sol','especialidad':'Pediatría'}
        self.assertEqual(self.call('/api/mvp/doctores','recepcion',body)[0],403)
        self.assertEqual(self.call('/api/mvp/doctores','admin',body)[0],201)
        self.assertEqual(self.call('/api/mvp/doctores','admin',body)[0],400)

    def test_paciente_no_cancela_cita_propia(self):
        pid=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id']
        c=self.service.agendar('MED001','2026-11-10',480,30,paciente_id=pid)
        self.assertEqual(self.call(f"/api/mvp/citas/{c['id']}/cancelar",'paciente',{})[0],403)

    def test_administrador_puede_ver_panel(self):
        for path in ('/api/mvp/resumen','/api/mvp/usuarios','/api/mvp/paciente-demo'):
            self.assertEqual(self.call(path,'admin')[0],200)
        for path in ('/api/mvp/resumen','/api/mvp/usuarios'):
            self.assertEqual(self.call(path,'recepcion')[0],403)


if __name__ == '__main__':unittest.main()
