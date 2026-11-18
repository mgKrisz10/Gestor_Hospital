# Pruebas del Gestor de citas médicas

Iniciar con `python app.py`. Las cuentas de inicio son `admin`, `doctora`, `doctor_carlos`, `doctora_sofia`, `paciente` y `recepcion`, todas con la contraseña `Demo2026!`.

1. **Registrar paciente (R01).** Entrar como recepción, abrir **Pacientes**, registrar un nombre nuevo y buscarlo en la tabla.
2. **Registrar médico (R02).** Entrar como administrador y agregar un médico con ID `MED009`. Intentar repetir el ID para comprobar el error.
3. **Inicio de sesión (R03).** Probar los cuatro perfiles y una contraseña incorrecta. Comprobar que aparecen funciones distintas según el rol.
4. **Consultar horarios (R04).** Elegir médico, fecha y duración y buscar espacios libres.
5. **Agendar (R05).** Con recepción, elegir una hora libre y guardar la cita. Comprobar su aparición en la agenda.
6. **Empalmes (R06).** Intentar guardar otra cita en el mismo médico, fecha y horario. El sistema debe rechazarla.
7. **Cancelar (R07).** Cancelar una cita de la agenda. Buscar disponibilidad otra vez: el intervalo debe estar libre.
8. **Reprogramar (R08).** Crear una cita, usar **Reprogramar**, cambiar la fecha y la hora. Verificar que se actualiza sin duplicarla. Intentar moverla a un horario ocupado.
9. **Próximas citas (R09).** Vincular una cita a la cuenta `paciente`, entrar como paciente y comprobar que el calendario muestra la hora y el médico de sus citas programadas.
10. **Agenda del médico (R10).** Entrar con `doctora`, `doctor_carlos` y `doctora_sofia`. Cada cuenta solo podrá consultar la agenda de MED001, MED002 y MED003 respectivamente.
11. **Usuarios (R11).** Como admin, crear una cuenta nueva, editar su nombre y eliminarla. Comprobar que el usuario eliminado ya no inicia sesión.
12. **Confirmaciones (R12).** Vincular una cita a la cuenta `paciente`. Verificar el comprobante de confirmación al agendar. El paciente ve sus citas en el calendario. Si no hay SMTP, no se envía correo.
13. **Privacidad (R13).** Comprobar que `recepcion` no abre los datos de administración y que `paciente` no ve citas ajenas y que `doctora` no consulta agendas de otros médicos.
14. **Vista de los doctores.** Comprobar que las cuentas médicas solo muestran el listado de citas del consultorio, sin controles de disponibilidad ni ausencias.

Para ejecutar las pruebas automatizadas:

```bash
python -m unittest discover -s tests -v
```

El archivo `data/hospital.sqlite3` conserva todos los cambios. Si se desea reiniciar, cerrar el servidor y borrar ese archivo.

## Pruebas adicionales de la revisión

- **Intentar agendar con médico ocupado:** como recepción, reservar el 09:00–09:30 de una fecha futura y repetir con otro paciente. La segunda solicitud devuelve un error y la agenda conserva una cita programada.
- **Liberar el espacio y volver a agendar:** cancelar la primera cita, consultar de nuevo y confirmar otra en el mismo intervalo. La cita anterior queda cancelada y el horario se reutiliza únicamente si el médico está disponible.
- **Cita el día anterior:** intentar consultar y registrar el día de ayer. Debe aparecer la ventana **Fecha anterior**. Aunque se envíe la solicitud directamente, la API rechaza registrar o reprogramar la cita.
- **Dar de baja a un médico:** crear una cita futura, entrar como administrador, ir a **Administrar médicos** y elegir **Dar de baja**. La ventana muestra cuántas citas futuras quedarán **Pendientes de reagendar**. Tras la baja, entrar como recepción o administración, buscar la cita en la agenda y usar **Reagendar** para pasarla a otro médico, conservando folio y paciente. La cuenta del doctor dado de baja queda desactivada; al reactivarlo, las citas pendientes no se reactivan solas.

Pruebas automatizadas específicas: `python -m unittest tests.test_pruebas_maestra -v`.

## Cambios de agenda y catálogo

- **Agenda de doctora:** iniciar sesión con `doctora` y contraseña `Demo2026!`, abrir **Mi agenda**. Deben verse solo las citas del médico MED001; comprobar que una cita de MED002 no aparece. Esta cuenta se desactiva cuando MED001 recibe baja administrativa.
- **Pendiente de reagendar:** como recepción, registrar una cita futura con MED001. Después, como administrador, dar de baja a MED001. Al revisar las citas como recepción o administración, la cita debe mostrar el estado **Pendiente de reagendar** (no cancelada). Pulsar **Reagendar**, elegir MED002 y un horario disponible. La cita vuelve a `programada` y conserva su folio.
- **Directorio:** iniciar sesión como recepción o administración. Se muestran nombres, especialidades, estado y cantidades de citas; no se muestran datos personales de pacientes en el directorio.
- **Tabla de médicos:** abrir **Directorio de médicos** como recepción o administrador. Los médicos dados de baja deben aparecer como inactivos, con el número de citas pendientes de reagendar.

El cambio de estado se migra automáticamente al iniciar el servidor con una base de datos anterior; no hace falta borrar `hospital.sqlite3`. Antes de actualizar, conviene respaldar ese archivo.

## Calendario del paciente

Iniciar sesión como `paciente`. Comprobar que aparece únicamente el calendario de sus citas: navegar entre meses, seleccionar el día con una cita, verificar horario y nombre del médico. Las citas de otros pacientes y las canceladas no deben mostrarse como consultas programadas.

## Identificación y empalmes entre médicos (18 de noviembre)

- Selecciona **Doctor** en la pantalla inicial y entra con ID `MED001` y contraseña `Demo2026!`. Repite con `MED002`. Debes ver una sola agenda vinculada a cada identificador.
- Registra un paciente en Recepción y anota su clave `PAC-...`. También puedes usar la cuenta `paciente` y ver la clave que aparece en el calendario.
- Reserva una cita para ese paciente con `MED001` de 09:00 a 10:00, en una fecha futura. Intenta reservar con `MED002` de 09:30 a 10:00 usando **la misma clave de paciente**. Debe aparecer un error por horario del paciente.
- Haz otra reserva de 10:00 a 10:30: es válida. Intenta reprogramarla a las 09:45: debe rechazarse y conservar el horario anterior.
- Verifica que el acceso retirado ya no aparece y que `consulta` no puede iniciar sesión.
- Da de baja al médico con una cita futura. En el calendario del paciente debe aparecer **Pendiente de reagendar**. El folio y la clave de paciente se conservan.
- También se prueba eliminar la última cuenta médica desde Administrador: debe dar de baja al médico y dejar pendientes sus citas futuras.

Las claves de paciente se derivan de la identidad interna, no son contraseñas. Para entrar como paciente se requiere también la contraseña correcta.
