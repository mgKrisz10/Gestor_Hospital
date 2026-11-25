-- Crear previamente una base vacía GestorHospital en Microsoft SQL Server.
-- Script reejecutable; no borra tablas ni información.
IF OBJECT_ID('dbo.doctores','U') IS NULL
BEGIN
 CREATE TABLE dbo.doctores (
  id NVARCHAR(12) PRIMARY KEY, nombre NVARCHAR(120) NOT NULL,
  especialidad NVARCHAR(100) NOT NULL,
  activo BIT NOT NULL CONSTRAINT DF_doctores_activo DEFAULT 1
 );
END
GO
IF OBJECT_ID('dbo.pacientes','U') IS NULL
BEGIN
 CREATE TABLE dbo.pacientes (
  id INT IDENTITY(1,1) PRIMARY KEY, nombre NVARCHAR(120) NOT NULL,
  telefono NVARCHAR(30) NOT NULL, correo NVARCHAR(254) NOT NULL DEFAULT N''
 );
END
GO
IF OBJECT_ID('dbo.especialidades_hospital','U') IS NULL
BEGIN
 CREATE TABLE dbo.especialidades_hospital (nombre NVARCHAR(100) PRIMARY KEY);
END
GO
IF OBJECT_ID('dbo.doctor_especialidades','U') IS NULL
BEGIN
 CREATE TABLE dbo.doctor_especialidades (
  doctor_id NVARCHAR(12) NOT NULL REFERENCES dbo.doctores(id),
  especialidad NVARCHAR(100) NOT NULL,
  CONSTRAINT PK_doctor_especialidades PRIMARY KEY(doctor_id,especialidad)
 );
END
GO
IF OBJECT_ID('dbo.citas','U') IS NULL
BEGIN
 CREATE TABLE dbo.citas (
  id INT IDENTITY(1,1) PRIMARY KEY,
  doctor_id NVARCHAR(12) NOT NULL REFERENCES dbo.doctores(id),
  paciente_id INT NOT NULL REFERENCES dbo.pacientes(id),
  fecha VARCHAR(10) NOT NULL, inicio INT NOT NULL, duracion INT NOT NULL,
  estado NVARCHAR(24) NOT NULL CONSTRAINT DF_citas_estado DEFAULT N'programada',
  cancelacion_motivo NVARCHAR(250) NOT NULL DEFAULT N'',
  especialidad NVARCHAR(100) NOT NULL DEFAULT N'',
  CONSTRAINT CK_citas_estado CHECK (estado IN (N'programada',N'cancelada',N'pendiente_reagendar'))
 );
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_citas_agenda' AND object_id=OBJECT_ID('dbo.citas'))
 CREATE INDEX idx_citas_agenda ON dbo.citas(doctor_id,fecha,estado,inicio);
GO
IF OBJECT_ID('dbo.usuarios','U') IS NULL
BEGIN
 CREATE TABLE dbo.usuarios (
  id INT IDENTITY(1,1) PRIMARY KEY,
  usuario NVARCHAR(40) NOT NULL UNIQUE,
  nombre NVARCHAR(100) NOT NULL,
  rol NVARCHAR(20) NOT NULL CHECK(rol IN (N'administrador',N'doctor',N'paciente',N'recepcion')),
  salt VARBINARY(128) NOT NULL,
  password_hash VARBINARY(128) NOT NULL,
  doctor_id NVARCHAR(12) NULL REFERENCES dbo.doctores(id),
  paciente_id INT NULL REFERENCES dbo.pacientes(id),
  activo BIT NOT NULL DEFAULT 1 CHECK(activo IN (0,1))
 );
END
GO
IF OBJECT_ID('dbo.ausencias','U') IS NULL
BEGIN
 CREATE TABLE dbo.ausencias (
  id INT IDENTITY(1,1) PRIMARY KEY,
  doctor_id NVARCHAR(12) NOT NULL REFERENCES dbo.doctores(id),
  fecha VARCHAR(10) NOT NULL, motivo NVARCHAR(250) NOT NULL,
  creado_en VARCHAR(19) NOT NULL DEFAULT CONVERT(VARCHAR(19), GETUTCDATE(), 120),
  CONSTRAINT UQ_ausencias_doctor_fecha UNIQUE(doctor_id,fecha)
 );
END
GO
IF OBJECT_ID('dbo.notificaciones','U') IS NULL
BEGIN
 CREATE TABLE dbo.notificaciones (
  id INT IDENTITY(1,1) PRIMARY KEY,
  paciente_id INT NOT NULL REFERENCES dbo.pacientes(id),
  cita_id INT NOT NULL REFERENCES dbo.citas(id),
  tipo NVARCHAR(40) NOT NULL, mensaje NVARCHAR(MAX) NOT NULL,
  creado_en VARCHAR(19) NOT NULL DEFAULT CONVERT(VARCHAR(19), GETUTCDATE(), 120),
  leida BIT NOT NULL DEFAULT 0
 );
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_notificaciones_paciente' AND object_id=OBJECT_ID('dbo.notificaciones'))
 CREATE INDEX idx_notificaciones_paciente ON dbo.notificaciones(paciente_id,creado_en);
GO
IF OBJECT_ID('dbo.suspensiones_doctor','U') IS NULL
BEGIN
 CREATE TABLE dbo.suspensiones_doctor (
  doctor_id NVARCHAR(12) NOT NULL REFERENCES dbo.doctores(id),
  usuario_id INT NOT NULL,
  CONSTRAINT PK_suspensiones_doctor PRIMARY KEY(doctor_id,usuario_id)
 );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_citas_paciente' AND object_id=OBJECT_ID('dbo.citas'))
 CREATE INDEX idx_citas_paciente ON dbo.citas(paciente_id,fecha,estado,inicio);
GO
