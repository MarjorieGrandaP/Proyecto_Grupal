"""Regresiones PC-Fix. Ejecutar: python -m unittest discover -s tests -v.
Las pruebas PostgreSQL revierten los datos; las secuencias de auditoría pueden avanzar.
"""

import ast
from pathlib import Path
import unittest
from unittest.mock import patch
from werkzeug.datastructures import MultiDict
from flask_login import login_user
import conexion.conexion as db

# Importar la aplicación sin ejecutar semillas ni migraciones al arrancar.
with patch.object(db, "inicializar_base_datos"):
    import app as web
from forms import (
    UsuarioForm,
    PerfilForm,
    ClienteForm,
    ProveedorForm,
    ProductoForm,
    FacturacionForm,
)


class Transaction:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self, *args, **kwargs):
        return self.connection.cursor(*args, **kwargs)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class Correcciones(unittest.TestCase):
    def test_validaciones(self):
        with web.app.test_request_context():

            def field_valid(cls, name, value):
                form = cls(MultiDict({name: value}), meta={"csrf": False})
                field = getattr(form, name)
                return field.validate(form)

            for value in ("abc", "Áéíóúüñ", "A" * 50):
                self.assertTrue(field_valid(UsuarioForm, "usuario", value), value)
            for value in ("", "ab", "abc123", "abc_", "abc ", "ab?", "A" * 51):
                self.assertFalse(field_valid(UsuarioForm, "usuario", value), value)
            for cls in (UsuarioForm, PerfilForm, ClienteForm, ProveedorForm):
                self.assertTrue(field_valid(cls, "telefono", "0991234567"))
                for value in (
                    "099abc4567",
                    "099 1234567",
                    "１２３４５６７８９",
                    "0991234567" + chr(10),
                ):
                    self.assertFalse(field_valid(cls, "telefono", value))
            self.assertTrue(field_valid(PerfilForm, "telefono", ""))
            self.assertTrue(field_valid(ClienteForm, "cedula", ""))
            self.assertTrue(field_valid(ClienteForm, "cedula", "0012345678"))
            self.assertFalse(field_valid(ClienteForm, "cedula", "123abc"))
            for cls, name in ((ProductoForm, "precio"), (FacturacionForm, "total")):
                self.assertTrue(field_valid(cls, name, "12.50"))
                self.assertTrue(field_valid(cls, name, "0.01"))
                self.assertTrue(field_valid(cls, name, "99999999.99"))
                for value in ("-1", "abc", "NaN", "Infinity", "100000000"):
                    self.assertFalse(field_valid(cls, name, value), value)

    def test_sintaxis(self):
        for path in [Path("app.py"), *Path("forms").glob("*.py")]:
            ast.parse(path.read_text(encoding="utf-8"))
        for name in web.app.jinja_env.list_templates():
            web.app.jinja_env.get_template(name)

    def test_postgresql_y_rutas(self):
        conn = db.obtener_conexion()
        proxy = Transaction(conn)
        web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        try:
            with conn.cursor() as c:
                c.execute("SELECT id_usuario FROM usuarios WHERE rol = 'admin' LIMIT 1")
                admin = c.fetchone()[0]
                c.execute(
                    "SELECT id_usuario FROM usuarios WHERE rol = 'cliente' LIMIT 1"
                )
                customer = c.fetchone()[0]
                c.execute(
                    "SELECT id_servicio FROM servicios ORDER BY id_servicio LIMIT 1"
                )
                service = c.fetchone()[0]
                c.execute("SELECT id_cliente FROM clientes ORDER BY id_cliente LIMIT 1")
                client_id = c.fetchone()[0]
                c.execute(
                    "SELECT id_proveedor FROM proveedores ORDER BY id_proveedor LIMIT 1"
                )
                provider = c.fetchone()[0]
                c.execute(
                    """INSERT INTO pedidos (id_pedido,id_usuario,id_servicio,equipo,descripcion,solicita_factura)
                             VALUES (-987654,%s,%s,'Prueba','Regresión transaccional',TRUE)""",
                    (customer, service),
                )
            with patch.object(web, "obtener_conexion", return_value=proxy):
                client = web.app.test_client()
                with client.session_transaction() as session:
                    session["_user_id"] = str(admin)
                    session["_fresh"] = True

                def sql(query, args=()):
                    with conn.cursor() as c:
                        c.execute(query, args)
                        return c.fetchall()

                for plural, key, ident in (
                    ("servicios", "id_servicio", service),
                    ("clientes", "id_cliente", client_id),
                    ("proveedores", "id_proveedor", provider),
                ):
                    self.assertEqual(
                        client.post(f"/{plural}/desactivar/{ident}").status_code, 302
                    )
                    self.assertEqual(
                        sql(f"SELECT activo FROM {plural} WHERE {key}=%s", (ident,)),
                        [(False,)],
                    )
                    self.assertEqual(client.get(f"/{plural}").status_code, 200)
                    self.assertIn(
                        b"Reactivar" if plural == "servicios" else b"Activar",
                        client.get(f"/{plural}").data,
                    )
                    if plural == "servicios":
                        self.assertNotIn(service, dict(web.cargar_opciones_servicios()))
                        with web.app.test_request_context(
                            method="POST",
                            data={
                                "servicio": str(service),
                                "equipo": "Laptop",
                                "descripcion": "Prueba",
                            },
                        ):
                            form = web.PedidoForm()
                            form.servicio.choices = web.cargar_opciones_servicios()
                            self.assertFalse(form.validate())
                            self.assertIn("servicio", form.errors)
                        historical = sql(
                            "SELECT f.id_factura,s.nombre FROM facturas f JOIN servicios s ON s.id_servicio=f.id_servicio WHERE s.id_servicio=%s",
                            (service,),
                        )
                        self.assertTrue(historical)
                        self.assertEqual(client.get("/facturacion").status_code, 200)
                    if plural == "proveedores":
                        self.assertNotIn(
                            provider, dict(web.obtener_opciones_proveedores())
                        )
                    response = client.get("/facturacion/nuevo")
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.location.endswith("/pedidos"))
                    self.assertEqual(
                        client.post(f"/{plural}/activar/{ident}").status_code, 302
                    )
                    self.assertEqual(
                        sql(f"SELECT activo FROM {plural} WHERE {key}=%s", (ident,)),
                        [(True,)],
                    )
                    changes = sql(
                        """SELECT datos_anteriores->>'activo',datos_nuevos->>'activo'
                                   FROM auditoria WHERE tabla=%s AND id_registro=%s AND operacion='UPDATE'""",
                        (plural, str(ident)),
                    )
                    self.assertIn(("true", "false"), changes)
                    self.assertIn(("false", "true"), changes)
                self.assertIn(service, dict(web.cargar_opciones_servicios()))
                for field in ("nombre", "cedula", "telefono", "correo", "equipo"):
                    value = sql(
                        f"SELECT {field} FROM clientes WHERE {field} IS NOT NULL AND {field} <> '' LIMIT 1"
                    )[0][0]
                    response = client.get("/clientes", query_string={"q": value})
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(value, response.get_data(as_text=True))
                self.assertEqual(
                    client.get(
                        "/clientes", query_string={"q": "' OR 1=1 --"}
                    ).status_code,
                    200,
                )

                # Identificador negativo de prueba: invocar la vista con autenticación.
                def emit():
                    with web.app.test_request_context(method="POST"):
                        login_user(web.load_user(str(admin)))
                        return web.emitir_factura(-987654)

                emit()
                self.assertEqual(
                    sql("SELECT count(*) FROM facturas WHERE id_pedido=-987654"), [(0,)]
                )
                sql(
                    "UPDATE pedidos SET estado='Entregado' WHERE id_pedido=-987654 RETURNING id_pedido"
                )
                valores = web.importes(
                    sql(
                        "SELECT precio FROM servicios WHERE id_servicio=%s", (service,)
                    )[0][0],
                    web.app.config["IVA_RATE"],
                )
                sql(
                    "UPDATE pedidos SET subtotal=%s,porcentaje_iva=%s,valor_iva=%s,total=%s,anticipo_requerido=%s,saldo_requerido=%s WHERE id_pedido=-987654 RETURNING id_pedido",
                    tuple(
                        valores[k]
                        for k in (
                            "subtotal",
                            "porcentaje_iva",
                            "valor_iva",
                            "total",
                            "anticipo_requerido",
                            "saldo_requerido",
                        )
                    ),
                )
                sql(
                    "INSERT INTO pagos(id_pedido,tipo_pago,monto,estado,nombre_archivo,mime_type,contenido,id_usuario_confirma,fecha_confirmacion) VALUES (-987654,'total',%s,'Confirmado','fixture.png','image/png',%s,%s,CURRENT_TIMESTAMP) RETURNING id_pago",
                    (valores["total"], b"fixture", admin),
                )
                emit()
                self.assertEqual(
                    sql("SELECT count(*) FROM facturas WHERE id_pedido=-987654"), [(1,)]
                )
                emit()
                self.assertEqual(
                    sql("SELECT count(*) FROM facturas WHERE id_pedido=-987654"), [(1,)]
                )
                self.assertEqual(client.get("/pedidos").status_code, 200)
                with client.session_transaction() as session:
                    session["_user_id"] = str(customer)
                self.assertEqual(client.get("/pedido/nuevo").status_code, 200)
                self.assertEqual(
                    client.post(f"/servicios/desactivar/{service}").status_code, 403
                )
                web.app.config["WTF_CSRF_ENABLED"] = True
                with client.session_transaction() as session:
                    session["_user_id"] = str(admin)
                self.assertEqual(
                    client.post(f"/servicios/desactivar/{service}").status_code, 400
                )
        finally:
            conn.rollback()
            conn.close()
            web.app.config["WTF_CSRF_ENABLED"] = True

    def test_esquema_reejecutable(self):
        conn = db.obtener_conexion()
        try:
            with conn.cursor() as c:
                original = {}
                for table in ("servicios", "clientes", "proveedores", "facturas"):
                    c.execute(f"SELECT to_jsonb(t) FROM {table} t")
                    original[table] = c.fetchall()
                schema = Path("sql/esquema.sql").read_text(encoding="utf-8")
                c.execute(schema)
                first = {}
                for table in original:
                    c.execute(f"SELECT to_jsonb(t) FROM {table} t")
                    first[table] = c.fetchall()
                    for row in original[table]:
                        self.assertIn(row, first[table])
                c.execute(schema)
                for table in original:
                    c.execute(f"SELECT to_jsonb(t) FROM {table} t")
                    self.assertEqual(first[table], c.fetchall())
        finally:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
