# MedAgenda - Gestor de citas médicas

Proyecto de Paradigmas de Programación, ESCOM, grupo 3CV4.

El sistema se ejecuta localmente con Python 3.10 o superior. Usa SQLite para conservar la información, HTML/CSS/JavaScript para la interfaz y Python para calcular la disponibilidad y validar los permisos.

## Ejecutar

1. Abrir la carpeta del repositorio en Visual Studio Code.
2. Ejecutar `python app.py` (en Windows también funciona `INICIAR.bat`).
3. Abrir la dirección de la terminal, normalmente `http://127.0.0.1:8000`.

No es necesario instalar Flask ni paquetes adicionales. **No abrir `frontend/mvp.html` directamente**: las operaciones necesitan el servidor Python.

## Cuentas iniciales

| Usuario | Rol | Contraseña |
|---|---|---|
| `admin` | Administrador | `Demo2026!` |
| `doctora` | Doctor (MED001) | `Demo2026!` |
| `doctor_carlos` | Doctor (MED002) | `Demo2026!` |
| `doctora_sofia` | Doctor (MED003) | `Demo2026!` |
| `paciente` | Paciente registrado | `Demo2026!` |
| `recepcion` | Recepción | `Demo2026!` |
| `consulta` | Personal autorizado | `Demo2026!` |

El administrador puede crear, editar y eliminar más cuentas, asociando las cuentas de doctor y paciente al registro correspondiente. No es posible eliminar la cuenta propia del administrador o dejar el sistema sin administradores.

## Funciones

- **Pacientes:** recepción y administración pueden registrar pacientes por separado, con nombre, teléfono y correo opcional.
- **Médicos:** administración da de alta médicos, consulta su situación, los da de baja o los reactiva. La baja no elimina el historial: deja las citas futuras pendientes de reagendar y desactiva temporalmente sus cuentas vinculadas.
- **Sesiones:** usuarios y contraseñas, cierre de sesión y permisos por rol.
- **Disponibilidad:** consulta por médico, fecha y duración (08:00 a 14:00).
- **Citas:** registro, cancelación y reprogramación sin superponer horarios. No se permite reservar o reprogramar en una fecha anterior al día actual (hora de Ciudad de México).
- **Agendas:** recepción y administración consultan la agenda; cada doctor solo ve su consultorio y cada paciente sus propias citas. La opción de próximas citas muestra solo las citas futuras y programadas.
- **Confirmaciones:** al registrar o reprogramar, se guarda el aviso y se devuelve un comprobante con los datos de la cita. La pantalla de paciente está dedicada al calendario de citas.
- **Usuarios:** la administración puede crear, actualizar o eliminar cuentas. Las contraseñas se almacenan con PBKDF2-HMAC-SHA256 y sal, no como texto.

## Pruebas indicadas por la profesora

1. **Médico ocupado:** reservar un horario, intentar crear otra cita a la misma hora y comprobar que se rechaza.
2. **Liberar el horario:** cancelar la primera cita, consultar espacios y reservar el mismo horario.
3. **Fecha anterior:** seleccionar el día de ayer e intentar registrar una cita. La interfaz lo advierte y el servidor la rechaza aunque la petición se envíe directamente.
4. **Baja del médico:** como administrador, abrir «Administrar médicos» y pulsar «Dar de baja». La ventana indica cuántas citas futuras quedarán pendientes de reagendar. Tras confirmar, el médico sale del catálogo activo, sus citas anteriores permanecen en el historial y su cuenta asociada no puede iniciar sesión. Se puede reactivar; las citas pendientes deben reasignarse por separado.

Las operaciones se prueban también con `python -m unittest discover -s tests -v`.

## Confirmación por correo (opcional)

El envío automático **dentro del sistema** funciona sin configuración adicional. Si se necesita también correo electrónico, se deben definir las variables de entorno:

- `MEDAGENDA_SMTP_HOST`: servidor SMTP.
- `MEDAGENDA_SMTP_PORT`: puerto (465 para SSL o 587 para STARTTLS).
- `MEDAGENDA_SMTP_FROM`: dirección remitente.
- `MEDAGENDA_SMTP_USER` y `MEDAGENDA_SMTP_PASSWORD`: credenciales SMTP, si el proveedor las requiere.

El paciente debe tener un correo registrado. Si SMTP no está configurado, la notificación sigue guardada en el sistema, pero **no se envía un correo externo**. Nunca subir claves ni contraseñas SMTP a GitHub.

## Archivos principales

