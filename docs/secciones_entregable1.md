# Entregable I: secciones 1.5 a 1.8 (con datos reales)

Texto para reemplazar los marcadores [REVISAR DATOS] del documento. Todas las cifras
salen de `notebooks/01_eda.ipynb` (corte de datos: 2026-10-03) y se pueden verificar en
`reports/cifras_eda.json`. Las figuras están en `reports/figuras/`.

Al final hay una lista de ajustes que los hallazgos obligan a hacer en otras secciones.

---

## 1.5 Composición de la base de datos

La base proviene del sistema operativo de la empresa (MySQL) y corresponde a la sede
Cartagena. Se usaron tres tablas, de las que se extrajeron solo las columnas necesarias
y se reemplazó el número de contrato por un código anónimo:

| Tabla | Contenido | Registros |
|---|---|---|
| Historial de abonos | un registro por contrato y fecha de pago, de 2020-02-09 a 2026-10-03 | 214.745 |
| Foto diaria de motos activas | estado de cada moto por día desde 2024-03-30: fecha de inicio, frecuencia, cuota, justificaciones | 1.260.006 |
| Rentabilidad de activos | episodios cerrados con su desenlace (pago normal, pronto pago o tipo de retiro) | 3.531 |

Antes del análisis se excluyeron los registros fuera de alcance: los de la empresa
RastreoYa (4.475 registros, cuyos identificadores eran correos electrónicos), los
contratos no numéricos y 15 contratos de ventas a Medellín.

El hallazgo central de la exploración es que el número de contrato identifica la
motocicleta y no al cliente: cuando a un cliente se le retira la moto, esta se asigna a
otro con el mismo número. De los 3.081 contratos de la foto diaria, 1.732 tienen dos o
más fechas de inicio. Por eso la unidad de análisis es el **episodio**, es decir, un
cliente con una moto, identificado por el contrato y su fecha de inicio. La base tiene
3.906 contratos y 5.316 episodios de leasing (4.371 semanales y 135 quincenales desde
2024-03-30). La muestra para modelar tiene **2.933 episodios**, cada uno descrito por
24 variables candidatas (19 de comportamiento de pago y 5 del contrato) y la etiqueta.

Las columnas usadas y su significado de negocio son:

| Columna | Fuente | Significado |
|---|---|---|
| `fecha` | abonos | fecha del registro de pago |
| `abono`, `transf` | abonos | pago al canon en efectivo o por transferencia; son lo único que reduce el saldo de la moto |
| `multa` | abonos | multa por atraso cobrada en el pago |
| `repuesto` | abonos | devolución de dinero prestado al cliente (repuestos, trámites, SOAT) |
| `carta`, `cartamotivo` | abonos | abono ficticio que cierra el saldo cuando la moto deja de estar con el cliente, y su motivo |
| `fecha_inicio` | foto diaria | inicio del episodio |
| `tipopago`, `dia_canon` | foto diaria | frecuencia de pago y día de vencimiento de la cuota |
| `cuota`, `no_canon` | foto diaria | valor de la cuota y número de cuotas pactadas |
| `justificacion` | foto diaria | justificación del cliente o marca de gestión vigente ese día |
| `empresa` | ambas | empresa del grupo (MotoHoy o RentaYa) |

Los montos están en miles de pesos. Los faltantes de `cartamotivo` y `justificacion`
son estructurales: solo se llenan cuando hay carta o justificación. Los faltantes reales
encontrados fueron:

- 1.692 tramos con fecha de inicio 0000-00-00, que corresponden a clientes asignados con
  trámites pendientes, todavía sin la moto.
- 18 episodios semanales sin día de vencimiento, para los que no se puede construir el
  calendario de pagos.
- 39.760 registros con el código 999 en los días sin pagar, que el sistema usa cuando
  aún no hay pagos.
- La multa vale 0 en todos los pagos de 2020 a 2022 porque no se registraba en ese
  período; no equivale a "sin multa".
