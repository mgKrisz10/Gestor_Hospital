# Pruebas del hospital

Inicia el programa con `python app.py`. Los usuarios son `admin`, `doctora`, `paciente`, `recepcion` y `consulta`. La contraseña es `Demo2026!`.

## Iniciar sesión
Prueba las cinco cuentas. Una contraseña incorrecta debe impedir el acceso. Cierra sesión antes de cambiar de usuario.

## Recepción
Entra como `recepcion` y consulta horarios de un médico en una fecha nueva. Registra una cita de 30 minutos. El horario debe desaparecer de los disponibles. Intenta registrar otra cita en el mismo horario: no debe permitirlo. Cancela la cita y vuelve a buscar el horario.

## Doctor
Entra como `doctora` y consulta la agenda del médico MED001. No debe poder consultar la agenda de otro médico ni cancelar citas.

## Paciente
Entra como `recepcion` y registra una cita marcando **Asociar a la cuenta «paciente»**. Cierra sesión y entra como `paciente`. Debe aparecer esa cita, pero no las de otras personas.

## Administrador
Entra como `admin`. Revisa la agenda y el resumen. Da de alta un médico con ID `MED004`, nombre y especialidad. Intenta repetir el mismo ID: debe mostrar un error.

## Personal autorizado
Entra como `consulta`. Puede buscar horarios, pero no tiene acceso a citas ni a operaciones de registro o cancelación.

## Ejecutar pruebas
`python -m unittest discover -s tests -v`

El archivo `data/hospital.sqlite3` guarda las citas. Para reiniciar los datos, cierra el servidor, elimina ese archivo y vuelve a abrir el programa.