- `src/gestor_citas.py`: cálculo funcional de disponibilidad.
- `src/mvp.py`: modelos y operaciones básicas de SQLite.
- `src/operaciones_extra.py`: pacientes, confirmaciones y reprogramación; conserva reglas previas de disponibilidad para bases existentes.
- `src/autenticacion.py`: cuentas, contraseñas, sesiones y permisos.
- `src/servidor.py`: rutas HTTP.
- `frontend/mvp.html`, `mvp.css`, `mvp.js`: interfaz principal y calendario del paciente.
- `tests/`: pruebas automatizadas.
- `docs/`: diagrama, reporte e instrucciones de laboratorio.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Los datos se guardan en `data/hospital.sqlite3`. Para empezar desde cero, cerrar Python, borrar ese archivo y ejecutar nuevamente `python app.py`. **Esto borra todas las citas, pacientes y cuentas registradas durante la práctica.**

## Privacidad

Este es un sistema local para la clase: utiliza datos ficticios. Incluye control de acceso en el servidor, sesiones temporales, contraseñas derivadas y restricciones sobre qué agendas puede ver cada cuenta. No está auditado ni preparado para operar un hospital real o almacenar expedientes clínicos, y no tiene despliegue público ni copias de seguridad de producción.

## Subir esta versión al fork

En Windows, abre esta carpeta y ejecuta `SUBIR_GITHUB.bat`. Necesitas Git instalado y haber iniciado sesión en tu cuenta. El script actualiza **solo** la rama `segundo-parcial-mvp-2026` y no modifica `main`. También puedes copiar los archivos manualmente al repositorio y hacer `git add`, `git commit` y `git push`.

## Directorio y citas por reagendar

El perfil `consulta` corresponde al personal de coordinación: puede ver un directorio de médicos (nombre, especialidad, estado y números de citas) y consultar disponibilidad, pero no puede ver información personal de pacientes ni modificar citas.

Cuando administración da de baja a un médico, las citas futuras pasan a **Pendiente de reagendar**, sin perder el historial. Recepción o administración puede pulsar **Reagendar** en la agenda y elegir otro médico y horario libre. El folio y paciente se conservan. La cuenta del médico dado de baja queda inactiva hasta una eventual reactivación.

La primera ejecución con una base antigua actualiza el esquema de `citas` para admitir el nuevo estado sin borrar datos. Se recomienda respaldar `data/hospital.sqlite3` antes de actualizar.

## Pantallas por tipo de cuenta

- **Doctor:** muestra exclusivamente las citas vinculadas al consultorio de su cuenta. No se muestran controles para consultar disponibilidad ni registrar ausencias.
- **Paciente:** abre un calendario mensual con las citas propias, la hora y el médico que atenderá. No puede consultar las citas de otros pacientes.
- **Recepción y administración:** mantienen la búsqueda y la gestión de citas y médicos.
- **Personal autorizado:** conserva su vista de consulta del directorio médico.

Cuentas de médicos de ejemplo: `doctora` (MED001), `doctor_carlos` (MED002), `doctora_sofia` (MED003). Las tres usan `Demo2026!`. Al iniciar el servidor, las dos cuentas nuevas también se incorporan a una base SQLite que ya existiera, sin eliminar datos previos.

## Identificación de médicos y pacientes (actualización)

El acceso de **Doctor** es único en la pantalla inicial. Al seleccionarlo,
se solicita el identificador médico (`MED001`, `MED002`, `MED003`) y la contraseña.
La cuenta se resuelve en el servidor y cada doctor ve solamente su agenda.
Los usuarios médicos anteriores (`doctora`, `doctor_carlos`, `doctora_sofia`)
se conservan para no perder accesos existentes.

Cada paciente tiene una **clave única** en formato `PAC-000001`, derivada de su
identificador primario de SQLite. Esa clave se ve en el calendario y en el
catálogo de pacientes. Puede utilizarse para iniciar sesión con su contraseña,
pero **la clave no sustituye la autenticación**. Las cuentas de pacientes
quedan vinculadas a un registro concreto, independientemente de que haya otras
personas con el mismo nombre.

Al agendar o reprogramar, se revisa el horario del doctor **y el del paciente**.
Dos médicos distintos no pueden atender al mismo paciente al mismo tiempo.
Se comprueban empalmes parciales, no solo horas de inicio idénticas.

El perfil **Personal autorizado** sirve para coordinación: puede consultar
el directorio de médicos y buscar disponibilidad, pero no puede ver pacientes
ni modificar citas o cuentas. Estas restricciones se verifican en Python.

Una baja de médico cambia sus citas futuras a **Pendiente de reagendar**.
El calendario del paciente muestra esas citas con el estado correcto.
Si se elimina la **última cuenta de un doctor**, también se da de baja su
registro y sus futuras citas quedan pendientes; se conservan los folios.
Las instalaciones anteriores se ajustan al iniciar, sin borrar la base de datos.

**Antes de actualizar:** respalda `data/hospital.sqlite3`, cierra el servidor,
actualiza la rama, inicia nuevamente `python app.py` y recarga el navegador
con Ctrl+F5.
