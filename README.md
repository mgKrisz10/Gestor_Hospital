# Gestor de Citas Médicas - MVP acotado del segundo parcial

Materia: Paradigmas de Programación · ESCOM-IPN · grupo 3CV4.

## Alcance evaluable (tres operaciones)

1. **Consultar horarios libres**: elegir uno de los tres médicos, fecha válida y duración de 15, 30, 45 o 60 minutos. Jornada de 08:00 a 14:00. Se muestran bloques disponibles y citas ocupadas.
2. **Agendar cita**: elegir uno de esos horarios, indicar nombre del paciente y confirmar. Se guarda en SQLite y aparece en la tabla de citas. No se permiten empalmes para el mismo médico y fecha.
3. **Cancelar cita**: utilizar el botón Cancelar en una cita programada. La cita queda marcada como cancelada y su horario se libera.

La tabla de citas, el catálogo de tres médicos y SQLite son **elementos auxiliares** de esas tres operaciones, no funciones de administración independiente. La primera etapa utilizó datos ficticios de agenda; en el MVP la base de citas empieza vacía y el archivo JSON solo proporciona el catálogo de médicos. Las citas se conservan al cerrar y reiniciar.

**Fuera de alcance:** reprogramar, crear/editar médicos, editar pacientes, eliminar físicamente citas, autenticación, roles, historial clínico y notificaciones. No aparecen como funciones del MVP de esta entrega.

## Ejecutar

Python 3.10 o superior, sin dependencias externas. Desde la carpeta que contiene `app.py`:

```sh
python app.py
```

En Windows también funciona `INICIAR.bat`. Abre la dirección local indicada (habitualmente `http://127.0.0.1:8000`). **No abras `frontend/mvp.html` con doble clic**: requiere el servidor Python.

## Pruebas

```sh
python -m unittest discover -s tests -v
```

Las pruebas cubren las tres operaciones y casos de error: horario ocupado (total y parcialmente), límites de jornada, fechas inválidas, nombres inválidos y cancelación repetida. En el laboratorio se probarán **tres casos aleatorios dentro de lo que figure en el reporte**, no necesariamente nuestros tres ejemplos.

## API utilizada por el MVP

| Método | Ruta | Operación |
|---|---|---|
| GET | `/api/mvp/doctores` | Cargar catálogo |
| GET | `/api/mvp/disponibilidad?doctor=MED001&fecha=2026-11-09&duracion=30` | Consultar horas libres |
| GET | `/api/mvp/citas` | Consultar tabla de citas |
| POST | `/api/mvp/citas` | Crear cita |
| POST | `/api/mvp/citas/{id}/cancelar` | Cancelar cita |

La interfaz se limita a esos flujos. El cálculo de huecos de `src/gestor_citas.py` se mantiene de la primera entrega.

## Restablecer los datos de práctica

Cerrar el servidor y eliminar solo `data/hospital.sqlite3` para volver a una agenda vacía. Al ejecutar de nuevo se recreará. **No borrar** `data/citas_ficticias.json`.

## Uso exclusivamente académico

Prototipo local sin autenticación ni condiciones para almacenar datos clínicos reales. Utilizar nombres y teléfonos ficticios.

## Documentación del segundo parcial

El reporte actualizado es un PDF de 32 páginas que conserva las 25 páginas originales, incorpora una nota de alcance y seis páginas de esta entrega. Se entrega por separado como PDF. El DOCX original del primer parcial permanece en `docs/Reporte_Etapa_Funcional_Gestor_Citas.docx`.

El diagrama de clases actualizado se encuentra en `docs/diagrama_clases_mvp.dot` y `docs/diagrama_clases_mvp.svg`. La guía para las pruebas de laboratorio está en `docs/guion_laboratorio.md`.

Para mantener reproducible el MVP, el alcance evaluable se limita a consultar disponibilidad, agendar sin empalmes y cancelar citas. Las demás funcionalidades del primer informe son requisitos previstos para etapas posteriores.
