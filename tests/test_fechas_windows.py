"""Validaciones de fechas y horarios para el hospital en Ciudad de México."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.autenticacion import AutenticacionService
from src.mvp import ReglaNegocioError
from src.operaciones_extra import HospitalService

DATA = Path(__file__).resolve().parents[1] / 'data' / 'citas_ficticias.json'
TZ = timezone(timedelta(hours=-6))


class FechasWindowsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.svc = HospitalService(Path(self.temp.name) / 'hospital.sqlite3', DATA)
        AutenticacionService(self.svc.db_path)
        self.hoy = '2026-11-12'
        self.manana = '2026-11-13'
        self.ayer = '2026-11-11'

    def _momento(self, hour, minute=0):
        return patch.object(
            HospitalService, 'ahora',
            return_value=datetime(2026, 11, 12, hour, minute, tzinfo=TZ)
        )

    def test_manana_08_es_valida_aunque_ahora_sean_las_17(self):
        with self._momento(17):
            espacios = self.svc.disponibilidad('MED001', self.manana, 30)['intervalos']
            self.assertEqual(espacios[0]['inicio'], 480)
            cita = self.svc.agendar('MED001', self.manana, 480, 30, paciente_id=1)
            self.assertEqual(cita['estado'], 'programada')

    def test_ayer_no_se_puede_reservar(self):
        with self._momento(9):
            with self.assertRaisesRegex(ReglaNegocioError, 'anteriores'):
                self.svc.agendar('MED001', self.ayer, 600, 30, paciente_id=1)

    def test_hoy_a_hora_pasada_no_se_puede_reservar(self):
        with self._momento(10, 10):
            with self.assertRaisesRegex(ReglaNegocioError, 'horarios que ya pasaron'):
                self.svc.agendar('MED001', self.hoy, 480, 30, paciente_id=1)

    def test_hoy_a_hora_futura_si_se_puede_reservar(self):
        with self._momento(9, 10):
            cita = self.svc.agendar('MED001', self.hoy, 600, 30, paciente_id=1)
            self.assertEqual(cita['estado'], 'programada')

    def test_disponibilidad_filtra_solo_hoy(self):
        with self._momento(9, 10):
            actual = self.svc.disponibilidad('MED001', self.hoy, 30)['intervalos']
            manana = self.svc.disponibilidad('MED001', self.manana, 30)['intervalos']
            self.assertTrue(actual and min(x['inicio'] for x in actual) > 550)
            self.assertEqual(manana[0]['inicio'], 480)


if __name__ == '__main__':
    unittest.main()
