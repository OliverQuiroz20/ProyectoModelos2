# Resumen del estado del arte (verificado contra el texto cuando fue posible)

Fecha: 2026-10-26. PDFs en esta carpeta: `alaraj2021.pdf` (version publicada, Springer open access, 27 pags.) y `bakoben_arxiv1706.07466.pdf` (preprint arXiv v1 de 2017, NO la version final de JORS 2020; las cifras pueden diferir de la publicada). Yuan 2022 y Kennedy 2013 NO se pudieron descargar: solo se tiene el resumen abierto, obtenido via buscador (no verificado en el texto completo).

| Trabajo | Fuente leida | Verificacion |
|---|---|---|
| [1] Yuan 2022 | solo abstract (IDEAS/RePEc, via busqueda) | parcial, articulo de pago |
| [2] Bakoben 2020 | preprint arXiv 1706.07466 (texto completo) | completa para el preprint |
| [3] Kennedy 2013 | solo abstract (registro ARROW, via busqueda); el PDF de arrow.tudublin.ie devolvio una pagina HTML de proteccion anti-bots y no se intento eludirla | parcial |
| [4] Ala'raj 2021 | texto completo publicado | completa |

Paginas: para Ala'raj son las de la revista (J Big Data 8:69). Para Bakoben son las del PDF arXiv (9 pags.), aproximadas.

---

## [1] Yuan, Chi, Zhou, Yin (2022), Research in Int. Business and Finance 59:101536

Solo abstract (no leido el texto completo).
- Problema/datos: prediccion de default de empresas chinas listadas, con atributos de 1 a 5 anios antes del estado y default posterior; alerta hasta 5 anios antes. Tamano de muestra y tasa de positivos: NO verificado.
- Metodo: dos etapas, k-means para dividir la muestra y luego SVDD (support vector domain description) para predecir default.
- Resultado en el abstract: el modelo de dos etapas supera a los de una sola etapa (solo k-means o solo SVDD); AUC superior a 0,85 para prediccion a 5 anios. Variables influyentes: utilidades retenidas/activos totales, gastos financieros/ingresos brutos, tipo de opinion de auditoria.
- Validacion, otras metricas, baselines numericos, limitaciones, paginas/tablas: NO verificado.
- Similitud/diferencia con nuestro proyecto: comparte la idea de clustering previo a un clasificador, pero es riesgo corporativo (estados financieros anuales, horizonte de anios) y no comportamiento de pago de personas en leasing. Ademas reporta que el clustering mejora, mientras que en nuestro caso los 4 perfiles de pago no mejoran el clasificador (AUC ~0,80 val., 0,76-0,79 prueba). No sabemos si su validacion es temporal ni si evalua generalizacion a otras ciudades.

## [2] Bakoben, Bellotti, Adams (2020), JORS 71(5):775-783 (leido: preprint arXiv 2017)

- Problema/datos (p.2): tarjetas de credito de un banco britanico anonimo; 494 cuentas, hasta 37 meses de comportamiento mensual. Default = 3 pagos perdidos consecutivos; variable respuesta "alguna vez en default" (p.3). Tasa de positivos en entrenamiento (n=296, Tabla 3, p.7): 19+8+51 = 78 defaults de 296 (aprox. 26%; calculado por mi sumando la tabla, no lo dice el texto).
- Metodo: cada cuenta (pagos y tasa de utilizacion) se modela con un VAR(1) bivariado (4 coeficientes); k-medoids con k=3 sobre una disimilitud basada en el solapamiento de elipsoides de confianza de los coeficientes (incorpora incertidumbre) vs. distancia euclidea. Luego regresion logistica con la asignacion de cluster como unico predictor; baseline: regresion logistica con medias agregadas (pago, utilizacion).
- Validacion (p.2, p.5): 60% entrenamiento (296 cuentas) / 40% prueba (198), division por cuentas, no temporal. Para "forecasting" (p.3): clustering con los primeros 2/3 del perfil de cada cuenta y default medido en el ultimo 1/3 (Fig. 1).
- Tamanos de cluster (Tabla 1, p.4): elipsoide 244 (50%), 115 (23%), 135 (27%); euclidea 307 (62%), 144 (29%), 43 (9%).
- Metricas en prueba, prediccion (Tabla 4, p.7). Orden: elipsoide / euclidea / agregado / agregado+elipsoide / agregado+euclidea
  - H-measure: 0,3748 / 0,1416 / 0,0573 / 0,3962 / 0,1818
  - KS: 0,5443 / 0,3405 / 0,1569 / 0,5543 / 0,3679
  - Gini: 0,5273 / 0,3563 / 0,0620 / 0,5110 / 0,3527
  - AUC: 0,7637 / 0,6781 / 0,5310 / 0,7555 / 0,6764 (texto p.5: AUC 0,7637 s.e. 0,0397; agregado 0,5310 s.e. 0,0450)
