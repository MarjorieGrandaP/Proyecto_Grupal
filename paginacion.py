"""Paginación SQL para consultas de listado ordenadas y parametrizadas."""
from urllib.parse import urlencode
from flask import request


def paginar(cursor, consulta, parametros=(), por_pagina=10):
    # Las consultas y su ORDER BY provienen exclusivamente del código de las rutas.
    filtrada, separador, _ = consulta.rpartition('ORDER BY')
    if not separador:
        raise ValueError('El listado necesita un orden estable.')
    cursor.execute(f'SELECT COUNT(*) AS total FROM ({filtrada}) AS resultados', parametros)
    total = cursor.fetchone()['total']
    paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = min(max(request.args.get('page', 1, type=int), 1), paginas)
    offset = (pagina - 1) * por_pagina
    cursor.execute(consulta + ' LIMIT %s OFFSET %s', tuple(parametros) + (por_pagina, offset))
    registros = cursor.fetchall()
    def enlace(numero):
        filtros = [(k, v) for k, v in request.args.items(multi=True) if k != 'page']
        return request.path + '?' + urlencode(filtros + [('page', numero)])
    numeros = sorted({1, paginas, *range(max(1, pagina - 2), min(paginas, pagina + 2) + 1)})
    return dict(registros=registros, total=total, pagina=pagina, paginas=paginas,
                inicio=offset + 1 if total else 0, fin=offset + len(registros),
                numeros=numeros, enlace=enlace)
