from io import BytesIO
from PIL import Image


def confirmar_pago(test, tipo='anticipo'):
    if test.query("SELECT 1 FROM pagos WHERE id_pedido=%s AND tipo_pago=%s AND estado='Confirmado'", (test.order,tipo)):
        test.login(test.admin)
        return
    test.login(test.admin)
    test.client.post(f'/pedidos/{test.order}/anticipo', data={'solicitado':'y'})
    image = BytesIO()
    Image.new('RGB',(4,4),'blue').save(image,format='PNG')
    image.seek(0)
    test.login(test.customer)
    response = test.client.post(f'/pedidos/{test.order}/comprobantes', data={'tipo_pago':tipo,'archivo':(image,'pago.png')},content_type='multipart/form-data')
    test.assertEqual(response.status_code,302)
    ident = test.query("SELECT id_pago FROM pagos WHERE id_pedido=%s AND tipo_pago=%s AND estado='Pendiente'",(test.order,tipo))[0][0]
    test.login(test.admin)
    test.assertEqual(test.client.post(f'/pagos/{ident}/decision',data={'decision':'Confirmado'}).status_code,302)
