"""Pruebas de operaciones documentadas: consulta, alta, cancelacion y sus validaciones."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.mvp import HospitalService, ReglaNegocioError


class MVPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'demo.sqlite3'
        self.service = HospitalService(db_path=self.path)
        self.fecha = '2026-11-09'

    def test_01_doctores_precargados(self):
        self.assertEqual([d['id'] for d in self.service.listar_doctores()], ['MED001', 'MED002', 'MED003'])

    def test_02_disponibilidad_agenda_vacia_30_minutos(self):
        res = self.service.disponibilidad('MED001', self.fecha, 30)
        self.assertEqual(len(res['intervalos']), 12)
        self.assertEqual(res['intervalos'][0]['inicio'], 480)
        self.assertEqual(res['intervalos'][-1]['fin'], 840)

    def test_03_disponibilidad_agenda_vacia_60_minutos(self):
        self.assertEqual(len(self.service.disponibilidad('MED003', self.fecha, 60)['intervalos']), 6)

    def test_04_agendar_y_persistir(self):
        r = self.service.agendar('MED001', self.fecha, 480, 30, 'Paciente de Prueba', '5512345678')
        self.assertGreater(r['id'], 0)
        otra = HospitalService(db_path=self.path)
        agenda = otra.listar_citas()
        self.assertEqual(len(agenda), 1)
        self.assertEqual(agenda[0]['paciente_nombre'], 'Paciente de Prueba')
        self.assertEqual(agenda[0]['estado'], 'programada')
        self.assertNotIn(480, [i['inicio'] for i in otra.disponibilidad('MED001', self.fecha, 30)['intervalos']])

    def test_05_rechazo_cita_duplicada(self):
        self.service.agendar('MED001', self.fecha, 480, 30, 'Alicia')
        with self.assertRaisesRegex(ReglaNegocioError, 'ocupado'):
            self.service.agendar('MED001', self.fecha, 480, 30, 'Roberto')
        self.assertEqual(len(self.service.listar_citas()), 1)

    def test_06_rechazo_empalme_parcial(self):
        self.service.agendar('MED001', self.fecha, 600, 60, 'Paciente A')
        with self.assertRaisesRegex(ReglaNegocioError, 'ocupado'):
            self.service.agendar('MED001', self.fecha, 630, 30, 'Paciente B')
        with self.assertRaisesRegex(ReglaNegocioError, 'ocupado'):
            self.service.agendar('MED001', self.fecha, 590, 30, 'Paciente C')
        self.assertEqual(len(self.service.listar_citas()), 1)

    def test_07_contiguas_son_validas(self):
        self.service.agendar('MED001', self.fecha, 600, 30, 'Paciente A')
        self.service.agendar('MED001', self.fecha, 630, 30, 'Paciente B')
        self.assertEqual(len(self.service.listar_citas()), 2)

    def test_08_otro_doctor_mismo_horario_valido(self):
        self.service.agendar('MED001', self.fecha, 480, 30, 'Paciente A')
        self.service.agendar('MED002', self.fecha, 480, 30, 'Paciente B')
        self.assertEqual(len(self.service.listar_citas()), 2)

    def test_09_otra_fecha_mismo_horario_valida(self):
        self.service.agendar('MED001', self.fecha, 480, 30, 'Paciente A')
        self.service.agendar('MED001', '2026-11-10', 480, 30, 'Paciente B')
        self.assertEqual(len(self.service.listar_citas()), 2)
        self.assertEqual(len(self.service.listar_citas(self.fecha)), 1)

    def test_10_cancelar_libera_horario(self):
        i = self.service.agendar('MED001', self.fecha, 480, 30, 'Paciente A')['id']
        self.assertEqual(self.service.cancelar(i)['estado'], 'cancelada')
        self.assertIn(480, [r['inicio'] for r in self.service.disponibilidad('MED001', self.fecha, 30)['intervalos']])
        self.assertEqual(self.service.listar_citas()[0]['estado'], 'cancelada')
        self.service.agendar('MED001', self.fecha, 480, 30, 'Paciente B')
        self.assertEqual(len(self.service.listar_citas()), 2)

    def test_11_no_se_cancela_dos_veces(self):
        i = self.service.agendar('MED001', self.fecha, 480, 30, 'Paciente A')['id']
        self.service.cancelar(i)
        with self.assertRaisesRegex(ReglaNegocioError, 'cancelada'):
            self.service.cancelar(i)
        self.assertEqual(len(self.service.listar_citas()), 1)

    def test_12_no_se_cancela_cita_inexistente(self):
        with self.assertRaisesRegex(ReglaNegocioError, 'no encontrada'):
            self.service.cancelar(9999)

    def test_13_rechaza_duracion_no_positiva_y_fuera_de_jornada(self):
        for duracion in (0,-15,361):
            with self.subTest(duracion=duracion), self.assertRaises(ReglaNegocioError):
                self.service.agendar('MED001', self.fecha, 480, duracion, 'Paciente A')
        for inicio, duracion in ((479, 30),(830, 30),(841, 15)):
            with self.subTest(inicio=inicio, duracion=duracion), self.assertRaises(ReglaNegocioError):
                self.service.agendar('MED001', self.fecha, inicio, duracion, 'Paciente A')
        self.assertEqual(self.service.listar_citas(), [])

    def test_14_limites_horario_permitidos(self):
        self.service.agendar('MED001', self.fecha, 480, 30, 'Paciente A')
        self.service.agendar('MED001', self.fecha, 810, 30, 'Paciente B')
        self.assertEqual(len(self.service.listar_citas()), 2)

    def test_15_rechazar_fecha_imposible(self):
        for fecha in ('2026-02-30','2026-11-9','no-fecha',''):
            with self.subTest(fecha=fecha), self.assertRaises(ReglaNegocioError):
                self.service.agendar('MED001',fecha,480,30,'Paciente A')

    def test_16_rechaza_paciente_vacio(self):
        for nombre in ('', '  ', 'A'):
            with self.subTest(nombre=nombre), self.assertRaises(ReglaNegocioError):
                self.service.agendar('MED001',self.fecha,480,30,nombre)

    def test_17_rechaza_doctor_inexistente(self):
        with self.assertRaisesRegex(ReglaNegocioError, 'Doctor no encontrado'):
            self.service.disponibilidad('MED999',self.fecha,30)
        with self.assertRaisesRegex(ReglaNegocioError, 'Doctor no encontrado'):
            self.service.agendar('MED999',self.fecha,480,30,'Paciente A')

    def test_18_concurrencia_una_sola_cita(self):
        def agendar(_):
            try:
                return self.service.agendar('MED001',self.fecha,480,30,'Paciente de prueba')
            except ReglaNegocioError:
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(agendar,range(4)))
        self.assertEqual(sum(bool(r) for r in results), 1)
        self.assertEqual(len(self.service.listar_citas()), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
