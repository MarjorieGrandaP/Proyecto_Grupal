"""Instalación en esquema vacío, con rollback total y sin tocar las cuentas reales."""
from pathlib import Path
import secrets
import unittest
from uuid import uuid4
from psycopg2 import sql
from werkzeug.security import check_password_hash
from conexion.bootstrap_admin import crear_admin_desde_entorno
from test_correcciones import db, Transaction


class BootstrapAdmin(unittest.TestCase):
    def setUp(self):
        self.conn=db.obtener_conexion()
        self.schema='test_pcfix_'+uuid4().hex
        self.schema_sql=Path('sql/esquema.sql').read_text(encoding='utf-8')
        with self.conn.cursor() as c:
            c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            c.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(self.schema)))
            c.execute(self.schema_sql)
        self.env={'ADMIN_USERNAME':'AdministradorPrueba','ADMIN_EMAIL':'admin@example.com',
                  'ADMIN_PASSWORD':'Aa1!'+secrets.token_urlsafe(24)}
        self.connect=lambda:Transaction(self.conn)

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def rows(self, query, args=()):
        with self.conn.cursor() as c:
            c.execute(query,args)
            return c.fetchall()

    def test_esquema_vacio_bootstrap_hash_idempotencia(self):
        self.assertEqual(self.rows('SELECT count(*) FROM usuarios'),[(0,)])
        self.assertTrue(crear_admin_desde_entorno(self.connect,self.env))
        row=self.rows('SELECT usuario,correo,password,rol FROM usuarios')[0]
        self.assertEqual(row[:2],('AdministradorPrueba','admin@example.com'))
        self.assertTrue(check_password_hash(row[2],self.env['ADMIN_PASSWORD']))
        self.assertNotEqual(row[2],self.env['ADMIN_PASSWORD'])
        self.assertEqual(row[3],'admin')
        self.assertFalse(crear_admin_desde_entorno(self.connect,{**self.env,'ADMIN_PASSWORD':'OtroPassword1!'}))
        self.assertEqual(self.rows('SELECT password FROM usuarios')[0][0],row[2])
        with self.conn.cursor() as c:
            c.execute(self.schema_sql)
            c.execute(self.schema_sql)
        self.assertEqual(self.rows('SELECT count(*) FROM usuarios'),[(1,)])
        self.assertEqual(self.rows('SELECT count(*) FROM servicios'),[(6,)])
        audit=self.rows("SELECT datos_nuevos FROM auditoria WHERE tabla='usuarios'")
        self.assertTrue(audit)
        self.assertTrue(all('password' not in r[0] for r in audit))

    def test_sin_variables_y_parciales(self):
        self.assertFalse(crear_admin_desde_entorno(self.connect,{}))
        with self.assertRaises(RuntimeError):
            crear_admin_desde_entorno(self.connect,{'ADMIN_USERNAME':'Administrador'})
        self.assertEqual(self.rows('SELECT count(*) FROM usuarios'),[(0,)])

    def test_no_promueve_cuenta_existente_ni_password_debil(self):
        with self.assertRaises(RuntimeError):
            crear_admin_desde_entorno(self.connect,{**self.env,'ADMIN_PASSWORD':'debil'})
        with self.conn.cursor() as c:
            c.execute("INSERT INTO usuarios (usuario,correo,password,rol) VALUES (%s,%s,'hash_prueba','cliente')",(self.env['ADMIN_USERNAME'],self.env['ADMIN_EMAIL']))
        with self.assertRaises(RuntimeError):
            crear_admin_desde_entorno(self.connect,self.env)
        self.assertEqual(self.rows('SELECT rol FROM usuarios'),[('cliente',)])

if __name__ == '__main__':
    unittest.main()
