"""Gestor de Citas Medicas - funcionalidad de busqueda de horarios disponibles.

La logica de negocio es deliberadamente independiente de la interfaz web.
No usa paquetes externos: solo la biblioteca estandar de Python.
"""
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
HORARIO_LABORAL = Intervalo(480, 840)  # 08:00 - 14:00


def calcular_fin(cita: Cita) -> int:
    return cita.inicio + cita.duracion


def validar_cita(cita: Cita, horario: Intervalo) -> Resultado:
    if cita.duracion <= 0:
        return Error("Duracion invalida")
    if cita.inicio < horario.inicio or calcular_fin(cita) > horario.fin:
        return Error("Cita fuera del horario laboral")
    return Exito(cita)


def cita_a_intervalo(cita: Cita) -> Intervalo:
    return Intervalo(cita.inicio, calcular_fin(cita))


def ordenar_por_inicio(intervalos: Sequence[Intervalo]) -> Tuple[Intervalo, ...]:
    return tuple(sorted(intervalos, key=lambda intervalo: intervalo.inicio))


def fusionar(intervalos: Sequence[Intervalo]) -> Tuple[Intervalo, ...]:
    def acumular(
        acumulados: Tuple[Intervalo, ...], actual: Intervalo
    ) -> Tuple[Intervalo, ...]:
        if not acumulados:
            return (actual,)
        ultimo = acumulados[-1]
        if actual.inicio <= ultimo.fin:
            combinado = Intervalo(ultimo.inicio, max(ultimo.fin, actual.fin))
            return acumulados[:-1] + (combinado,)
        return acumulados + (actual,)

    return reduce(acumular, intervalos, ())


def calcular_huecos(
    ocupados: Sequence[Intervalo], horario: Intervalo
) -> Tuple[Intervalo, ...]:
    puntos = (
        Intervalo(horario.inicio, horario.inicio),
        *ocupados,
        Intervalo(horario.fin, horario.fin),
    )
    pares = zip(puntos[:-1], puntos[1:])
    candidatos = tuple(
        map(lambda par: Intervalo(par[0].fin, par[1].inicio), pares)
    )
    return tuple(filter(lambda hueco: hueco.fin > hueco.inicio, candidatos))


def dividir_hueco(hueco: Intervalo, duracion: int) -> Tuple[Intervalo, ...]:
    cantidad = (hueco.fin - hueco.inicio) // duracion
    return tuple(
        map(
            lambda k: Intervalo(
                hueco.inicio + k * duracion,
                hueco.inicio + (k + 1) * duracion,
            ),
            range(cantidad),
        )
    )


def formatear_hora(minutos: int) -> str:
    horas, mins = divmod(minutos, 60)
    return f"{horas:02d}:{mins:02d}"


def componer(*funciones: Callable) -> Callable:
    def pipeline(valor):
        return reduce(lambda actual, funcion: funcion(actual), funciones, valor)

    return pipeline


def buscar_disponibilidad(
    citas: Sequence[Cita], horario: Intervalo, duracion: int
) -> Resultado:
    """Calcula bloques disponibles sin modificar las citas de entrada."""
    if duracion <= 0:
        return Error("Duracion invalida")
    if duracion > horario.fin - horario.inicio:
        return Error("La duracion excede el horario laboral")

    validaciones = tuple(map(lambda cita: validar_cita(cita, horario), citas))
    errores = tuple(filter(lambda r: isinstance(r, Error), validaciones))
    if errores:
        return errores[0]

    pipeline = componer(
        lambda cs: tuple(map(cita_a_intervalo, cs)),
        ordenar_por_inicio,
        fusionar,
        lambda ocupadas: calcular_huecos(ocupadas, horario),
        lambda huecos: tuple(
            chain.from_iterable(map(lambda hueco: dividir_hueco(hueco, duracion), huecos))
        ),
    )
    return Exito(pipeline(tuple(citas)))


def intervalo_a_dict(intervalo: Intervalo) -> dict:
    return asdict(intervalo)


def resultado_a_dict(resultado: Resultado) -> dict:
    if isinstance(resultado, Error):
        return {"ok": False, "error": resultado.mensaje}
    return {
        "ok": True,
        "intervalos": [intervalo_a_dict(i) for i in resultado.valor],
        "horario": intervalo_a_dict(HORARIO_LABORAL),
    }


def ejecutar_ejemplo() -> None:
    citas = (Cita(540, 30), Cita(600, 60), Cita(630, 30))
    resultado = buscar_disponibilidad(citas, HORARIO_LABORAL, 30)
    if isinstance(resultado, Error):
        print(f"Error: {resultado.mensaje}")
        return
    print("Horarios disponibles:")
    for intervalo in resultado.valor:
        print(f"{formatear_hora(intervalo.inicio)} - {formatear_hora(intervalo.fin)}")


if __name__ == "__main__":
    ejecutar_ejemplo()
