# Reglas de negocio y de limpieza confirmadas

Reglas confirmadas con la empresa (Juan Esteban Cardozo, 2026-10-04) durante la
exploración de la base `db_packgps`. Cada regla indica de qué tabla sale y por qué
se aplica. El notebook de EDA las implementa en este mismo orden.

## Alcance

Solo **Cartagena** (decidido 2026-10-04). Las tablas de `db_packgps` corresponden a esa
sede, y cada sede tiene particularidades que harían muy complejo mezclarlas con el alcance
del curso. Sincelejo y Montería quedan como trabajo futuro, reutilizando estas reglas.
Como consecuencia, "ciudad" no es una variable del modelo.

## Fuentes

| Tabla | Grano | Uso |
|---|---|---|
| `np_his_abonos` | un registro por contrato y fecha de pago | historial de pagos (abono, multa, carta) |
| `motos_app_hist` | una foto diaria por moto activa (desde 2024-03-30) | fecha de inicio, frecuencia de pago, días sin pagar |
| `rentabilidad_activos`, `rentabilidad_activos_cartas` | un registro por episodio cerrado | fecha de inicio y desenlace de episodios cerrados |

## Unidad de análisis: el episodio, no el contrato

- El número de `CONTRATO` identifica la moto y **se reasigna** a otro cliente cuando la
  moto se retira. Un mismo contrato puede tener varios clientes en el tiempo.
- La unidad de análisis es el **episodio**: un cliente con una moto, identificado por
  (`contrato`, `fecha_inicio`).
- Los episodios se construyen desde la secuencia diaria de `motos_app_hist`, como
  tramos continuos con la misma `fecha_inicio` y `tipopago`. Agrupar solo por
  (`contrato`, `fecha_inicio`) falla porque el sistema reusa la `fecha_inicio` de un
  período diario anterior cuando la moto vuelve a arriendo.

## Exclusiones completas

| Regla | Motivo |
|---|---|
| `empresa = 'RASTREOYA'` | no es leasing de motos; sus identificadores son correos |
| `CONTRATO` con correo electrónico o no numérico | no es un contrato de leasing; además es dato personal |
| Contratos con `CARTAMOTIVO = 'CARTA MEDELLIN'` | ventas hechas a Medellín, fuera del alcance |
| Episodios con `tipopago = 'DIARIO'` | período de prueba (~1 mes) sin contrato de propiedad; si el cliente responde pasa a semanal o quincenal con una `fecha_inicio` nueva |
| Tramos con `fecha_inicio = 0000-00-00` | cliente asignado con trámites pendientes; la moto aún no está en sus manos |
| Episodios con menos de k semanas observadas | errores de asignación; no hay ventana de observación completa |

## Cartas (`np_his_abonos.CARTA = 'SI'`)

Una carta es un abono **ficticio** que cierra el saldo cuando la moto deja de estar con
el cliente. No es un pago y no entra al cálculo de abonos, salvo `PRONTO PAGO`.

| `CARTAMOTIVO` | ¿Pago real? | ¿Retiro por mal comportamiento? |
|---|---|---|
| CARTA REGRESO DIARIO | no | sí |
| CARTA ADMINISTRACION | no | sí |
| CARTA REALQUILER | no | sí |
| CARTA PERDIDA (el saldo se perdió, no se volvió a contactar al cliente) | no | sí |
| CARTA CORRECCION (cambio en la negociación) | no | no |
| PRONTO PAGO (abono real con descuento por pagar antes) | **sí** | no |
| vacío (solo 2021-2023) | no | causa desconocida: no se cuenta como retiro ni como desenlace bueno; esos episodios se excluyen del análisis de validación (rentabilidad no tiene su motivo) |

- El retiro es **discrecional**: se usa como variable de validación posterior, nunca
  como etiqueta del modelo supervisado.
- La fecha del retiro es la de la primera carta de retiro del episodio.

## Justificaciones y marcas de gestión (`motos_app_hist.JUSTIFICACION`)

