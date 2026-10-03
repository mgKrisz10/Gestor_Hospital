import unittest
from copy import deepcopy

from src.gestor_citas import (
    Cita,
    Error,
    Exito,
    HORARIO_LABORAL,
    Intervalo,
    buscar_disponibilidad,
    calcular_fin,
    calcular_huecos,
    dividir_hueco,
    fusionar,
)


class GestorCitasTests(unittest.TestCase):
    def assertDisponibles(self, citas, duracion, esperados):
        original = deepcopy(citas)
        resultado = buscar_disponibilidad(citas, HORARIO_LABORAL, duracion)
        self.assertIsInstance(resultado, Exito)
        obtenidos = [(x.inicio, x.fin) for x in resultado.valor]
        self.assertEqual(obtenidos, esperados)
        self.assertEqual(citas, original)

    def test_01_calcular_fin(self):
        self.assertEqual(calcular_fin(Cita(540, 30)), 570)

    def test_02_duracion_negativa(self):
        resultado = buscar_disponibilidad((), HORARIO_LABORAL, -15)
        self.assertIsInstance(resultado, Error)

    def test_03_duracion_cero(self):
        resultado = buscar_disponibilidad((), HORARIO_LABORAL, 0)
        self.assertIsInstance(resultado, Error)

    def test_04_duracion_mayor_que_jornada(self):
        resultado = buscar_disponibilidad((), HORARIO_LABORAL, 361)
        self.assertIsInstance(resultado, Error)

    def test_05_sin_citas(self):
        self.assertDisponibles((), 60, [(480, 540), (540, 600), (600, 660), (660, 720), (720, 780), (780, 840)])

    def test_06_cita_al_inicio(self):
        self.assertDisponibles((Cita(480, 30),), 30, [(510, 540), (540, 570), (570, 600), (600, 630), (630, 660), (660, 690), (690, 720), (720, 750), (750, 780), (780, 810), (810, 840)])

    def test_07_cita_al_final(self):
        self.assertDisponibles((Cita(810, 30),), 30, [(480, 510), (510, 540), (540, 570), (570, 600), (600, 630), (630, 660), (660, 690), (690, 720), (720, 750), (750, 780), (780, 810)])

    def test_08_dos_citas_separadas(self):
        self.assertDisponibles((Cita(540, 30), Cita(660, 30)), 30, [(480, 510), (510, 540), (570, 600), (600, 630), (630, 660), (690, 720), (720, 750), (750, 780), (780, 810), (810, 840)])

    def test_09_traslape(self):
        resultado = buscar_disponibilidad((Cita(540, 60), Cita(570, 30)), HORARIO_LABORAL, 30)
        self.assertIsInstance(resultado, Exito)
        self.assertEqual(resultado.valor[0], Intervalo(480, 510))

    def test_10_cita_fuera_del_horario(self):
        resultado = buscar_disponibilidad((Cita(830, 20),), HORARIO_LABORAL, 30)
        self.assertIsInstance(resultado, Error)

    def test_11_citas_fuera_de_orden(self):
        self.assertDisponibles((Cita(660, 30), Cita(540, 30)), 30, [(480, 510), (510, 540), (570, 600), (600, 630), (630, 660), (690, 720), (720, 750), (750, 780), (780, 810), (810, 840)])

    def test_12_hueco_menor_que_duracion(self):
        resultado = buscar_disponibilidad((Cita(480, 45), Cita(510, 15)), HORARIO_LABORAL, 30)
        self.assertIsInstance(resultado, Exito)
        self.assertEqual(resultado.valor[0], Intervalo(525, 555))

    def test_13_division_de_hueco(self):
        self.assertEqual(dividir_hueco(Intervalo(480, 555), 30), (Intervalo(480, 510), Intervalo(510, 540)))

    def test_14_fusionar_no_modifica(self):
        datos = (Intervalo(540, 570), Intervalo(560, 600))
        original = datos
        self.assertEqual(fusionar(datos), (Intervalo(540, 600),))
        self.assertEqual(datos, original)

    def test_15_entrada_inmutable(self):
        citas = (Cita(540, 30), Cita(600, 60), Cita(630, 30))
        original = citas
        buscar_disponibilidad(citas, HORARIO_LABORAL, 30)
        self.assertEqual(citas, original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
