# Configuración de SQL Server externo

La aplicación del laboratorio actualmente guarda los datos en SQLite. Para migrarla a una instancia externa de Microsoft SQL Server:

1. Instala **SQL Server 2019+** (o usa una instancia existente) y crea una base vacía llamada `GestorHospital` en SQL Server Management Studio (SSMS): `CREATE DATABASE GestorHospital;`.
2. Instala **Microsoft ODBC Driver 18 for SQL Server** en Windows y ejecuta `python -m pip install -r requirements-sqlserver.txt`.
3. Establece las variables de entorno en la terminal **sin escribir contraseñas en GitHub**. Por ejemplo, usando autenticación de Windows en PowerShell:

   ```powershell
   $env:HOSPITAL_DB_BACKEND = "sqlserver"
   $env:HOSPITAL_SQLSERVER_CONNECTION_STRING = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=tcp:NOMBRE_SERVIDOR,1433;DATABASE=GestorHospital;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=no;"
   ```

   Para usuarios SQL Server usa `UID=...;PWD=...;` en lugar de `Trusted_Connection=yes;`. El servidor debe presentar un certificado TLS confiable. No utilices `TrustServerCertificate=yes` en producción.

4. **Respalda** `data/hospital.sqlite3`. Si existe la base anterior, ejecuta desde la raíz del proyecto:

   ```powershell
   python -m sqlserver.migrar_desde_sqlite --origen data/hospital.sqlite3
   python -m sqlserver.migrar_desde_sqlite --origen data/hospital.sqlite3 --verificar
   ```

   El proceso se niega a sobrescribir una base destino con datos, conserva el identificador de citas, pacientes y cuentas, y compara todo el contenido migrado (no solo los conteos).

5. Con esas variables de entorno, inicia `python app.py` y prueba de forma real los cuatro roles, altas, bajas, especialidades, citas, conflictos, reagendar, y notificaciones **en la instancia de SQL Server**. También ejecuta las pruebas funcionales en una base de prueba; no las ejecutes sobre una base que contenga datos reales.
6. **Solo después** de verificar una ejecución real de todas las funciones y conservar un respaldo externo, puedes desactivar SQLite para producción (`HOSPITAL_DB_BACKEND=sqlserver`). El archivo SQLite **no se elimina automáticamente**: la aplicación no borra bases de datos sin demostrar que el servidor externo funciona.

Si el servidor SQL no responde, la aplicación devuelve un error. No activa silenciosamente SQLite ni crea una base secundaria, para evitar divergencia de citas.

### Notas

- El catálogo institucional está en `src/especialidades.py` y su copia en SQL Server se guarda en `especialidades_hospital`.
- Un médico tiene una o varias especialidades en `doctor_especialidades`, y cada cita conserva la especialidad solicitada.
- El acceso SQLite se mantiene provisionalmente para poder migrar y ejecutar pruebas sin SQL Server.
- `schema.sql` contiene las tablas `doctores`, `pacientes`, `especialidades_hospital`, `doctor_especialidades`, `citas`, `usuarios`, `ausencias`, `notificaciones` y `suspensiones_doctor`.
- Sin una instancia y credenciales disponibles **no es posible afirmar que el entorno SQL Server ya esté conectado o migrado**.
