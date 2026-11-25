"""Cobertura de catálogo, múltiples especialidades, reagendado y fail closed."""
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from src.mvp import ReglaNegocioError
from src.operaciones_extra import HospitalService
from src import sqlserver_backend

DATA=Path(__file__).resolve().parents[1]/'data'/'citas_ficticias.json'


class EspecialidadesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc=HospitalService(Path(self.tmp.name)/'hospital.db',DATA)
        self.fecha=(self.svc.hoy()+timedelta(days=5)).isoformat()

    def test_catalogo_cerrado_sin_fisioterapia(self):
        self.assertIn('Cardiología',self.svc.listar_especialidades())
        self.assertIn('Neurocirugía',self.svc.listar_especialidades())
        self.assertNotIn('Fisioterapia',self.svc.listar_especialidades())
        with self.assertRaisesRegex(ReglaNegocioError,'no autorizada'):
            self.svc.registrar_doctor('MED900','Doctor Nuevo',especialidades=['Fisioterapia'])

    def test_medico_con_dos_especialidades_y_acento_compatible(self):
        self.svc.registrar_doctor('MED900','Doctora Alta',especialidades=['Cardiologia','Neurocirugía'])
        doc=next(d for d in self.svc.listar_doctores() if d['id']=='MED900')
        self.assertEqual(doc['especialidades'],['Cardiología','Neurocirugía'])
        self.assertEqual(self.svc.agendar('MED900',self.fecha,480,30,'Paciente Uno',especialidad='Neurocirugia')['estado'],'programada')

    def test_rechazar_especialidad_ajena_en_cita(self):
        with self.assertRaisesRegex(ReglaNegocioError,'no atiende'):
            self.svc.agendar('MED002',self.fecha,480,30,'Paciente Uno',especialidad='Dermatología')

    def test_reagendar_solo_medicos_compatibles(self):
        self.svc.registrar_doctor('MED900','Doctora Alta',especialidades=['Cardiología','Neurocirugía'])
        self.svc.registrar_doctor('MED901','Doctor Compatible',especialidades=['Neurocirugía'])
        cita=self.svc.agendar('MED900',self.fecha,480,30,paciente_nombre='Paciente',especialidad='Neurocirugía')
        compatibles=self.svc.medicos_para_reagendar(cita['id'])
        ids={d['id'] for d in compatibles['doctores']}
        self.assertIn('MED901',ids)
        self.assertNotIn('MED002',ids)
        with self.assertRaisesRegex(ReglaNegocioError,'no atiende'):
            self.svc.reprogramar(cita['id'],'MED002',self.fecha,540,30)
        self.assertEqual(self.svc.reprogramar(cita['id'],'MED901',self.fecha,540,30)['estado'],'programada')
        with self.svc._conexion() as con:
            self.assertEqual(con.execute('SELECT especialidad FROM citas WHERE id=?',(cita['id'],)).fetchone()[0],'Neurocirugía')

    def test_registro_duplicado_especialidades_rechazado(self):
        with self.assertRaisesRegex(ReglaNegocioError,'repitas'):
            self.svc.registrar_doctor('MED900','Doctora Alta',especialidades=['Cardiologia','Cardiología'])

    def test_migracion_sqlite_conserva_especialidad_cita(self):
        cita=self.svc.agendar('MED001',self.fecha,540,30,'Paciente')
        nuevo=HospitalService(self.svc.db_path,DATA)
        self.assertEqual(nuevo.confirmacion(cita['id'])['estado'],'programada')
        with nuevo._conexion() as con:
            spec=con.execute('SELECT especialidad FROM citas WHERE id=?',(cita['id'],)).fetchone()['especialidad']
            self.assertEqual(spec,'Medicina general')

    def test_sqlserver_no_se_reconvierte_silenciosamente_a_sqlite(self):
        with patch.dict(os.environ, {'HOSPITAL_DB_BACKEND':'sqlserver'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'HOSPITAL_SQLSERVER_CONNECTION_STRING'):
                sqlserver_backend.cadena_conexion()
            with self.assertRaisesRegex(RuntimeError,'HOSPITAL_SQLSERVER_CONNECTION_STRING'):
                HospitalService(Path(self.tmp.name)/'hospital.db',DATA)


if __name__=='__main__': unittest.main()

class AdaptadorSqlServerSinInstanciaTests(unittest.TestCase):
    def test_fila_es_compatible_con_diccionario_y_posicion(self):
        from src.sqlserver_backend import Fila
        value=Fila(id=7,nombre='Paciente')
        self.assertEqual(value[0],7)
        self.assertEqual(value['nombre'],'Paciente')
        self.assertEqual(dict(value)['id'],7)

    def test_esquema_tsql_contiene_todas_las_entidades(self):
        schema=(Path(__file__).resolve().parents[1]/'sqlserver'/'schema.sql').read_text(encoding='utf-8')
        for name in ('doctores','pacientes','citas','usuarios','notificaciones',
                     'ausencias','suspensiones_doctor','especialidades_hospital','doctor_especialidades'):
            self.assertIn('dbo.'+name,schema)

    def test_insercion_odbc_devuelve_identity_sin_consulta_adicional(self):
        from src.sqlserver_backend import Conexion
        class Cursor:
            rowcount=1
            description=[('id',None,None,None,None,None,None)]
            sql=''
            def execute(self,sql,*args):
                self.sql=sql
                self.args=args
                return self
            def fetchone(self): return (99,)
        class Raw:
            def __init__(self): self.cursor_instance=Cursor()
            def cursor(self): return self.cursor_instance
        raw=Raw()
        con=Conexion(raw)
        inserted=con.execute('INSERT INTO pacientes(nombre,telefono) VALUES (?,?)',('A','123'))
        self.assertEqual(inserted.lastrowid,99)
        self.assertIn('OUTPUT INSERTED.id',raw.cursor_instance.sql)
        self.assertEqual(raw.cursor_instance.args,('A','123'))