- Metricas en prueba, pronostico (Tabla 7, p.8), mismo orden
  - H-measure: 0,1825 / 0,0810 / 0,0276 / 0,1744 / 0,1130
  - KS: 0,3382 / 0,2237 / 0,1219 / 0,3230 / 0,2799
  - Gini: 0,4502 / 0,2246 / 0,0709 / 0,4094 / 0,2172
  - AUC: 0,7251 (s.e. 6e-4) / 0,6123 (s.e. 4e-4) / 0,5355 (s.e. 7e-4) / 0,7047 / 0,6086
- Otros: coeficientes logisticos de los clusters en Tablas 2 y 6; el cluster C3 elipsoide agrupa a los de mayor riesgo (51 de 80 en default en entrenamiento, Tabla 3). No hay prueba estadistica entre modelos; solo z de los coeficientes.
- Limitaciones que mencionan: k=3 elegido a criterio, optimizar k fuera de alcance (p.4); clusters poco separados en PCA (p.4); coeficientes con errores estandar enormes por pocas observaciones de la clase default (p.5-7); la extension con ventanas de tiempo requiere perfiles mas largos (p.8). La muestra pequena (494) es observacion mia.
- Similitud/diferencia con nuestro proyecto: es el antecedente mas cercano: clustering de comportamiento de pago + clasificador, y tambien una ventana de observacion seguida de una de pronostico (2/3 y 1/3, vs. nuestras 8 y 12 semanas). Difiere en que el clustering ES el unico predictor y mejora mucho frente a medias agregadas (AUC 0,53 a 0,76), con 494 cuentas y particion aleatoria 60/40; nosotros usamos validacion temporal, mas datos y un clasificador completo, donde los 4 perfiles no aportan. Su AUC de pronostico (0,7251) es comparable a nuestro 0,76-0,79 en prueba, pero no probaron generalizacion entre ciudades.

## [3] Kennedy, Mac Namee, Delany, O'Sullivan, Watson (2013), Expert Systems with Applications 40(4):1372-1380

Solo abstract (via busqueda; texto completo no leido).
- Problema/datos: scoring de comportamiento; siete anios de datos del mercado irlandes; estudia el efecto de variar el periodo de desempeno y el periodo de resultado (outcome window) en la prediccion. Tamano y tasa de positivos: NO verificado.
- Hallazgos del abstract: un periodo de desempeno de 12 meses da la tarea de prediccion mas facil entre los probados; el rendimiento de la regresion logistica cae de forma notable cuando la ventana de resultado supera 6 meses; definir default como "en default en cualquier momento del periodo de resultado" da un problema de clasificacion mas facil que mirar solo el final del periodo.
- Clasificadores, metricas con cifras, validacion, limitaciones y paginas: NO verificado.
- Similitud/diferencia con nuestro proyecto: antecedente directo para justificar las ventanas (8 semanas de observacion, 12 de resultado) y la definicion de "riesgo grave de mora a 14 dias en cualquier momento de la ventana", que segun su abstract facilita la clasificacion. Difiere en que es credito de consumo irlandes con ventanas en meses, y no evalua clustering ni generalizacion entre ciudades.

## [4] Ala'raj, Abbod, Majdalawieh (2021), J Big Data 8:69 (texto completo leido)

