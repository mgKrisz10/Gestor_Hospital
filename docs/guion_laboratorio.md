# Preparación para tres pruebas aleatorias del MVP

**Lo evaluable es lo expresamente declarado en el informe:** consulta de horarios, registro de cita y cancelación. La profesora puede variar el médico, la fecha, la duración, el nombre y las condiciones iniciales.

## Prueba de disponibilidad

1. Iniciar `python app.py`.
2. Elegir MED001 y una fecha sin reservas (p. ej. 2026-11-09). Duración 30 minutos.
3. Buscar. Inicialmente deben aparecer 12 bloques en la jornada de 08:00-14:00.
4. Cambiar a 60 minutos: inicialmente 6 bloques. No hace falta que la prueba use exactamente esa fecha.

## Prueba de alta / empalmes

1. Volver a 30 minutos, seleccionar 08:00 y escribir `Paciente de Prueba`.
2. Confirmar: aparece un ID y la cita se agrega a la tabla.
3. Buscar de nuevo: 08:00 deja de estar disponible.
4. La repetición exacta o parcial para el mismo doctor y fecha debe ser rechazada por el servidor. La pantalla oculta los horarios ocupados; puede verificarse el rechazo con `python -m unittest tests.test_mvp -v` o mediante la API.

## Prueba de cancelación

1. En la tabla, cancelar la cita de la prueba anterior y confirmar la ventana de diálogo.
2. Verificar que su estado pasa a `cancelada`.
3. Buscar disponibilidad: 08:00 vuelve a estar disponible. Actualizar la página no revierte la cancelación.

## Variantes que también deben superar las pruebas

- Dos médicos en la misma fecha y hora pueden agendar por separado.
- Fechas diferentes pueden compartir la misma hora.
- No se permiten reservas fuera de 08:00-14:00 o con duración no positiva.
- Nombre vacío o fecha imposible produce mensaje de error.
- No se debe crear dos veces una cita exactamente igual para el mismo doctor, fecha y hora.
- Cancelar por segunda vez no altera el estado ni crea nuevas citas.

## Preparar una prueba limpia

Cierra el servidor y borra `data/hospital.sqlite3`; vuelve a iniciarlo. El catálogo de médicos se recrea y la agenda empieza sin citas. Esta acción es solo para **datos ficticios de prueba**.
