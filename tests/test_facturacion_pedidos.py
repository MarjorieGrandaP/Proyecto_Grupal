"""Pruebas con PostgreSQL real y rollback de todos los datos de prueba."""
import unittest
from unittest.mock import patch
from test_correcciones import web, db, Transaction


class FacturacionPedidos(unittest.TestCase):
    def setUp(self):
        self.conn = db.obtener_conexion()
        self.previous_csrf = web.app.config.get("WTF_CSRF_ENABLED", True)
        web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.patcher = patch.object(web, "obtener_conexion", return_value=Transaction(self.conn))
        self.patcher.start()
        self.client = web.app.test_client()
        self.admin = self.query("SELECT id_usuario FROM usuarios WHERE rol='admin' LIMIT 1")[0][0]
        self.customer = self.query("SELECT id_usuario FROM usuarios WHERE rol='cliente' LIMIT 1")[0][0]
        self.service = -876543
        self.order = 987654321
        self.query("""INSERT INTO servicios (id_servicio,nombre,descripcion,precio,duracion,imagen,activo)
                      VALUES (%s,'Servicio original prueba','Prueba transaccional',25.50,'1 hora','servicio-1.jpg',TRUE)
                      RETURNING id_servicio""", (self.service,))
        self.query("""INSERT INTO pedidos (id_pedido,id_usuario,id_servicio,equipo,descripcion,estado,solicita_factura)
                      VALUES (%s,%s,%s,'Laptop','Prueba','Entregado',TRUE) RETURNING id_pedido""",
                   (self.order,self.customer,self.service))
        self.login(self.admin)

    def tearDown(self):
        self.patcher.stop()
        self.conn.rollback()
        self.conn.close()
        web.app.config["WTF_CSRF_ENABLED"] = self.previous_csrf

    def query(self, sql, args=()):
        with self.conn.cursor() as cursor:
            cursor.execute(sql,args)
            return cursor.fetchall()

    def login(self, user):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user)
            session["_fresh"] = True

    def emit(self):
        # Datos manipulados: la emisión debe ignorarlos por completo.
        return self.client.post(f"/pedidos/{self.order}/factura", data={
            "total":"0.01", "id_servicio":"999", "id_usuario":"999",
            "fecha":"2000-01-01", "numero":"MANIPULADO",
        })

    def invoices(self):
        return self.query("SELECT id_factura FROM facturas WHERE id_pedido=%s",(self.order,))

    def test_en_revision_solicitada_no_emite(self):
        self.query("UPDATE pedidos SET estado='En revisión' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.assertEqual(self.emit().status_code,302)
        self.assertEqual(self.invoices(),[])

    def test_listo_solicitada_no_emite(self):
        self.query("UPDATE pedidos SET estado='Listo' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.emit()
        self.assertEqual(self.invoices(),[])

    def test_entregado_sin_solicitud_no_emite(self):
        self.query("UPDATE pedidos SET solicita_factura=FALSE WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        self.emit()
        self.assertEqual(self.invoices(),[])

    def test_entregado_solicitada_datos_automaticos_y_no_duplicados(self):
        self.assertEqual(self.emit().status_code,302)
        self.assertEqual(len(self.invoices()),1)
        row=self.query("""SELECT id_usuario,id_servicio,total,estado,servicio_nombre,
                                fecha=CURRENT_DATE,numero FROM facturas WHERE id_pedido=%s""",(self.order,))[0]
        self.assertEqual(row[0:2],(self.customer,self.service))
        self.assertEqual(str(row[2]),"25.50")
        self.assertEqual(row[3:6],("Pendiente","Servicio original prueba",True))
        self.assertTrue(row[6].startswith("FAC-"))
        self.emit()
        self.assertEqual(len(self.invoices()),1)

    def test_ruta_manual_get_y_post_redirigen_sin_insert(self):
        before=self.query("SELECT count(*) FROM facturas")
        for method in ("get","post"):
            response=getattr(self.client,method)("/facturacion/nuevo")
            self.assertEqual(response.status_code,302)
            self.assertTrue(response.location.endswith("/pedidos"))
            with self.client.session_transaction() as session:
                self.assertIn(("info","Las facturas se emiten desde pedidos entregados."),session["_flashes"])
        self.assertEqual(self.query("SELECT count(*) FROM facturas"),before)

    def test_nombre_conservado_al_pausar_renombrar_y_pdf(self):
        self.emit()
        invoice=self.invoices()[0][0]
        self.query("UPDATE servicios SET activo=FALSE,nombre='Nombre cambiado' WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        self.assertNotIn(self.service,dict(web.cargar_opciones_servicios()))
        self.assertIn("Servicio original prueba",self.client.get("/facturacion").get_data(as_text=True))
        with patch.object(web,"Paragraph",wraps=web.Paragraph) as paragraph:
            response=self.client.get(f"/facturas/{invoice}/pdf")
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.data.startswith(b"%PDF"))
            texts=[call.args[0] for call in paragraph.call_args_list]
            self.assertIn("Servicio original prueba",texts)
            self.assertNotIn("Nombre cambiado",texts)
        self.login(self.customer)
        self.assertIn("Servicio original prueba",self.client.get("/mis-facturas").get_data(as_text=True))
        self.assertEqual(self.client.get("/mis-pedidos").status_code,200)
        self.query("UPDATE servicios SET activo=TRUE WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        self.assertEqual(self.query("SELECT servicio_nombre FROM facturas WHERE id_factura=%s",(invoice,))[0][0],"Servicio original prueba")

    def test_migracion_completa_nulos_sin_sobrescribir(self):
        from pathlib import Path
        self.emit()
        invoice=self.invoices()[0][0]
        self.query("UPDATE facturas SET servicio_nombre=NULL WHERE id_factura=%s RETURNING id_factura",(invoice,))
        schema=Path("sql/esquema.sql").read_text(encoding="utf-8")
        migration=schema[schema.index("ALTER TABLE facturas ADD COLUMN IF NOT EXISTS servicio_nombre"):]
        with self.conn.cursor() as cursor:
            cursor.execute(migration)
        self.assertEqual(self.query("SELECT servicio_nombre FROM facturas WHERE id_factura=%s",(invoice,))[0][0],"Servicio original prueba")
        self.query("UPDATE servicios SET nombre='Nombre posterior' WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        with self.conn.cursor() as cursor:
            cursor.execute(migration)
        self.assertEqual(self.query("SELECT servicio_nombre FROM facturas WHERE id_factura=%s",(invoice,))[0][0],"Servicio original prueba")

    def test_pedido_con_servicio_pausado_si_emite(self):
        self.query("UPDATE servicios SET activo=FALSE WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        self.emit()
        self.assertEqual(len(self.invoices()),1)

    def test_pedido_inexistente_y_permisos_csrf(self):
        self.assertEqual(self.client.post("/pedidos/987654322/factura").status_code,404)
        self.login(self.customer)
        self.assertEqual(self.emit().status_code,403)
        self.login(self.admin)
        web.app.config["WTF_CSRF_ENABLED"]=True
        self.emit()
        self.assertEqual(self.invoices(),[])

    def test_interfaz_emision_y_panel(self):
        self.query("UPDATE pedidos SET estado='Listo' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        html=self.client.get("/pedidos").get_data(as_text=True)
        self.assertIn("Disponible al entregar",html)
        self.assertNotIn(f'form-emision-{self.order}"',html)
        self.query("UPDATE pedidos SET estado='Entregado' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        html=self.client.get("/pedidos").get_data(as_text=True)
        self.assertIn(f'form-emision-{self.order}"',html)
        self.emit()
        html=self.client.get("/pedidos").get_data(as_text=True)
        self.assertIn("Ver PDF",html)
        self.assertNotIn(f'form-emision-{self.order}"',html)
        self.login(self.customer)
        response=self.client.get("/dashboard")
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        for title in ("Nueva solicitud","Mis pedidos","Mis facturas","Servicios disponibles","Mi perfil"):
            self.assertIn(title,html)
        self.assertEqual(html.count("col-12 col-md-6 col-lg-4"),5)
        self.assertIn("Bienvenido,",html)

if __name__ == "__main__":
    unittest.main()
