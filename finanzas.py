from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

IVA_PREDETERMINADO = "0.15"
CENTAVO = Decimal("0.01")


def validar_tarifa(valor):
    try:
        tarifa = Decimal(str(valor))
    except InvalidOperation:
        raise ValueError("IVA_RATE debe ser una fracción decimal válida.") from None
    if not tarifa.is_finite() or not Decimal("0") <= tarifa <= Decimal("1") or tarifa.as_tuple().exponent < -4:
        raise ValueError("IVA_RATE debe ser una fracción entre 0 y 1, con hasta cuatro decimales.")
    return tarifa


def importes(precio, tarifa, descuento=0):
    subtotal = Decimal(str(precio)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    tarifa = validar_tarifa(tarifa)
    descuento = validar_tarifa(descuento)
    valor_descuento = (subtotal * descuento).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    base = subtotal - valor_descuento
    iva = (base * tarifa).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    total = base + iva
    anticipo = (total / 2).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    return dict(subtotal=subtotal, porcentaje_descuento=descuento,
                valor_descuento=valor_descuento, subtotal_con_descuento=base,
                porcentaje_iva=tarifa, valor_iva=iva, total=total,
                anticipo_requerido=anticipo, saldo_requerido=total-anticipo)
