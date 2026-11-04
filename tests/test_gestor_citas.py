import unittest
from copy import deepcopy
from src.gestor_citas import Cita, Error, Exito, HORARIO_LABORAL, Intervalo, buscar_disponibilidad, calcular_fin, dividir_hueco, fusionar


class GestorCitasTests(unittest.TestCase):
    def assertDisponibles(self, citas, duracion, esperados):
        original = deepcopy(citas)
        resultado = buscar_disponibilidad(citas, HORARIO_LABORAL, duracion)
        self.assertIsInstance(resultado, Exito)
        self.assertEqual([(x.inicio,x.fin) for x in resultado.valor], esperados)
        self.assertEqual(citas,original)

    def test_01_calcular_fin(self): self.assertEqual(calcular_fin(Cita(540,30)),570)
    def test_02_duracion_negativa(self): self.assertIsInstance(buscar_disponibilidad((),HORARIO_LABORAL,-15),Error)
    def test_03_duracion_cero(self): self.assertIsInstance(buscar_disponibilidad((),HORARIO_LABORAL,0),Error)
    def test_04_duracion_mayor_que_jornada(self): self.assertIsInstance(buscar_disponibilidad((),HORARIO_LABORAL,361),Error)
    def test_05_sin_citas(self): self.assertDisponibles((),60,[(480,540),(540,600),(600,660),(660,720),(720,780),(780,840)])
    def test_06_cita_al_inicio(self): self.assertDisponibles((Cita(480,30),),30,[(i,i+30) for i in range(510,840,30)])
    def test_07_cita_al_final(self): self.assertDisponibles((Cita(810,30),),30,[(i,i+30) for i in range(480,810,30)])
    def test_08_dos_citas_separadas(self): self.assertDisponibles((Cita(540,30),Cita(660,30)),30,[(i,i+30) for i in range(480,840,30) if i not in (540,660)])
    def test_09_traslape(self):
        result = buscar_disponibilidad((Cita(540,60),Cita(570,30)),HORARIO_LABORAL,30)
        self.assertIsInstance(result,Exito)
        self.assertEqual(result.valor[0],Intervalo(480,510))
    def test_10_cita_fuera_del_horario(self): self.assertIsInstance(buscar_disponibilidad((Cita(830,20),),HORARIO_LABORAL,30),Error)
    def test_11_citas_fuera_de_orden(self): self.assertDisponibles((Cita(660,30),Cita(540,30)),30,[(i,i+30) for i in range(480,840,30) if i not in (540,660)])
    def test_12_hueco_menor_que_duracion(self):
        result=buscar_disponibilidad((Cita(480,45),Cita(510,15)),HORARIO_LABORAL,30)
        self.assertEqual(result.valor[0],Intervalo(525,555))
    def test_13_division_hueco(self): self.assertEqual(dividir_hueco(Intervalo(480,555),30),(Intervalo(480,510),Intervalo(510,540)))
    def test_14_fusionar_no_modifica(self):
        data=(Intervalo(540,570),Intervalo(560,600)); old=data
        self.assertEqual(fusionar(data),(Intervalo(540,600),)); self.assertEqual(data,old)
    def test_15_entrada_inmutable(self):
        citas=(Cita(540,30),Cita(600,60),Cita(630,30)); old=citas
        buscar_disponibilidad(citas,HORARIO_LABORAL,30); self.assertEqual(citas,old)