- La columna de fecha de inicio del historial de abonos no se puede usar (siempre
  0000-00-00), así que la fecha de inicio se toma de la foto diaria.

La estrategia de imputación se detalla en la sección 1.8. Las variables categóricas se
codifican así: frecuencia de pago y empresa como binarias, y día de vencimiento (martes,
miércoles, jueves o quincenal) con codificación one-hot. Las numéricas se estandarizan
dentro del flujo de entrenamiento.

## 1.6 Definición de la variable objetivo y prevención de fuga de información

**Fecha esperada de pago.** La base no registra la fecha esperada de cada pago, por lo
que se reconstruye el calendario de cada episodio. Para pago semanal, la cuota vence
cada día de canon a partir de la fecha de inicio; para pago quincenal, cada 14 días. El
48 % de los pagos semanales cae exactamente el día de canon, y la multa aparece desde el
día siguiente: el 96,2 % de los ciclos pagados a tiempo no tiene multa, mientras que el
83,1 % de los pagados con uno o dos días de atraso sí la tiene. Para la empresa hubo pago
si el cliente entregó cualquier dinero ese día, aunque se descuente a multa o repuesto;
el mal comportamiento es no entregar nada. Cada día con pago cubre una cuota del
calendario, o varias si el monto alcanza varias cuotas, y el atraso de una cuota es la
diferencia entre la fecha del pago que la cubrió y su fecha de vencimiento.

**Evento objetivo.** Un episodio está en riesgo grave de mora si alguna cuota que vence
en la ventana de predicción alcanza 14 o más días de atraso, lo que equivale a dos
cuotas semanales sin pagar. También cuenta como evento la cuota que nunca se pagó porque
el episodio se cerró antes de llegar a 14 días. El umbral se eligió con la distribución
real del atraso. Al comparar el máximo atraso de una cuota en la ventana con el
porcentaje de episodios que terminan con la moto retirada, el retiro pasa del 13–16 %
sin atraso relevante al 47 % con 7 a 13 días, y se estabiliza en 66–72 % desde los 14
días. Desde ese punto, más días de atraso ya no aumentan el riesgo.

**Ventanas y fecha de corte.** Para cada episodio, la fecha de corte es t_k = fecha de
inicio + k semanas, con k = 8:

- Ventana de observación: semanas 1 a 8 del episodio. Las variables de entrada solo usan
  información con fecha anterior o igual a t_k. Una cuota vencida antes de t_k y pagada
  después se registra como no pagada, con el atraso acumulado hasta t_k, porque es lo
  que se sabría ese día.
- Ventana de predicción: semanas 9 a 20 (H = 12 semanas).

Se eligió k = 8 porque ofrece ocho cuotas semanales (cuatro quincenales), suficientes
para medir regularidad y variabilidad. Con k = 4 solo habría cuatro cuotas, y con
k = 12 se perderían 960 episodios retirados antes de poder predecir. El horizonte de 12
semanas coincide con el de mejor desempeño reportado en [3] y conserva episodios de 2026.

**Regla de etiquetado.**

- y = 1 si alguna cuota con vencimiento en las semanas 9 a 20 alcanza 14 o más días de
  atraso, o nunca se pagó porque el episodio se cerró.
- y = 0 en cualquier otro caso.

**Población.** Entran los episodios que iniciaron desde el 2024-03-30, fecha en que
empieza la foto diaria. Los episodios anteriores solo aparecen si seguían activos ese
día, lo que sesgaría la muestra hacia clientes que sobrevivieron. Además, el episodio
debe seguir con la moto en t_k y su desenlace debe ser observable antes del corte de
datos (2026-10-03). Se excluyeron 810 episodios anteriores a la cohorte, 225 errores de
asignación (una semana o menos sin ningún pago), 18 sin día de vencimiento, 994
cerrados antes de la semana 8 y 336 recientes sin desenlace observable todavía.

