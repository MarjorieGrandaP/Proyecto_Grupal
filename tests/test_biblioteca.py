"""Biblioteca multimedia real en PostgreSQL, con rollback de los datos de prueba."""
from io import BytesIO
from pathlib import Path
import re
import unittest
from PIL import Image
import test_facturacion_pedidos as base
from test_correcciones import web


class Biblioteca(unittest.TestCase):
    setUp = base.FacturacionPedidos.setUp
    tearDown = base.FacturacionPedidos.tearDown
    query = base.FacturacionPedidos.query
    login = base.FacturacionPedidos.login

    def archivo(self, formato="PNG", color="red"):
        out = BytesIO()
        Image.new("RGB", (20, 20), color).save(out, format=formato)
        return out.getvalue()

    def subir(self, contenido=None, nombre="prueba.png", **extra):
        response = self.client.post('/imagenes-servicio/subir', data={
            'archivo': (BytesIO(self.archivo() if contenido is None else contenido), nombre), **extra
        }, content_type='multipart/form-data')
        response.request.input_stream.close()
        return response

    def servicio(self, imagen, nombre='Servicio multimedia nuevo', ident=None):
        return self.client.post('/servicios/nuevo' if ident is None else f'/servicios/editar/{ident}', data={
            'nombre':nombre, 'descripcion':'Descripción de prueba multimedia', 'precio':'25.50',
            'duracion':'1 hora', 'imagen':imagen, 'id_proveedor':'0', 'requiere_entrega_equipo':'si'
        })

    def test_jpg_png_webp_y_servir_bytes_mime_cache(self):
        for formato, ext, mime in [('JPEG','jpg','image/jpeg'),('PNG','png','image/png'),('WEBP','webp','image/webp')]:
            data=self.archivo(formato)
            response=self.subir(data, 'foto.'+ext)
            self.assertEqual(response.status_code,201, response.get_data(as_text=True))
            item=response.json['imagen']
            result=self.client.get(item['url'])
            self.assertEqual(result.data,data)
            self.assertEqual(result.mimetype,mime)
            self.assertEqual(result.headers['X-Content-Type-Options'],'nosniff')
            self.assertEqual(self.client.get(item['url'],headers={'If-None-Match':result.headers['ETag']}).status_code,304)
            self.assertIn(item['valor'],dict(web.obtener_imagenes_servicios()))
        self.assertEqual(self.subir(self.archivo('JPEG','blue'), 'otra.JPEG').status_code,201)

    def test_rechaza_falso_formato_tamano_corrupto(self):
        cases=[(b'<html>Falso</html>','falso.png'),(self.archivo(),'falso.jpg'),
               (self.archivo(),'foto.svg'),(b'','vacio.png'),(self.archivo()[:30],'truncada.png'),
               (b'x'*(2*1024*1024+1),'grande.png')]
        before=self.query('SELECT count(*) FROM imagenes_servicio')
        for content,name in cases:
            self.assertIn(self.subir(content,name).status_code,(400,413),name)
        self.assertEqual(self.query('SELECT count(*) FROM imagenes_servicio'),before)

    def test_duplicada_reutiliza_sin_bytea_nuevo(self):
        first=self.subir().json['imagen']
        second=self.subir(nombre='otro-nombre.png')
        self.assertEqual(second.status_code,200)
        self.assertTrue(second.json['reutilizada'])
        self.assertEqual(first['id'],second.json['imagen']['id'])
        self.assertEqual(self.query('SELECT count(*) FROM imagenes_servicio WHERE id_imagen=%s',(first['id'],)),[(1,)])

    def test_biblioteca_estaticas_y_nueva_y_modal(self):
        item=self.subir().json['imagen']
        result=self.client.get('/imagenes-servicio/biblioteca').json['imagenes']
        self.assertEqual(result[0]['id'],item['id'])
        for name in ('servicio-1.jpg','servicio-2.jpg','servicio-3.jpg','servicio-4.jpg'):
            row=next(r for r in result if r['valor']==name)
            self.assertIsNone(row['eliminar_url'])
            self.assertGreater(row['tamano'],0)
            self.assertEqual(self.client.post('/imagenes-servicio/'+name+'/eliminar').status_code,404)
        html=self.client.get('/servicios/nuevo').get_data(as_text=True)
        for text in ('bibliotecaMultimedia','Biblioteca multimedia','Subir nueva','Usar esta imagen','buscarImagen','archivoImagen'):
            self.assertIn(text,html)

    def test_crear_estatica_y_reutilizar_en_dos_servicios(self):
        self.assertEqual(self.servicio('servicio-2.jpg').status_code,302)
        row=self.query("SELECT imagen,id_imagen FROM servicios WHERE nombre='Servicio multimedia nuevo'")[0]
        self.assertEqual(row,('servicio-2.jpg',None))
        item=self.subir().json['imagen']
        for name in ('Servicio imagen compartida uno','Servicio imagen compartida dos'):
            self.assertEqual(self.servicio(item['valor'],name).status_code,302)
        self.assertEqual(self.query('SELECT count(*) FROM servicios WHERE id_imagen=%s',(item['id'],)),[(2,)])
        response=self.client.post(item['eliminar_url'])
        self.assertEqual(response.status_code,409)
        self.assertIn('2 servicio(s)',response.json['error'])
        self.assertIn(item['url'],self.client.get('/servicios').get_data(as_text=True))

    def test_editar_conserva_y_cambia_a_estatica(self):
        item=self.subir().json['imagen']
        name='Servicio conservar imagen'
        self.servicio(item['valor'],name)
        ident=self.query('SELECT id_servicio FROM servicios WHERE nombre=%s',(name,))[0][0]
        html=self.client.get(f'/servicios/editar/{ident}').get_data(as_text=True)
        self.assertRegex(html, r'<option selected value="'+re.escape(item['valor'])+'"')
        self.assertEqual(self.servicio(item['valor'],name,ident).status_code,302)
        self.assertEqual(self.query('SELECT id_imagen FROM servicios WHERE id_servicio=%s',(ident,)),[(item['id'],)])
        self.assertEqual(self.servicio('servicio-3.jpg',name,ident).status_code,302)
        self.assertEqual(self.query('SELECT imagen,id_imagen FROM servicios WHERE id_servicio=%s',(ident,)),[('servicio-3.jpg',None)])
        self.assertEqual(self.client.post(item['eliminar_url']).status_code,200)
        self.assertEqual(self.client.get(item['url']).status_code,404)

    def test_pausar_archivar_conserva_imagen_y_bloquea_borrado(self):
        # Usar un id positivo: los conversores Flask no aceptan negativos.
        item=self.subir().json['imagen']
        name='Servicio imagen archivada'
        self.servicio(item['valor'],name)
        ident=self.query('SELECT id_servicio FROM servicios WHERE nombre=%s',(name,))[0][0]
        self.client.post(f'/servicios/desactivar/{ident}')
        self.client.post(f'/servicios/{ident}/archivar')
        self.assertEqual(self.query('SELECT id_imagen,archivado FROM servicios WHERE id_servicio=%s',(ident,)),[(item['id'],True)])
        self.assertEqual(self.client.post(item['eliminar_url']).status_code,409)
        self.assertEqual(self.client.get(item['url']).status_code,200)

    def test_permisos_csrf_y_ids_inventados(self):
        item=self.subir().json['imagen']
        self.login(self.customer)
        self.assertEqual(self.subir().status_code,403)
        self.assertEqual(self.client.get('/imagenes-servicio/biblioteca').status_code,403)
        self.assertEqual(self.client.post(item['eliminar_url']).status_code,403)
        self.assertEqual(self.client.get(item['url']).status_code,200)
        self.login(self.admin)
        self.assertEqual(self.servicio('bd:987654321').status_code,200)
        web.app.config['WTF_CSRF_ENABLED']=True
        self.assertEqual(self.subir().status_code,400)
        self.assertEqual(self.client.post(item['eliminar_url']).status_code,400)
        html=self.client.get('/servicios/nuevo').get_data(as_text=True)
        token=re.search(r'name="csrf_token"[^>]*value="([^"]+)"',html).group(1)
        self.assertEqual(self.subir(self.archivo(color='green'),csrf_token=token).status_code,201)
        self.assertEqual(self.client.post(item['eliminar_url'],data={'csrf_token':token}).status_code,200)

    def test_migracion_repetible_conserva_asociacion(self):
        item=self.subir().json['imagen']
        self.servicio(item['valor'])
        sql=Path('sql/migracion_biblioteca_multimedia.sql').read_text(encoding='utf-8')
        with self.conn.cursor() as c:
            c.execute(sql)
            c.execute(sql)
        self.assertEqual(self.query('SELECT count(*) FROM servicios WHERE id_imagen=%s',(item['id'],)),[(1,)])
        self.assertEqual(self.client.get(item['url']).status_code,200)

if __name__ == '__main__':
    unittest.main()
