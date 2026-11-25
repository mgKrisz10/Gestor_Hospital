"""Copia verificable de SQLite a una base SQL Server externa.

No modifica ni borra el origen; opera sobre un snapshot para completar migraciones
previas y conservar el archivo original como respaldo.

Ejemplo:
  python -m sqlserver.migrar_desde_sqlite --origen data/hospital.sqlite3
  python -m sqlserver.migrar_desde_sqlite --origen data/hospital.sqlite3 --verificar
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from pathlib import Path

from src.sqlserver_backend import cadena_conexion, preparar_esquema

# Orden garantiza claves foráneas y preserva las identidades de SQLite.
TABLAS = (
    'doctores', 'pacientes', 'especialidades_hospital', 'doctor_especialidades',
    'citas', 'usuarios', 'ausencias', 'notificaciones', 'suspensiones_doctor',
)
IDENTIDAD = {'pacientes', 'citas', 'usuarios', 'ausencias', 'notificaciones'}


def normalizar(value):
    if value is None: return None
    if isinstance(value, (bytearray, memoryview)): return bytes(value)
    if isinstance(value, bool): return int(value)
    return value


def columnas_sqlite(con, tabla):
    return [r['name'] for r in con.execute('PRAGMA table_info('+tabla+')')]


def filas_sqlite(con, tabla, columnas):
    sel=','.join('"'+name+'"' for name in columnas)
    rows=con.execute('SELECT '+sel+' FROM "'+tabla+'"').fetchall()
    return sorted([tuple(normalizar(row[name]) for name in columnas) for row in rows],key=repr)


def filas_servidor(con, tabla, columnas):
    sel=','.join('['+name+']' for name in columnas)
    rows=con.execute('SELECT '+sel+' FROM dbo.['+tabla+']').fetchall()
    return sorted([tuple(normalizar(x) for x in row) for row in rows],key=repr)


def inspeccionar(origen, conectado):
    """Verifica contenido completo, no solo cantidades por tabla."""
    with sqlite3.connect(origen) as sql:
        sql.row_factory=sqlite3.Row
        resumen={}
        for tabla in TABLAS:
            columnas=columnas_sqlite(sql, tabla)
            fuente=filas_sqlite(sql, tabla, columnas)
            destino=filas_servidor(conectado, tabla, columnas)
            if fuente != destino:
                raise RuntimeError(f'No coinciden los registros de {tabla} (SQLite {len(fuente)}, SQL Server {len(destino)})')
            resumen[tabla]=len(fuente)
        return resumen


def copiar(origen, con):
    # Solo migrar hacia tablas vacías. Nunca sobrescribir datos de la instalación.
    for tabla in TABLAS:
        if con.execute('SELECT COUNT(*) FROM dbo.['+tabla+']').fetchone()[0]:
            raise RuntimeError('La base destino ya tiene datos en '+tabla+'; se canceló sin sobrescribir')
    origencon=sqlite3.connect(origen)
    origencon.row_factory=sqlite3.Row
    try:
        con.execute('SET XACT_ABORT ON')
        con.autocommit=False
        try:
            for tabla in TABLAS:
                columnas=columnas_sqlite(origencon,tabla)
                if not columnas: raise RuntimeError('Tabla inexistente en SQLite: '+tabla)
                registros=filas_sqlite(origencon,tabla,columnas)
                if not registros: continue
                quoted=','.join('['+name+']' for name in columnas)
                placeholders=','.join('?' for _ in columnas)
                statement=f'INSERT INTO dbo.[{tabla}] ({quoted}) VALUES ({placeholders})'
                if tabla in IDENTIDAD: con.execute(f'SET IDENTITY_INSERT dbo.[{tabla}] ON')
                try:
                    for row in registros: con.execute(statement,tuple(row))
                finally:
                    if tabla in IDENTIDAD: con.execute(f'SET IDENTITY_INSERT dbo.[{tabla}] OFF')
            # Misma conexión transaccional: no confirmar si falta un registro.
            result=inspeccionar(origen,con)
            con.commit()
            return result
        except Exception:
            con.rollback()
            raise
    finally:
        origencon.close()


def generar_snapshot(origen, destino):
    # sqlite3.backup crea una copia consistente incluso con conexiones abiertas.
    source=sqlite3.connect(origen)
    try:
        with sqlite3.connect(destino) as replica:
            source.backup(replica)
    finally:
        source.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origen',type=Path,default=Path('data/hospital.sqlite3'))
    parser.add_argument('--verificar',action='store_true',help='Comparar todos los registros; no insertar')
    args=parser.parse_args(argv)
    if not args.origen.is_file(): parser.error('La base SQLite original no existe')
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError('Falta pyodbc. Instálalo antes de migrar') from exc
    # Acceder a SQL Server exige conexión explícita y certificado validado.
    conn_str=cadena_conexion()
    with tempfile.TemporaryDirectory(prefix='hospital_snapshot_') as directory:
        snapshot=Path(directory)/'hospital.sqlite3'
        generar_snapshot(args.origen,snapshot)
        # Asegurar tablas y especialidades históricas sin tocar la base original.
        # Forzar SQLite solo para migrar el snapshot (nunca se cambia la ejecución del servidor).
        old=os.environ.get('HOSPITAL_DB_BACKEND')
        try:
            os.environ['HOSPITAL_DB_BACKEND']='sqlite'
            from src.operaciones_extra import HospitalService
            from src.autenticacion import AutenticacionService
            service=HospitalService(snapshot)
            AutenticacionService(snapshot)
        finally:
            if old is None: os.environ.pop('HOSPITAL_DB_BACKEND',None)
            else: os.environ['HOSPITAL_DB_BACKEND']=old
        preparar_esquema()
        raw=pyodbc.connect(conn_str,autocommit=True,timeout=10)
        try:
            if args.verificar:
                resultado=inspeccionar(snapshot,raw)
            else:
                resultado=copiar(snapshot,raw)
                # Releer del servidor tras COMMIT y comparar el snapshot.
                resultado=inspeccionar(snapshot,raw)
        finally:
            raw.close()
        print('MIGRACIÓN VERIFICADA' if not args.verificar else 'VERIFICACIÓN COMPLETA')
        for table,n in resultado.items(): print(f'{table}: {n} registros')
        print('Origen intacto:',args.origen.resolve())
        print('IMPORTANTE: no borres SQLite hasta pasar las pruebas usando HOSPITAL_DB_BACKEND=sqlserver.')


if __name__=='__main__':
    main()
