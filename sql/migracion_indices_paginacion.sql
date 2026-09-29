-- Índices de acceso para listados ordenados y registros propios del cliente.
CREATE INDEX IF NOT EXISTS pedidos_usuario_fecha_idx ON pedidos(id_usuario, fecha_solicitud DESC, id_pedido DESC);
CREATE INDEX IF NOT EXISTS pedidos_fecha_idx ON pedidos(fecha_solicitud DESC, id_pedido DESC);
CREATE INDEX IF NOT EXISTS facturas_usuario_fecha_idx ON facturas(id_usuario, fecha DESC, id_factura DESC);
CREATE INDEX IF NOT EXISTS facturas_fecha_idx ON facturas(fecha DESC, id_factura DESC);
CREATE INDEX IF NOT EXISTS auditoria_fecha_idx ON auditoria(fecha_hora DESC, id_auditoria DESC);
CREATE INDEX IF NOT EXISTS servicios_listado_nombre_idx ON servicios(nombre, id_servicio) WHERE eliminado = FALSE;
CREATE INDEX IF NOT EXISTS clientes_listado_nombre_idx ON clientes(nombre, id_cliente) WHERE eliminado = FALSE;
CREATE INDEX IF NOT EXISTS proveedores_empresa_idx ON proveedores(empresa, id_proveedor);
