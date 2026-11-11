# MedAgenda

Gestor de citas médicas para la materia de Paradigmas de Programación.

El sistema permite consultar horarios, registrar y cancelar citas, revisar agendas y agregar médicos. Se hizo en Python, HTML, CSS, JavaScript y SQLite.

## Iniciar

Se necesita Python 3.10 o superior.

1. Abre la carpeta en Visual Studio Code.
2. Ejecuta `python app.py`. En Windows también sirve `INICIAR.bat`.
3. Abre la dirección que aparece en la terminal, normalmente `http://127.0.0.1:8000`.

La página necesita que el servidor esté encendido. No abras `frontend/mvp.html` directamente.

## Usuarios

Para las pruebas se incluyeron estas cuentas. Todas usan la contraseña `Demo2026!`.

| Usuario | Rol | Puede hacer |
|---|---|---|
| `admin` | Administrador | Consultar y cancelar citas, registrar citas, ver usuarios y agregar médicos. |
| `doctora` | Doctor | Consultar las citas del médico MED001. |
| `paciente` | Paciente | Ver sus citas y consultar horarios. |
| `recepcion` | Recepción | Consultar horarios y registrar o cancelar citas. |
| `consulta` | Personal autorizado | Consultar médicos y horarios. |

Los permisos se revisan en el servidor. Cada cuenta ve únicamente lo que le corresponde.

## Registrar una cita

1. Entra con `recepcion` o `admin`.
2. Elige médico, fecha y duración y busca un horario.
3. Selecciona uno de los horarios libres.
4. Escribe el nombre del paciente y confirma la cita.

Para que aparezca en la cuenta `paciente`, marca **Asociar a la cuenta «paciente»** antes de confirmarla.

Las citas no pueden empalmarse para un mismo médico y fecha. Si cancelas una cita, el horario vuelve a quedar disponible.

## Archivos principales

- `src/gestor_citas.py`: cálculo de horarios libres.
- `src/mvp.py`: médicos, pacientes, citas y SQLite.
- `src/autenticacion.py`: usuarios, contraseñas y sesiones.
- `src/servidor.py`: solicitudes HTTP y permisos.
- `frontend/mvp.html`, `mvp.css`, `mvp.js`: interfaz.
- `tests/`: pruebas automatizadas.
- `docs/`: reporte y diagrama de clases.

Los datos se guardan en `data/hospital.sqlite3`. Para empezar con una base nueva, cierra el servidor, elimina ese archivo y vuelve a ejecutar `python app.py`.

## Pruebas

Ejecuta:

```bash
python -m unittest discover -s tests -v
```

También puedes seguir los casos del archivo `docs/guion_laboratorio.md`.

## Funciones que faltan

Todavía no se pueden reprogramar citas, editar o eliminar usuarios, enviar notificaciones ni gestionar expedientes médicos.

El proyecto usa cuentas y datos de prueba; no debe utilizarse con información real de pacientes.