El retiro del vehículo y las marcas de gestión de la empresa no forman parte de la
etiqueta, porque son decisiones discrecionales sin una regla fija. El retiro solo se
usa para validar el umbral. De los 1.070 episodios positivos, 766 lo son por atraso de
14 o más días y 304 por una cuota nunca pagada; de estos, 260 terminaron con la moto
retirada en promedio siete días después de la cuota incumplida, antes de llegar al
umbral.

## 1.7 Variables candidatas confirmadas en la base real

Todas las variables se calculan con las primeras 8 semanas de cada episodio y se
expresan como proporciones o promedios por cuota, para que sean comparables entre
pago semanal y quincenal. La última columna es la correlación de Spearman con la
etiqueta.

| Variable | Fuente | Definición | ρ |
|---|---|---|---|
| Proporción de cuotas atrasadas | abonos + calendario | cuotas con 1 o más días de atraso / cuotas vencidas | 0,43 |
| Proporción de cuotas con atraso de 3 o más días | abonos + calendario | cuotas con 3 o más días de atraso / cuotas vencidas | 0,46 |
| Atraso promedio | abonos + calendario | días de atraso promedio por cuota | 0,47 |
| Atraso máximo | abonos + calendario | mayor atraso de una cuota | 0,48 |
| Cuotas sin pagar en t_k | abonos + calendario | cuotas vencidas sin pago al momento de predecir | 0,47 |
| Pagos por cuota | abonos | días con pago / cuotas vencidas | −0,44 |
| Déficit relativo | abonos + foto diaria | 1 − (abono + transferencia) / (cuota × cuotas vencidas) | 0,44 |
| Variabilidad del abono | abonos | coeficiente de variación del pago al canon | 0,15 |
| Multa acumulada | abonos | suma de multas | 0,23 |
| Proporción de pagos con multa | abonos | pagos con multa / pagos | 0,30 |
| Repuesto acumulado | abonos | dinero devuelto por préstamos | 0,09 |
| Días hasta el primer pago | abonos | días entre el inicio y el primer pago | 0,03 |
| Justificaciones por enfermedad | foto diaria | eventos de enfermedad o calamidad familiar | 0,08 |
| Justificaciones por inmovilización | foto diaria | eventos de moto varada, accidentada, en patio, en taller, en garantía o en Fiscalía | 0,13 |
| Retención temporal | foto diaria | eventos de moto ingresada (la empresa la retiene alrededor de una semana) | 0,15 |
| Cliente problema | foto diaria | eventos de cliente marcado como problema | −0,01 |
| Frecuencia de pago | foto diaria | semanal o quincenal | — |
| Empresa | foto diaria | MotoHoy o RentaYa | — |
| Cuota | foto diaria | valor de la cuota | −0,02 |
| Cuotas pactadas | foto diaria | duración pactada del contrato | 0,00 |
| Día de vencimiento | foto diaria | martes, miércoles, jueves o quincenal | — |

Tres variables del caso no se confirmaron como se habían planteado:

- **Ciudad:** el alcance se limitó a Cartagena, porque cada sede tiene particularidades
  que harían muy complejo combinarlas.
- **Semanas observadas:** es igual a 8 para todos los episodios de la población, así que
  no aporta información; su equivalente por frecuencia es el número de cuotas vencidas.
- **Frecuencia de pago:** en el historial de abonos está vacía en el 70 % de los
  registros, por lo que se toma de la foto diaria.

La retención temporal y el cliente problema son marcas de gestión de la empresa, no
comportamientos del cliente. Se conocen al momento de predecir y no producen fuga de
información, pero el modelo se evaluará con y sin ellas para no aprender solo las
decisiones de cartera. La prevalencia de la etiqueta también varía por empresa (31,1 %
en MotoHoy y 55,6 % en RentaYa), lo que respalda incluir la empresa como variable.

## 1.8 Calidad y preparación de datos

