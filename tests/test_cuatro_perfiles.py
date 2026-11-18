"""El perfil retirado no vuelve a aparecer en bases nuevas ni existentes."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import timedelta

from src.autenticacion import AutenticacionService, SinSesion
from src.mvp import ReglaNegocioError
from src.operaciones_extra import HospitalService

DATA = Path(__file__).resolve().parents[1] / 'data' / 'citas_ficticias.json'


class CuatroPerfilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'hospital.sqlite3'
        self.svc = HospitalService(self.db, DATA)
        self.auth = AutenticacionService(self.db)

    def test_solo_cuatro_perfiles_al_instalar(self):
        self.assertEqual({u['rol'] for u in self.auth.usuarios()},
                         {'administrador','doctor','paciente','recepcion'})
        self.assertEqual(len(self.auth.usuarios()), 6)
        with self.assertRaises(SinSesion):
            self.auth.login('consulta','Demo2026!')

    def test_no_se_puede_crear_perfil_eliminado(self):
        with self.assertRaisesRegex(ReglaNegocioError, 'Rol no válido'):
            self.auth.crear_usuario('consulta','Personal antiguo','personal_autorizado','Demo2026!')
        admin = next(u for u in self.auth.usuarios() if u['usuario']=='admin')
        with self.assertRaisesRegex(ReglaNegocioError,'Rol no válido'):
            self.auth.actualizar_usuario(admin['id'],'admin','Administrador','personal_autorizado')

    def test_migrar_cuenta_antigua_sin_borrar_citas(self):
        # Base antigua permitía cinco roles en el CHECK de usuarios. Reproducirla
        # y añadir su cuenta antes de reiniciar el servicio de autenticación.
        cita = self.svc.agendar('MED001',
            (self.svc.hoy()+timedelta(days=3)).isoformat(),
            540, 30, paciente_id=self.auth.login('paciente','Demo2026!')['usuario']['paciente_id'])
        with sqlite3.connect(self.db) as con:
            con.execute('PRAGMA foreign_keys=OFF')
            ddl = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='usuarios'").fetchone()[0]
            self.assertIn("'administrador','doctor','paciente','recepcion'", ddl)
            con.execute('ALTER TABLE usuarios RENAME TO usuarios_old')
            con.execute(ddl.replace('CREATE TABLE usuarios','CREATE TABLE usuarios').replace(
              "'administrador','doctor','paciente','recepcion'",
              "'administrador','doctor','paciente','recepcion','personal_autorizado'"))
            columns='id,usuario,nombre,rol,salt,password_hash,doctor_id,paciente_id,activo'
            con.execute(f'INSERT INTO usuarios({columns}) SELECT {columns} FROM usuarios_old')
            con.execute('DROP TABLE usuarios_old')
            con.execute("INSERT INTO usuarios(usuario,nombre,rol,salt,password_hash,doctor_id,paciente_id) "
                "SELECT 'consulta','Personal autorizado','personal_autorizado',salt,password_hash,NULL,NULL "
                "FROM usuarios WHERE usuario='admin'")
        migrated = AutenticacionService(self.db)
        self.assertNotIn('consulta', {u['usuario'] for u in migrated.usuarios()})
        with self.assertRaises(SinSesion):
            migrated.login('consulta','Demo2026!')
        self.assertEqual(self.svc.confirmacion(cita['id'])['estado'],'programada')
        self.assertEqual(len(migrated.usuarios()),6)

if __name__=='__main__': unittest.main()
