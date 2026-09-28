# Auditoría previa a Render — PC-Fix

Fecha: 28/09/2026. No se realizó commit, push ni configuración de Render.

- **LISTO PARA COMMIT/PUSH: SÍ.**
- **LISTO PARA RENDER: SÍ**, como código listo para la siguiente etapa de configuración.
- Bloqueadores funcionales detectados para este bloque: ninguno.
- No se ha desplegado ni probado una instancia remota de Render.

## Cambios de este bloque

La biblioteca multimedia usa un modal Bootstrap con pestañas Biblioteca/Subir nueva,
búsqueda local por nombre, miniaturas, metadatos, vista previa y confirmación de selección.
El servicio conserva su imagen si se guarda sin cambiar la selección. El formulario
no se recarga al explorar, subir o borrar imágenes.

Las nuevas imágenes se verifican y decodifican con Pillow (JPG/JPEG, PNG, WEBP;
2 MB, hasta 20 megapíxeles, sin animación) y se almacenan como BYTEA en PostgreSQL.
SHA-256 y un índice único evitan duplicados. Se sirven desde memoria con MIME,
ETag, caché y `nosniff`. Las cuatro imágenes originales siguen siendo estáticas.
La biblioteca y sus mutaciones requieren administrador; POST requiere CSRF.
Las imágenes son recursos públicos, igual que los recursos originales de `static/img`.
No se eliminan imágenes referenciadas, incluidos servicios pausados/archivados.
La asignación bloquea la fila de imagen para evitar carreras con la eliminación.

Bootstrap opcional del primer administrador mediante las tres variables vacías de
`.env.example`: `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`. Usa hash, no
imprime contraseña, no eleva clientes ni reemplaza credenciales existentes y se
serializa mediante bloqueo transaccional. No crea cuentas predeterminadas.

## Migración

`sql/migracion_biblioteca_multimedia.sql`, aplicada localmente e incorporada en
`sql/esquema.sql`: tabla `imagenes_servicio`, índice único SHA-256, columna
`servicios.id_imagen` y FK `ON DELETE SET NULL` idempotente.
La aplicación bloquea el borrado de toda imagen en uso; no utiliza la FK para
permitir ese borrado desde la interfaz. No migra ni borra archivos estáticos.

## Verificaciones

- **100 pruebas Python/PostgreSQL aprobadas**, conservando las anteriores y adaptando únicamente las expectativas del flujo técnico e IVA sustituidas por el nuevo requisito.
- **17 comprobaciones JavaScript aprobadas**, ejecutando `biblioteca.js` con DOM
  simulado; prueba reproducible en `tests/biblioteca_frontend.js`.
- Formatos reales JPG/JPEG/PNG/WEBP, archivos falsos/truncados/formato incorrecto,
  más de 2 MB, deduplicación, reutilización, conservación/edición, pausa/archivo,
  borrado bloqueado/en desuso, imágenes estáticas, permisos y CSRF verificados.
- Todas las plantillas Jinja cargadas; Python compilado con `compileall`.
- Esquema PostgreSQL completo ejecutado tres veces en un esquema aislado vacío;
  semillas y administrador sin duplicados. El esquema de prueba se revierte.
- `pip check`: sin dependencias incompatibles. Pillow declarado explícitamente;
  `requirements.txt` normalizado de UTF-16 a UTF-8. Gunicorn ya estaba declarado.
- `DATABASE_URL` ya soportado; `.env` ignorado y no versionado. La revisión de
  código no detectó secretos hardcodeados de producción; la clave literal detectada
  corresponde exclusivamente al entorno aislado de pruebas.
- Arranque HTTP real en `localhost`, puerto libre: `/login` y el JavaScript
  multimedia respondieron 200. La aplicación conserva `host="localhost"` local.
- `git diff --check`: correcto.
- Las imágenes y esquemas generados por las pruebas no quedan guardados.

Límite de comprobación visual: Edge headless falló al iniciar su proceso gráfico
en este entorno. Se verificaron render Jinja, rutas, datos y controlador JavaScript;
no se afirma una revisión visual en navegador ni una ejecución de Gunicorn en
Windows (su destino de ejecución es Linux).

## Funciones discutidas

| Función | Estado | Evidencia / alcance |
|---|---|---|
| Anticipo del 50 % | IMPLEMENTADO | Cotización fija con IVA, comprobantes privados, confirmación administrativa, bloqueo de reparación sin anticipo y de entrega sin pago completo. |
| Términos y condiciones | IMPLEMENTADO | Página y aceptación persistente al solicitar. |
| Garantía de 3 meses | IMPLEMENTADO | Fecha real de entrega, vencimiento por meses y exclusiones; no inventa fechas históricas desconocidas. |
| Expediente técnico interno | IMPLEMENTADO | Datos técnicos auditados y notas privadas por defecto, con publicación explícita opcional. |
| Modal Gestionar pedido | IMPLEMENTADO | Secciones administrativas y controles fuera de la tabla. |
| Motivos de cancelación | IMPLEMENTADO | Validación por rol, Otro con detalle, plazo cliente y bloqueo con factura. |
| Línea de tiempo | IMPLEMENTADO | Historial persistente, vista interna completa y seguimiento cliente filtrado. |
| Snapshots históricos de factura | IMPLEMENTADO | Servicio, equipo, modelo y total conservados; PDF comercial separado del expediente. |

