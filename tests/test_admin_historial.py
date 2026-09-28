"""Regresiones administrativas, sin conservar datos de prueba."""
import unittest
from pathlib import Path
from unittest.mock import patch
import test_facturacion_pedidos as base
from test_correcciones import web


class AdminHistorial(unittest.TestCase):
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login
    emit = base.FacturacionPedidos.emit
    invoices = base.FacturacionPedidos.invoices
    tearDown = base.FacturacionPedidos.tearDown

    def setUp(self):
        base.FacturacionPedidos.setUp(self)
        self.service = 987654323
        self.query("""INSERT INTO servicios (id_servicio,nombre,descripcion,precio,duracion,imagen)
                      VALUES (%s,'Catálogo prueba archivo','Descripción de prueba',35,'1 hora','servicio-1.jpg')
                      RETURNING id_servicio""",(self.service,))
        self.query("UPDATE pedidos SET id_servicio=%s WHERE id_pedido=%s RETURNING id_pedido",(self.service,self.order))

    def post_service(self, name):
        image = web.obtener_imagenes_servicios()[0][0]
        return self.client.post("/servicios/nuevo",data={
            "nombre":name,"descripcion":"Descripción de prueba","precio":"35",
            "duracion":"1 hora","imagen":image,"id_proveedor":"0",
        })

    def test_snapshot_pausa_archivo_cambio_nombre_y_pdf(self):
        self.emit()
        invoice = self.invoices()[0][0]
        self.assertEqual(self.client.post(f"/servicios/desactivar/{self.service}").status_code,302)
        self.assertEqual(self.client.post(f"/servicios/{self.service}/archivar").status_code,302)
        self.query("UPDATE servicios SET nombre='Renombrado después' WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        self.assertEqual(self.query("SELECT servicio_nombre,total FROM facturas WHERE id_factura=%s",(invoice,))[0][0],"Catálogo prueba archivo")
        with patch.object(web,"Paragraph",wraps=web.Paragraph) as paragraph:
            r=self.client.get(f"/facturas/{invoice}/pdf")
            self.assertEqual(r.status_code,200)
            self.assertTrue(r.data.startswith(b"%PDF"))
            self.assertIn("Catálogo prueba archivo",[c.args[0] for c in paragraph.call_args_list])
        self.assertEqual(self.client.post(f"/servicios/{self.service}/restaurar").status_code,302)
        self.assertEqual(self.query("SELECT archivado,activo FROM servicios WHERE id_servicio=%s",(self.service,)),[(False,False)])
        self.assertEqual(self.client.post(f"/servicios/activar/{self.service}").status_code,302)

    def test_duplicado_vigente_pausado_archivado(self):
        for archived in (False,True):
            self.query("UPDATE servicios SET archivado=%s,activo=FALSE WHERE id_servicio=%s RETURNING id_servicio",(archived,self.service))
            r=self.post_service("  CATÁLOGO PRUEBA ARCHIVO  ")
            self.assertEqual(r.status_code,200)
            message=("Ya existe un servicio archivado con ese nombre. Puedes restaurarlo en lugar de crear uno nuevo."
                     if archived else "Ya existe un servicio con ese nombre.")
            self.assertIn(message,r.get_data(as_text=True))
        self.assertEqual(self.query("SELECT count(*) FROM servicios WHERE lower(btrim(nombre))=lower(%s)",("Catálogo prueba archivo",)),[(1,)])

    def test_archivados_filtros_propiedad_y_auditoria(self):
        self.client.post(f"/servicios/{self.service}/archivar")
        for route in ("/servicios","/servicios?estado=activos","/servicios?estado=pausados"):
            self.assertNotIn("Catálogo prueba archivo",self.client.get(route).get_data(as_text=True))
        html=self.client.get("/servicios?estado=archivados").get_data(as_text=True)
        self.assertIn("Catálogo prueba archivo",html)
        self.assertIn("Restaurar",html)
        self.assertEqual(self.client.post(f"/servicios/activar/{self.service}").status_code,404)
        self.login(self.customer)
        for state in ("todos","archivados","activos"):
            self.assertNotIn("Catálogo prueba archivo",self.client.get("/servicios",query_string={"estado":state}).get_data(as_text=True))
        self.assertNotIn(self.service,dict(web.cargar_opciones_servicios()))
        self.assertEqual(self.client.post(f"/servicios/{self.service}/restaurar").status_code,403)
        changes=self.query("""SELECT datos_anteriores->>'archivado',datos_nuevos->>'archivado'
                              FROM auditoria WHERE tabla='servicios' AND id_registro=%s AND operacion='UPDATE'""",(str(self.service),))
        self.assertIn(("false","true"),changes)

    def test_pdf_factura_historica_reparada(self):
        rows=self.query("SELECT id_factura,servicio_nombre FROM facturas WHERE numero=%s",("FAC-20260922190640-5",))
        if not rows:
            self.skipTest("La factura histórica local no existe en esta instalación.")
        invoice,name=rows[0]
        self.assertEqual(name,"Recuperación de Datos")
        with patch.object(web,"Paragraph",wraps=web.Paragraph) as paragraph:
            r=self.client.get(f"/facturas/{invoice}/pdf")
            self.assertEqual(r.status_code,200)
            self.assertIn(name,[c.args[0] for c in paragraph.call_args_list])

    def test_reparacion_auditoria_idempotente_sin_sobrescribir(self):
        self.emit()
        invoice=self.invoices()[0][0]
        # Simula FK histórica perdida. La auditoría real conserva los ids anteriores.
        self.query("UPDATE facturas SET servicio_nombre='',id_servicio=NULL WHERE id_factura=%s RETURNING id_factura",(invoice,))
        self.query("UPDATE pedidos SET id_servicio=NULL WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        sql=Path("sql/migracion_historial_archivado.sql").read_text(encoding="utf-8")
        with self.conn.cursor() as cursor: cursor.execute(sql)
        self.assertEqual(self.query("SELECT servicio_nombre FROM facturas WHERE id_factura=%s",(invoice,)),[("Catálogo prueba archivo",)])
        self.query("UPDATE servicios SET nombre='Nombre posterior de prueba' WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        with self.conn.cursor() as cursor: cursor.execute(sql)
        self.assertEqual(self.query("SELECT servicio_nombre FROM facturas WHERE id_factura=%s",(invoice,)),[("Catálogo prueba archivo",)])

    def test_historial_ambiguo_no_se_inventa(self):
        self.emit()
        invoice=self.invoices()[0][0]
        self.query("UPDATE servicios SET nombre='Otro nombre histórico' WHERE id_servicio=%s RETURNING id_servicio",(self.service,))
        self.query("UPDATE facturas SET servicio_nombre=NULL,id_servicio=NULL WHERE id_factura=%s RETURNING id_factura",(invoice,))
        self.query("UPDATE pedidos SET id_servicio=NULL WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        with self.conn.cursor() as cursor:
            cursor.execute(Path("sql/migracion_historial_archivado.sql").read_text(encoding="utf-8"))
        self.assertEqual(self.query("SELECT servicio_nombre FROM facturas WHERE id_factura=%s",(invoice,)),[(None,)])

    def test_filtros_admin_pedidos(self):
        self.query("UPDATE pedidos SET estado='Solicitado' WHERE id_pedido=%s RETURNING id_pedido",(self.order,))
        for state,found in (("Solicitado",True),("Entregado",False)):
            with patch.object(web,"render_template",wraps=web.render_template) as render:
                r=self.client.get("/pedidos",query_string={"q":str(self.order),"estado":state,"factura":"solicitada","orden":"antiguos"})
                self.assertEqual(r.status_code,200)
                self.assertEqual(bool(render.call_args.kwargs["pedidos"]),found)
        for invoice_filter,found in (("no_solicitada",False),("solicitada",True),("emitida",False)):
            with patch.object(web,"render_template",wraps=web.render_template) as render:
                self.client.get("/pedidos",query_string={"q":str(self.order),"factura":invoice_filter})
                self.assertEqual(bool(render.call_args.kwargs["pedidos"]),found)
        with patch.object(web,"render_template",wraps=web.render_template) as render:
            self.client.get("/pedidos",query_string={"fecha":"fecha-maliciosa","orden":"DROP TABLE pedidos","estado":"malo","factura":"malo"})
            self.assertEqual(render.call_args.kwargs["fecha"],"")
            self.assertEqual(render.call_args.kwargs["orden"],"recientes")

    def test_filtros_clientes_y_servicios(self):
        row=self.query("SELECT id_cliente,estado,activo FROM clientes LIMIT 1")[0]
        with patch.object(web,"render_template",wraps=web.render_template) as render:
            self.client.get("/clientes",query_string={"estado":row[1],"registro":"activos" if row[2] else "inactivos","orden":"antiguos"})
            results=render.call_args.kwargs["clientes"]
            self.assertTrue(all(c["estado"]==row[1] and c["activo"]==row[2] for c in results))
        for order in ("nombre","menor_precio","mayor_precio","recientes"):
            with patch.object(web,"render_template",wraps=web.render_template) as render:
                r=self.client.get("/servicios",query_string={"orden":order})
                self.assertEqual(r.status_code,200)
                results=render.call_args.kwargs["servicios"]
                if order=="menor_precio":
                    self.assertEqual([r["precio"] for r in results],sorted(r["precio"] for r in results))
                if order=="mayor_precio":
                    self.assertEqual([r["precio"] for r in results],sorted((r["precio"] for r in results),reverse=True))
        for route in ("/clientes","/servicios","/pedidos"):
            r=self.client.get(route,query_string={"q":"' OR 1=1 --","estado":"malo","orden":"DROP TABLE servicios","proveedor":"1 OR 1=1"})
            self.assertEqual(r.status_code,200)

if __name__ == "__main__":
    unittest.main()