| Grupo | Valores | Uso |
|---|---|---|
| Enfermedad o calamidad | Enfermo, Familiar muerto | justificación del cliente |
| Inmovilización | Varado, Acidentado, Patio, PATIOS, Fiscalia, EN TALLER, Garantía | justificación del cliente |
| Retención temporal | MOTO INGRESADA | marca de gestión de la empresa |
| Cliente problema | Problema | marca de gestión de la empresa |
| No son justificaciones | Multa, Nuevo, Prestamo, Adelantado, Por refinanciar, Administracion, Paz y Salvo, SEMANAL, Quincenal | estados o anotaciones; no se usan |

- **MOTO INGRESADA:** la empresa retiene la moto alrededor de una semana para ver si el
  cliente se pone al día; si no cumple, la moto no se devuelve y se retira
  definitivamente. En los datos, el 69,7 % de esos episodios termina en retiro
  definitivo, frente al 33,3 % de los que nunca tuvieron la moto ingresada.
- **Problema:** cliente al que todavía no se le hace carta, pero cuya moto no se puede
  recuperar (por ejemplo, se encierra con la moto y no deja acercarse a los cobradores).
  Si con el tiempo no hay forma de recuperar la moto o el saldo, se le hace carta.
- Las dos marcas de gestión son decisiones discrecionales de la empresa: se usan como
  variables propias (¿ocurrió en las primeras k semanas?), nunca en la etiqueta, y el
  modelo se evalúa con y sin ellas para no aprender solo las decisiones de cartera.
- La foto diaria repite la justificación mientras está vigente: un **evento** es un
  tramo de días consecutivos con el mismo valor.

## Componentes del pago (`np_his_abonos`)

Pago total del día = `ABONO` + `TRANSF` + `MULTA` + `REPUESTO`. Solo una parte reduce
el saldo adeudado de la moto:

| Columna | Qué es | ¿Reduce el saldo de la moto? |
|---|---|---|
| `ABONO` | pago al canon (efectivo o digitado) | sí |
| `TRANSF` | pago al canon por transferencia (poco común) | sí |
| `MULTA` | multa por atraso | no |
| `REPUESTO` | devolución de dinero prestado al cliente (repuestos, inicio de trámites, renovación del SOAT) | no |

- **Hubo pago = `ABONO` + `TRANSF` + `MULTA` + `REPUESTO` > 0.** Para la empresa, si el
  cliente entrega cualquier dinero hay gestión y en ese ciclo se comportó bien, aunque el
  sistema lo descuente a multa o repuesto. El mal comportamiento es no entregar nada.
- El no pago **no aparece como una fila en cero** (solo 42 de 212.604 registros de pago
  tienen total 0): aparece como **ausencia de registro**. La mora se mide contra el
  calendario esperado del episodio (fecha de inicio + frecuencia + día de canon).
- **Pago al canon = `ABONO` + `TRANSF`.** Se compara con la cuota para medir el déficit,
  como variable secundaria, no como definición de mora.
- `REPUESTO` indica que el cliente necesitó un préstamo, y puede usarse como variable
  aparte.

## Valores que no son datos

| Columna | Valor | Tratamiento |
|---|---|---|
| `motos_app_hist.diassinpagar` | 999 | primer día del episodio, sin pagos aún: faltante, no 999 días |
| `np_his_abonos.MULTA` | 0 en 2020-2022 | la multa no se registraba esos años: no equivale a "sin multa" |
| `np_his_abonos.FECHA_INI` | siempre 0000-00-00 | columna inutilizable; el inicio sale de `motos_app_hist` |

## Columnas descartadas como variables

| Columna | Qué es | Por qué no se usa |
|---|---|---|
| `ruta` | punto donde el cliente paga | no aporta al comportamiento de pago; además incluye estados del desenlace (CANCELADA, ADMINISTRACION, REALQUILADA, ROBADA), que producirían fuga de información |
| `cobro` (JP, RC y sus subdivisiones) | inversionista propietario de la moto | describe al dueño de la moto, no al cliente |
| `RUTA_PUNTO`, `DEBE_PAGAR`, `tipo_pago` | punto o barrio de pago | mismo motivo que `ruta` |
| `PRESTAMO` | duplicado de `REPUESTO` por un error de diseño de la base | en 2026 coincide con `REPUESTO` en el 100 % de las filas (en 2024-2025 se llenaba de forma irregular); nunca es el único dinero del día, así que excluirla no cambia la regla de "hubo pago" |

## Unidades

- Montos en **miles de pesos** (una cuota de 175,5 son $175.500).