- Problema/datos (p.17-18): probabilidad de pago perdido el mes siguiente (y consecutivos) en tarjeta de credito; dataset publico de Taiwan, 30.000 registros, 6.636 en default (22%), 23 variables explicativas, sin faltantes. Usa los 6 meses previos (p.19).
- Metodo: LSTM bidireccional; benchmarks: Gradient Boosting (GB), red neuronal bagged (BNN), SVM, Random Forest (RF), regresion logistica (LOGR); los benchmarks reciben los datos temporales aplanados (p.21). Sin clustering.
- Validacion (p.18): validacion cruzada de 5 particiones, division aleatoria de clientes (no temporal). Prueba de McNemar con alfa 0,05.
- Metricas del LSTM, todos los clientes (Tabla 2, p.19): exactitud 82,4%; sensibilidad 37,51%; especificidad 95,15%; AUC 78,47%; Brier 13,28%; KS 0,43; H-measure 0,30. Subgrupos (AUC): pago perdido en ult. 2 meses 78,37%; ult. mes 78,23%; dos consecutivos 79,81%; tres o mas consecutivos 76,86% (sensib. 90%, especif. 38,83%, Brier 17,62%, KS 0,46, H 0,27).
- Comparacion (Tabla 3, p.21), exactitud / sensib. / especif. / exactitud balanceada / AUC / Brier (todo en %) / KS / H:
  - GB: 82,07 / 36,47 / 95,02 / 65,75 / 78,03 / 13,43 / 0,43 / 0,29
  - BNN: 81,78 / 37,07 / 94,48 / 65,77 / 77,53 / 13,58 / 0,42 / 0,28
  - SVM: 81,46 / 28,56 / 96,49 / 62,52 / 69,57 / 14,33 / 0,37 / 0,23
  - RF: 80,18 / 17,01 / 98,12 / 57,57 / 76,54 / 14,38 / 0,41 / 0,27
  - LOGR: 80,88 / 22,56 / 97,44 / 60,00 / 71,82 / 14,55 / 0,37 / 0,24
  - LSTM bidireccional: 82,4 / 37,51 / 95,15 / 66,33 / 78,47 / 13,28 / 0,43 / 0,30
- McNemar LSTM vs otros (Tabla 4, p.23), estadistico / p: GB 17 / 3,62e-5; BNN 42 / 8,01e-11; SVM 76 / 2,77e-18; RF 211 / 1,02e-47; LOGR 128 / 1,15e-29. Desviaciones estandar entre folds (Tabla 5, p.24): exactitud 0,37%, AUC 0,41% para el LSTM; tiempos de entrenamiento de 0,2 a 306 s. Calibracion: curvas de 10 bins (Figs. 8 y 10); LSTM y BNN bien calibrados.
- Limitaciones que mencionan: exactitud menor que en un dataset transaccional por perdida de informacion en el preprocesado (p.19); rendimiento mucho menor con 3+ pagos perdidos consecutivos (p.19); futuro: otros datasets y extension a credito de consumo (p.25). El texto conserva referencias a un "transactional dataset" que no pude verificar.
- Similitud/diferencia con nuestro proyecto: misma pregunta (predecir incumplimiento desde la historia reciente de pagos, 6 meses vs. nuestras 8 semanas); su AUC de 0,78 es del mismo orden que nuestro 0,76-0,79 en prueba, y los modelos clasicos quedan a pocas decimas de la red profunda (GB 78,03 vs 78,47), coherente con usar clasificadores sencillos. Difiere en que usa validacion cruzada aleatoria (nosotros temporal), horizonte de un mes, tarjetas en Taiwan, sin clustering ni prueba de transferencia entre ciudades.

---
Notas: las comparaciones con [1] y [3] deben limitarse a lo del abstract hasta obtener el PDF (biblioteca UdeA o VPN institucional). Citar [2] como preprint o verificar las cifras contra la version publicada de JORS (accepted manuscript en Imperial Spiral).

---
## Actualizacion 2026-10-26: Bakoben verificado con la version aceptada (JORS 2020)

Fuente: `bakoben_jors2019_accepted.pdf` (accepted manuscript, Imperial Spiral; texto en `bakoben_jors2019_accepted.txt`).
Las cifras del preprint de arXiv coinciden con las de la version aceptada. Datos verificados en el texto:

- 494 cuentas de tarjeta de credito; default = 3 o mas pagos consecutivos perdidos; 27,33 % default (135) y 72,67 % no default (359). Los no-default estaban sub-muestreados por el proveedor.
- Validacion: 60 % entrenamiento / 40 % prueba (198 cuentas), promedio de 1000 particiones aleatorias.
- Prediccion (Tabla 5): AUC 0,7637 (dell), 0,6781 (euclidea), 0,5310 (medias agregadas); H-measure 0,3748 / 0,1416 / 0,0573; KS 0,5443 / 0,3405 / 0,1569; Gini 0,5273 / 0,3563 / 0,0620. Desv. est. AUC dell: 0,0397.
- Pronostico (Tabla 9): AUC 0,7251 / 0,6123 / 0,5355; H-measure 0,1825 / 0,0810 / 0,0276; KS 0,3382 / 0,2237 / 0,1219.

Pendientes de verificar: [1] Yuan 2022 y [3] Kennedy 2013 (solo abstract; texto completo requiere acceso institucional).