Los estados técnicos y de pago están separados. El estado técnico antiguo permanece en el historial; los pedidos que lo utilizaban se migran a En revisión con trazabilidad. No existen excepciones nuevas para entregar sin pago completo.

## Archivos de este bloque

Modificados: `.env.example`, `README.md`, `app.py`, `forms/producto_form.py`,
`requirements.txt`, `sql/esquema.sql`, `templates/formulario_producto.html`,
`templates/servicios.html`.

Nuevos: `AUDITORIA_PRE_RENDER.md`, `biblioteca.py`, `conexion/bootstrap_admin.py`,
`forms/imagen_servicio_form.py`, `sql/migracion_biblioteca_multimedia.sql`,
`static/js/biblioteca.js`, `templates/components/biblioteca_multimedia.html`,
`tests/test_biblioteca.py`, `tests/test_bootstrap_admin.py`, `tests/biblioteca_frontend.js`.


## Ampliación: duraciones, pagos e IVA

- Duración mediante cantidad y unidad (Minutos/Horas/Días/Semanas/Variable),
  conservando `servicios.duracion` para compatibilidad. La migración interpreta
  los textos reconocidos y no borra valores históricos no reconocidos.
- Flujo técnico: Solicitado → En revisión → En reparación → Listo → Entregado;
  Cancelado terminal. El pago se resume separadamente a partir de comprobantes
  persistentes y decisiones administrativas.
- IVA central en `IVA_RATE`, con valor de proyecto por defecto en `finanzas.py`.
  Los importes se calculan con Decimal y redondeo a centavos. El saldo absorbe
  el centavo residual cuando el total no permite dos mitades exactas.
- Al solicitar el anticipo se congelan subtotal, tarifa, IVA, total y cuotas,
  junto con el administrador y fecha de solicitud. El cambio posterior de precio
  o tarifa no modifica el pedido cotizado ni una factura emitida.
- JPG/PNG/PDF de hasta 5 MB se validan en backend y se almacenan en PostgreSQL.
  PDFs analizados con pypdf, sin contraseña ni acciones, hasta 20 páginas.
  Comprobantes privados: solo propietario/admin, sin caché compartida.
- El cliente no aporta importes efectivos ni puede confirmar. Confirmación/rechazo
  registran administrador, fecha, monto y auditoría sin copiar BYTEA al registro.
  Rechazo exige motivo; la nueva presentación conserva el comprobante anterior.
- Sin anticipo confirmado no se permite reparación. Sin pago completo no se
  permite entrega. Las confirmaciones históricas sin importes verificables se
  señalan para conciliación; no se inventan pagos ni comprobantes.
- Factura comercial: subtotal, IVA aplicado y total, preservando los snapshots
  de servicio/equipo/modelo. Las facturas anteriores sin desglose mantienen su
  total y muestran IVA histórico no desglosado, sin asignarles una tarifa inventada.
- Migración `sql/migracion_pagos_iva_duracion.sql` aplicada y repetible, integrada
  también en `sql/esquema.sql`. Las pruebas de esquema vacío siguen pasando.
- `PAYMENT_BANK`, `PAYMENT_ACCOUNT_TYPE`, `PAYMENT_ACCOUNT_NUMBER` y
  `PAYMENT_ACCOUNT_HOLDER` se documentan vacías en `.env.example`. Deben
  configurarse con datos reales antes de recibir transferencias en producción.
  La interfaz informa si faltan; no muestra información bancaria sin solicitud.
- Sin cambios de configuración de Render, sin commit ni push.

Archivos añadidos en esta ampliación: `finanzas.py`, `pagos.py`,
`forms/pagos_form.py`, `sql/migracion_pagos_iva_duracion.sql`,
`templates/pagos_pedido.html`, `templates/components/pagos_pedido.html`,
`tests/pagos_utils.py`, `tests/test_pagos_iva.py`.

Archivos modificados en esta ampliación: `app.py`, `.env.example`,
`requirements.txt`, `README.md`, `AUDITORIA_PRE_RENDER.md`, `sql/esquema.sql`,
`forms/producto_form.py`, `forms/pedido_estado_form.py`, `forms/cancelacion_form.py`,
`static/js/pedidos.js`, `templates/formulario_producto.html`,
`templates/servicios.html`, `templates/mis_pedidos.html`, `templates/condiciones.html`,
`templates/components/gestionar_pedido.html`, `templates/components/linea_tiempo.html`,
`templates/components/modales_pedidos.html`, `tests/test_seguimiento.py`,
`tests/test_gestion_modal.py`, `tests/test_cancelacion_anticipo.py`,
`tests/test_expediente_servicio.py`, `tests/test_facturacion_pedidos.py`.
