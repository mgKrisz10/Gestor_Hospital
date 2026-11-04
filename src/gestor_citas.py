"""Cálculo funcional de disponibilidad de la primera entrega."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from functools import reduce
from itertools import chain
from typing import Callable, Sequence, Tuple, Union

@dataclass(frozen=True)
class Cita:
    inicio: int
    duracion: int

@dataclass(frozen=True)
class Intervalo:
    inicio: int
    fin: int

@dataclass(frozen=True)
class Exito:
    valor: object

@dataclass(frozen=True)
class Error:
    mensaje: str

Resultado = Union[Exito, Error]
HORARIO_LABORAL = Intervalo(480, 840)

def calcular_fin(cita: Cita) -> int: return cita.inicio + cita.duracion

def validar_cita(cita: Cita, horario: Intervalo) -> Resultado:
    if cita.duracion <= 0: return Error('Duracion invalida')
    if cita.inicio < horario.inicio or calcular_fin(cita) > horario.fin: return Error('Cita fuera del horario laboral')
    return Exito(cita)

def cita_a_intervalo(cita: Cita) -> Intervalo: return Intervalo(cita.inicio, calcular_fin(cita))

def ordenar_por_inicio(intervalos: Sequence[Intervalo]) -> Tuple[Intervalo, ...]:
    return tuple(sorted(intervalos, key=lambda i: i.inicio))

def fusionar(intervalos: Sequence[Intervalo]) -> Tuple[Intervalo, ...]:
    def acumular(acc, actual):
        if not acc: return (actual,)
        ultimo = acc[-1]
        if actual.inicio <= ultimo.fin:
            return acc[:-1] + (Intervalo(ultimo.inicio, max(ultimo.fin, actual.fin)),)
        return acc + (actual,)
    return reduce(acumular, intervalos, ())

def calcular_huecos(ocupados, horario):
    puntos = (Intervalo(horario.inicio, horario.inicio), *ocupados, Intervalo(horario.fin, horario.fin))
    pares = zip(puntos[:-1], puntos[1:])
    candidatos = tuple(map(lambda par: Intervalo(par[0].fin, par[1].inicio), pares))
    return tuple(filter(lambda h: h.fin > h.inicio, candidatos))

def dividir_hueco(hueco, duracion):
    cantidad = (hueco.fin-hueco.inicio)//duracion
    return tuple(map(lambda k: Intervalo(hueco.inicio+k*duracion, hueco.inicio+(k+1)*duracion), range(cantidad)))

def formatear_hora(minutos):
    h, m = divmod(minutos,60)
    return f'{h:02d}:{m:02d}'

def componer(*funciones: Callable) -> Callable:
    def pipeline(valor): return reduce(lambda actual, fn: fn(actual), funciones, valor)
    return pipeline

def buscar_disponibilidad(citas, horario, duracion):
    if duracion <= 0: return Error('Duracion invalida')
    if duracion > horario.fin - horario.inicio: return Error('La duracion excede el horario laboral')
    validaciones = tuple(map(lambda c: validar_cita(c,horario), citas))
    errores = tuple(filter(lambda v: isinstance(v,Error), validaciones))
    if errores: return errores[0]
    pipeline = componer(lambda cs: tuple(map(cita_a_intervalo,cs)), ordenar_por_inicio, fusionar,
        lambda ocupadas: calcular_huecos(ocupadas,horario),
        lambda huecos: tuple(chain.from_iterable(map(lambda h: dividir_hueco(h,duracion),huecos))))
    return Exito(pipeline(tuple(citas)))

def resultado_a_dict(resultado):
    if isinstance(resultado,Error): return {'ok':False,'error':resultado.mensaje}
    return {'ok':True,'intervalos':[asdict(i) for i in resultado.valor],'horario':asdict(HORARIO_LABORAL)}
