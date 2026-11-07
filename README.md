# MedAgenda — Gestor de Citas Médicas (segundo parcial)

Proyecto de **Paradigmas de Programación**, ESCOM-IPN, grupo 3CV4. Este repositorio **continúa el primer parcial**, conserva su cálculo funcional de disponibilidad (`src/gestor_citas.py`) y añade un MVP local con inicio de sesión, cinco perfiles de demostración, persistencia SQLite y control de accesos en el servidor.

**Fecha de entrega:** 11 de noviembre de 2026 a las 16:30.

## Ejecutar el MVP

Se requiere **Python 3.10 o superior**. No usa Flask, Django ni bibliotecas de terceros.

```bash
python app.py
```

En Windows también puedes ejecutar `INICIAR.bat`. Abre la URL indicada por el servidor, generalmente `http://127.0.0.1:8000`.

**Importante:** no abras `frontend/mvp.html` directamente. La pantalla de acceso necesita el servidor Python y la base de datos. Las rutas del primer parcial (`/index.html`, `/api/doctores`, `/api/disponibilidad`) siguen disponibles para demostraciones históricas con datos ficticios.

## Usuarios para la demostración

**Contraseña común:** `Demo2026!` (solo datos ficticios; no usar para pacientes reales).

| Usuario | Rol | Acciones permitidas |
|---|---|---|
| `admin` | Administrador | Ver agenda, registrar/cancelar citas, consultar usuarios/resumen y dar de alta médicos. |
| `doctora` | Doctor | Consultar solamente su agenda (MED001) y su disponibilidad. |
| `paciente` | Paciente | Ver sus citas vinculadas y consultar horarios sin registrar/cancelar. |
| `recepcion` | Recepción | Consultar horarios, registrar pacientes ficticios y reservar/cancelar citas. |
| `consulta` | Personal autorizado | Consultar médicos y espacios libres; no ve datos personales ni cambia citas. |

El PDF original enumera cinco tipos de actores. **“Personal autorizado” es una categoría general** en el análisis inicial; aquí se representa mediante un perfil de consulta limitada. **Los permisos se validan en Python, no solamente ocultando botones.**

## Demostración de los perfiles

1. Selecciona **Recepción** e inicia sesión; consulta disponibilidad para una fecha ficticia.
2. Selecciona un horario libre. Marca **“Vincular cita con la cuenta paciente de demostración”** y confírmala. Así el usuario `paciente` podrá verla después.
3. Cierra sesión y entra como **Paciente**: verifica que solo aparece la cita vinculada.
4. Entra como **Doctor**: solo verá la agenda del MED001; no podrá cancelar ninguna cita.
5. Entra como **Personal autorizado**: podrá consultar horarios, pero no verá la tabla de citas.
6. Entra como **Administrador**: revisa usuarios, resumen y registra un nuevo médico con identificador `MED004`.
7. Desde **Recepción** o **Administrador**, cancela una cita; comprobarás que vuelve a aparecer su horario libre.

## Reglas de negocio del MVP

- Jornada de 08:00 a 14:00; citas de 15, 30, 45 o 60 minutos desde la interfaz.
- Verificación de intervalos ocupados por **médico y fecha**, incluyendo empalmes parciales.
- Citas almacenadas en `data/hospital.sqlite3`, con operaciones atómicas de inserción/cancelación.
- Las citas canceladas se conservan como historial y liberan su franja.
- Las cuentas de prueba se crean en el primer arranque y mantienen contraseñas derivadas con PBKDF2-HMAC-SHA256 y sal individual.
- Los tokens de sesión son aleatorios y viven solo en RAM durante dos horas o hasta cerrar sesión; hay que iniciar sesión de nuevo si reinicias Python.
- El doctor ve **solo** citas del MED001. El paciente ve **solo** las citas vinculadas a su cuenta.

## Pruebas automatizadas

```bash
python -m unittest discover -s tests -v
```

**53 pruebas aprobadas en la revisión local**, que cubren la funcionalidad del primer parcial, persistencia, concurrencia, autenticación, acceso prohibido, privacidad por rol y API HTTP. Para los tres casos aleatorios de laboratorio, utiliza también `docs/guion_laboratorio.md`.

La **prueba visual integral en navegador no pudo finalizarse en el entorno de creación** y debe verificarse en la PC de laboratorio. Las pruebas de red del backend sí se ejecutaron con HTTP real contra un servidor local.

## Documentos

- `docs/Reporte_Gestor_Citas_Actualizado_Segundo_Parcial.pdf`: **32 páginas**, contiene el reporte inicial de 25 páginas sin eliminar su contenido, nota sobre alcance y seis páginas de la implementación ampliada.
- `docs/Continuacion_Segundo_Parcial_Editable.docx`: continuación editable con diseño, roles, UML, código, permisos, pruebas y limitaciones.
- `docs/diagrama_clases_mvp.png` / `.svg` / `.dot`: diagrama de clases actualizado con Usuario y AutenticacionService.

## Alcance declarado y limitaciones

El reporte del primer parcial incluyó requerimientos **previstos**, pero **no todos están implementados**. El MVP **no incluye** reprogramar citas, editar/desactivar cuentas de usuarios, notificar ausencias, enviar correos, historiales clínicos, despliegue externo ni seguridad clínica de producción. El administrador puede ver usuarios y registrar médicos; aún no puede editar ni eliminar cuentas. No deben ingresarse datos médicos reales.

## Reiniciar solo los datos del laboratorio

1. Detén el servidor.
2. Borra únicamente el archivo `data/hospital.sqlite3`.
3. Ejecuta `python app.py` otra vez para crear una nueva base de prueba con los tres médicos iniciales y cinco cuentas demo.

Los archivos fuente y el PDF no se borran al reiniciar la base local.
