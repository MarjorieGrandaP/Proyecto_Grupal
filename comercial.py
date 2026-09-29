"""Configuración vigente y cálculo de nuevas operaciones (porcentajes en 0–100)."""
from decimal import Decimal
from finanzas import importes


def leer_configuracion(cursor, tarifa_respaldo):
    cursor.execute("""SELECT c.*, (CURRENT_TIMESTAMP AT TIME ZONE 'America/Guayaquil')::date AS hoy
                      FROM (SELECT 1) AS unica
                      LEFT JOIN configuracion_comercial c ON c.id_configuracion = 1""")
    fila = cursor.fetchone()
    datos = dict(fila) if isinstance(fila, dict) else dict(zip((c[0] for c in cursor.description), fila))
    if datos['id_configuracion'] is None:
        datos.update(porcentaje_iva=tarifa_respaldo * 100, descuento_activo=False,
                     porcentaje_descuento=Decimal('0'))
    return datos


def descuento_vigente(config):
    return bool(config['descuento_activo']
                and (not config['fecha_inicio_descuento'] or config['hoy'] >= config['fecha_inicio_descuento'])
                and (not config['fecha_fin_descuento'] or config['hoy'] <= config['fecha_fin_descuento']))


def cotizar(precio, config):
    descuento = config['porcentaje_descuento'] / 100 if descuento_vigente(config) else Decimal('0')
    valores = importes(precio, config['porcentaje_iva'] / 100, descuento)
    valores['nombre_promocion'] = config['nombre_promocion'] if descuento else None
    return valores
