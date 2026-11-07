# Ensayo para tres pruebas aleatorias — segundo parcial

La profesora puede elegir cualquier función **incluida como implementada en el reporte**, no solo tres escenarios preparados. Estos casos cubren las variantes que conviene ensayar.

## Entrar con los cinco perfiles

Ejecuta `python app.py`. En la pantalla de inicio, selecciona `admin`, `doctora`, `paciente`, `recepcion` o `consulta`, todos con clave `Demo2026!`. La contraseña errónea debe rechazarse. Cierra sesión antes de cambiar de rol.

## Recepción — consulta / agenda / cancelación

Entra como `recepcion`, busca un médico y una fecha sin citas. Prueba duración 30 min (12 espacios en jornada vacía). Selecciona uno, registra un paciente ficticio y comprueba que el horario queda ocupado. Un segundo registro total/parcialmente empalmado debe rechazarse. Cancela el primero y confirma que el intervalo vuelve a estar libre. Prueba fechas distintas y médicos distintos para verificar independencia de agendas.

## Doctor — agenda propia

Entra como `doctora`, vinculada a MED001. Consulta su agenda; no debe ver las citas de MED002 ni poder modificarlas. La API rechaza consultar disponibilidad de MED002 desde este usuario (403).

## Paciente — privacidad

Para preparar citas visibles al usuario `paciente`, desde `recepcion` marca la casilla **Vincular cita con la cuenta paciente de demostración** antes de confirmar. Inicia después como `paciente`. Solo aparece su registro, nunca citas creadas para otros pacientes. Puede buscar horarios pero no registrar/cancelar.

## Administrador — registro de médicos

Entra como `admin`; comprueba el panel de resumen, las cinco cuentas y el catálogo. Agrega `MED004`, nombre `Dr. Marco de Prueba`, especialidad `Medicina Interna`. Aparece en la lista de médicos. Un segundo alta con el mismo ID debe rechazarse. También puede registrar y cancelar citas.

## Personal autorizado — lectura limitada

Entra como `consulta`; consulta médicos y horarios libres. No hay tabla de citas ni botones de modificación. Las rutas que contienen datos personales o modificaciones deben devolver 403.

## Ejecutar pruebas automáticas

`python -m unittest discover -s tests -v`

**53 pruebas automatizadas** (la prueba visual completa debe repetirse en la PC de laboratorio). No se ofrecen como implementados: reprogramación, edición/eliminación de cuentas, notificaciones, ausencias del doctor ni expediente médico.

## Datos de prueba

El archivo `data/hospital.sqlite3` almacena lo realizado. Si deseas una demo nueva, cierra Python y elimina solamente ese archivo, que se reconstruye al arrancar. Nunca uses información clínica real.