**Consistencia de la multa.** La multa se cobra por escalones según el atraso dentro de
la semana: sin multa al día, 15 mil con uno o dos días de atraso y 25 mil desde tres
días. La correlación de Spearman entre multa y días de atraso por cuota es 0,61. La
relación se debilita desde siete días porque un cliente que va una semana atrasado pero
paga el día de canon muchas veces no recibe multa. La proporción de pagos con multa es
casi redundante con la proporción de cuotas atrasadas (ρ = 0,84), y también son
redundantes los pares atraso máximo y promedio (ρ = 0,97) y pagos por cuota y días con
pago (ρ = 0,99). Estos pares se resolverán con el análisis individual de variables y la
reducción de dimensión del Entregable II.

**Estrategia de imputación.** Ningún faltante se reemplaza por un valor inventado sin
dejar rastro:

| Caso | Causa | Tratamiento |
|---|---|---|
| Días hasta el primer pago y proporción de pagos con multa (126 episodios, 4,3 %) | episodios sin ningún pago en la ventana | no son faltantes al azar (el 84,1 % de esos episodios es positivo): se imputa el valor que corresponde a no pagar (el largo de la ventana; 0) y se agrega un indicador de "sin pagos en la ventana" |
| Variabilidad del abono (136 episodios, 4,6 %) | cero o un pago: la variación no está definida | se imputa 0 junto con el indicador de "sin pagos" o "un solo pago" |
| Día de vencimiento ausente (18 episodios) | no hay calendario posible | se excluyen, porque imputarlo sería inventar la fecha esperada |
| Código 999 en días sin pagar | código del sistema para "sin pagos aún" | se trata como faltante, no como 999 días |
| Multa en 0 entre 2020 y 2022 | la multa no se registraba | queda fuera de la cohorte, que inicia en 2024-03-30 |
| Atraso de cuotas nunca pagadas | episodio cerrado o activo al corte | no se imputa: es un atraso censurado de al menos esos días |

Cualquier imputación que dependa de estadísticos de los datos se ajusta solo con el
conjunto de entrenamiento, dentro de cada pliegue de validación.

**Balance de clases.** La población tiene 1.070 episodios positivos (36,5 %) y 1.863
negativos, una razón de 1 a 1,74. Es un desbalance moderado. Se compararán la
ponderación de clases, el submuestreo de la clase mayoritaria y el sobremuestreo con
SMOTE, aplicados únicamente dentro de los pliegues de entrenamiento para no
contaminar la validación. Los modelos se evaluarán con AUC, G-mean, exactitud
balanceada y el coeficiente de correlación de Matthews (MCC), que no se inflan con la
clase mayoritaria.

---

## Ajustes necesarios en otras secciones del documento

1. **1.1 Contexto:** la empresa opera en Cartagena, Sincelejo y Montería, pero el
   proyecto se limita a la sede Cartagena. Propuesta de frase para agregar al final del
   primer párrafo: "Este proyecto se limita a la sede Cartagena; las demás sedes quedan
   como trabajo futuro."
2. **Título de 1.7:** cambiar "Variables candidatas mencionadas en el caso" por
   "Variables candidatas confirmadas en la base real".
3. **1.9, tabla de etapas:** en la entrada de la Etapa 2, "(+ variables del contrato si
   se confirman)" puede reemplazarse por "+ variables del contrato (frecuencia, empresa,
   cuota, cuotas pactadas y día de vencimiento)", porque ya se confirmaron.
4. **1.9, marcador [PENDIENTE – DATOS]:** queda resuelto. Las variables de la etapa 1 se
   calculan con la misma ventana de 8 semanas y la prueba automática
   `test_variables_de_entrada_no_ven_informacion_posterior_a_k` verifica que no usan
   información posterior al momento de la predicción. Propuesta de reemplazo: "El
   perfil de la etapa 1 se construye con las mismas variables de las primeras 8 semanas,
   por lo que no usa información posterior al momento de la predicción."
5. **Más de 1000 contratos:** la base de Cartagena tiene 3.906 contratos (motos) y 5.316
   episodios de leasing; la muestra para modelar es de 2.933 episodios. Conviene ajustar
   esa cifra en 1.1 y en la Sección 2.C, donde se menciona "algo más de 1.000 contratos".
