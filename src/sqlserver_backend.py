"""Conexión externa opcional a Microsoft SQL Server 2019+ mediante ODBC 18.

Nunca hace fallback silencioso a SQLite cuando se solicita SQL Server.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path


def activado():
    driver = os.environ.get('HOSPITAL_DB_BACKEND', 'sqlite').strip().lower()
    if driver not in ('sqlite', 'sqlserver'):
        raise RuntimeError('HOSPITAL_DB_BACKEND debe ser sqlite o sqlserver')
    return driver == 'sqlserver'


def cadena_conexion():
    value = os.environ.get('HOSPITAL_SQLSERVER_CONNECTION_STRING', '').strip()
    if not value:
        raise RuntimeError('Falta HOSPITAL_SQLSERVER_CONNECTION_STRING; no se usará SQLite como alternativa')
    return value


class Fila(dict):
    """Misma interfaz para filas que usan r['campo'], r[0] y dict(r)."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class Resultado:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount
        self._fields = [c[0] for c in cursor.description] if cursor.description else []

    def _row(self, raw):
        if raw is None: return None
        return Fila({key: bytes(value) if isinstance(value, bytearray) else value
                     for key, value in zip(self._fields, raw)})

    def fetchone(self):
        return self._row(self._cursor.fetchone()) if self._fields else None

    def fetchall(self):
        return [self._row(row) for row in self._cursor.fetchall()] if self._fields else []

    def __iter__(self):
        if self._fields:
            for row in self._cursor:
                yield self._row(row)


_INSERT_ID = re.compile(r'^\s*INSERT\s+INTO\s+(pacientes|citas|usuarios|ausencias|notificaciones)\s*\([^)]*\)\s*(?=VALUES\s*\()', re.I | re.S)


class Conexion:
    def __init__(self, raw):
        self.raw = raw
        self._managed = False

    def execute(self, sql, params=()):
        sql = sql.strip()
        cmd = sql.upper().replace(' ', '')
        if cmd == 'BEGINIMMEDIATE':
            self.raw.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            self.raw.execute('BEGIN TRANSACTION')
            return Resultado(self.raw.cursor())
        if cmd in ('COMMIT', 'ROLLBACK'):
            self.raw.execute(cmd+' TRANSACTION')
            self.raw.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
            return Resultado(self.raw.cursor())
        if sql.upper().startswith('PRAGMA '):
            raise RuntimeError('Sentencias SQLite no permitidas en SQL Server')
        values=tuple(params or ())
        found=_INSERT_ID.match(sql)
        if found:
            # Devolver identidad en el mismo INSERT, sin consultas globales susceptibles
            # de carreras entre peticiones del servidor web.
            at=found.end()
            sql=sql[:at]+'OUTPUT INSERTED.id '+sql[at:]
        try:
            cur=self.raw.cursor()
            cur.execute(sql,*values)
            if found:
                return Resultado(cur, int(cur.fetchone()[0]))
            return Resultado(cur)
        except Exception as exc:
            try:
                import pyodbc
                if isinstance(exc, pyodbc.IntegrityError):
                    raise sqlite3.IntegrityError('Restricción de integridad en SQL Server') from exc
            except ImportError:
                pass
            raise

    def executemany(self, sql, rows):
        last=None
        for row in rows: last=self.execute(sql,row)
        return last

    def close(self):
        self.raw.close()

    def __enter__(self):
        # Los módulos de cuentas usan `with con:` como transacción.
        self.raw.execute('BEGIN TRANSACTION')
        self._managed=True
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self.raw.execute('ROLLBACK TRANSACTION' if exc_type else 'COMMIT TRANSACTION')
        finally:
            self.close()


def conectar():
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError('Instala pyodbc y Microsoft ODBC Driver 18 for SQL Server') from exc
    return Conexion(pyodbc.connect(cadena_conexion(),autocommit=True,timeout=10))


def preparar_esquema():
    """Crea tablas necesarias en la base externa existente sin borrar registros."""
    schema=(Path(__file__).resolve().parents[1]/'sqlserver'/'schema.sql').read_text(encoding='utf-8')
    con=conectar()
    try:
        for statement in re.split(r'^GO\s*$',schema,flags=re.M|re.I):
            if statement.strip(): con.raw.execute(statement)
    finally:
        con.close()
