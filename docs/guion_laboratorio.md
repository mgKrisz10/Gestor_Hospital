# Pruebas del Gestor de citas médicas

Iniciar con `python app.py`. Las cuentas de inicio son `admin`, `doctora`, `paciente`, `recepcion` y `consulta`, todas con la contraseña `Demo2026!`.

1. **Registrar paciente (R01).** Entrar como recepción, abrir **Pacientes**, registrar un nombre nuevo y buscarlo en la tabla.
2. **Registrar médico (R02).** Entrar como administrador y agregar un médico con ID `MED009`. Intentar repetir el ID para comprobar el error.
3. **Inicio de sesión (R03).** Probar las cinco cuentas y una contraseña incorrecta. Comprobar que aparecen funciones distintas según el rol.
4. **Consultar horarios (R04).** Elegir médico, fecha y duración y buscar espacios libres.
5. **Agendar (R05).** Con recepción, elegir una hora libre y guardar la cita. Comprobar su aparición en la agenda.
6. **Empalmes (R06).** Intentar guardar otra cita en el mismo médico, fecha y horario. El sistema debe rechazarla.
7. **Cancelar (R07).** Cancelar una cita de la agenda. Buscar disponibilidad otra vez: el intervalo debe estar libre.
8. **Reprogramar (R08).** Crear una cita, usar **Reprogramar**, cambiar la fecha y la hora. Verificar que se actualiza sin duplicarla. Intentar moverla a un horario ocupado.
9. **Próximas citas (R09).** Vincular una cita a la cuenta `paciente`, entrar como paciente y comprobar que solo aparecen las futuras y propias.
10. **Agenda del médico (R10).** Entrar como `doctora`. Solo podrá consultar la agenda de MED001.
11. **Usuarios (R11).** Como admin, crear una cuenta nueva, editar su nombre y eliminarla. Comprobar que el usuario eliminado ya no inicia sesión.
12. **Confirmaciones (R12).** Vincular una cita a la cuenta `paciente`. Entrar como paciente y revisar **Notificaciones**. En ausencia de SMTP, el aviso se entrega dentro del sistema, no por correo.
13. **Privacidad (R13).** Comprobar que `consulta` no abre la lista de citas, que `paciente` no ve citas ajenas y que `doctora` no consulta agendas de otros médicos.
14. **Ausencia médica (R14).** Como doctora, escoger una fecha que tenga citas del médico MED001 y registrar ausencia y motivo. Se cancelan las citas de ese día y se bloquean los espacios. Probar otra fecha para comprobar que conserva disponibilidad.

Para ejecutar las pruebas automatizadas:

```bash
python -m unittest discover -s tests -v
```

El archivo `data/hospital.sqlite3` conserva todos los cambios. Si se desea reiniciar, cerrar el servidor y borrar ese archivo.

## Pruebas adicionales de la revisión

- **Intentar agendar con médico ocupado:** como recepción, reservar el 09:00–09:30 de una fecha futura y repetir con otro paciente. La segunda solicitud devuelve un error y la agenda conserva una cita programada.
- **Liberar el espacio y volver a agendar:** cancelar la primera cita, consultar de nuevo y confirmar otra en el mismo intervalo. Si el día está bloqueado por ausencia, usar **Liberar fecha** (solo doctor o administrador). Las citas antes canceladas no vuelven a activarse.
- **Cita el día anterior:** intentar consultar y registrar el día de ayer. Debe aparecer la ventana **Fecha anterior**. Aunque se envíe la solicitud directamente, la API rechaza registrar o reprogramar la cita.
- **Dar de baja a un médico:** crear una cita futura, entrar como administrador, ir a **Administrar médicos** y elegir **Dar de baja**. La ventana muestra cuántas citas futuras quedarán **Pendientes de reagendar**. Tras la baja, entrar como recepción o administración, buscar la cita en la agenda y usar **Reagendar** para pasarla a otro médico, conservando folio y paciente. La cuenta del doctor dado de baja queda desactivada; al reactivarlo, las citas pendientes no se reactivan solas.

Pruebas automatizadas específicas: `python -m unittest tests.test_pruebas_maestra -v`.

## Cambios de agenda, catálogo y personal autorizado

- **Agenda de doctora:** iniciar sesión con `doctora` y contraseña `Demo2026!`, abrir **Mi agenda**. Deben verse solo las citas del médico MED001; comprobar que una cita de MED002 no aparece. Esta cuenta se desactiva cuando MED001 recibe baja administrativa.
- **Pendiente de reagendar:** como recepción, registrar una cita futura con MED001. Después, como administrador, dar de baja a MED001. Al revisar las citas como recepción o administración, la cita debe mostrar el estado **Pendiente de reagendar** (no cancelada). Pulsar **Reagendar**, elegir MED002 y un horario disponible. La cita vuelve a `programada` y conserva su folio.
- **Directorio:** iniciar sesión con `consulta` (personal autorizado). El panel permite consultar el directorio de médicos, especialidades, estado y cantidades de citas; también se pueden consultar horarios. No puede ver pacientes, agendas nominales, teléfonos ni registrar o cancelar citas.
- **Tabla de médicos:** abrir **Directorio de médicos** como personal autorizado, recepción o administrador. Los médicos dados de baja deben aparecer como inactivos, con el número de citas pendientes de reagendar.

El cambio de estado se migra automáticamente al iniciar el servidor con una base de datos anterior; no hace falta borrar `hospital.sqlite3`. Antes de actualizar, conviene respaldar ese archivo.
