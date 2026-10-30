# Modelo predictivo de riesgo de mora en contratos de leasing de motocicletas

Proyecto de aula de **Modelos y Simulación de Sistemas II** (Universidad de Antioquia),
Grupo 14: Juan Esteban Cardozo Rivera, Maria Carolina Cardona Calderon y Oliver Andres
Quiroz Mora.

El sistema tiene dos etapas encadenadas: (1) agrupar los contratos según su
comportamiento de pago en las primeras semanas (aprendizaje no supervisado) y (2)
estimar la probabilidad de que un contrato termine en riesgo grave de mora usando esas
variables y el perfil de la etapa 1 (aprendizaje supervisado).

Este repositorio contiene los dos entregables:

- **Entregable I:** análisis exploratorio de la base real, definición de la variable
  objetivo y construcción de las variables candidatas.
- **Entregable II:** modelo en dos etapas (perfiles de pago y clasificación) con
  validación temporal sin fuga de información, rejilla de ventanas K/H/X, selección de
  variables y explicabilidad (SHAP), búsqueda de un mejor modelo y validación externa en
  Sincelejo y Montería. Además, un ranking de gestión de las motos activas.

## Cuaderno único en Colab (`Modelo_Riesgo_Mora_Colab.ipynb`)

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1I_msn1aacWz-Sf6tPA5YsytYaKnJZKSa)

Enlace directo: <https://colab.research.google.com/drive/1I_msn1aacWz-Sf6tPA5YsytYaKnJZKSa>

El enlace abre la versión del notebook que está en la carpeta compartida de Drive, junto
con los datos. Solo funciona para las cuentas con acceso a esa carpeta, porque los datos
son confidenciales; para ejecutarlo se usa Entorno de ejecución → Ejecutar todas.

## Reportes

- Entregable I: [`informe/Primera_Entrega_ModelosII.pdf`](informe/Primera_Entrega_ModelosII.pdf)
  (fuente en `informe/entregable1.tex`).
- Entregable II: [`informe/Segunda_Entrega_ModelosII.pdf`](informe/Segunda_Entrega_ModelosII.pdf)
  (fuente en `informe/entregable2.tex`, plantilla IEEEtran; figuras en `informe/figuras/`).

## Arquitectura

Diagrama del flujo completo, de la base de datos al ranking de gestión (generado con
archify): [`.archify/architecture-modelos2-20261029-210000/modelos2-architecture.html`](.archify/architecture-modelos2-20261029-210000/modelos2-architecture.html).
Se descarga y se abre en el navegador.

## Estructura

```
informe/                      reportes en PDF, fuentes LaTeX y figuras (Entregables I y II)
notebooks/01_eda.ipynb        Entregable I: análisis exploratorio
notebooks/02_clustering.ipynb Etapa 1: perfiles de pago
notebooks/03_clasificacion.ipynb  Etapa 2: clasificadores, validación temporal y rejilla K/H/X
notebooks/04_seleccion_explicabilidad.ipynb  filtro, información mutua, Lasso, PCA, UMAP y SHAP
notebooks/05_mejora_modelo.ipynb  intentos de mejora y validación externa
notebooks/Modelo_Riesgo_Mora_Colab.ipynb  cuaderno único (partes 1 a 5) para Colab
src/ciclos.py                 episodios y calendario de pagos esperado
src/variables.py              población, etiqueta y variables con corte temporal
src/particion.py              partición temporal, purga y pliegues de ventana expansiva
src/modelado.py               perfiles de pago (etapa 1)
src/clasificacion.py          preprocesamiento, modelos y métricas (etapa 2)
src/extraer.py                extracción de la copia anonimizada (requiere acceso a la empresa)
src/conexion.py               conexión de solo lectura a la base
experimentos/                 experimentos reproducibles, validación en otras sedes y ranking de gestión
tests/                        pruebas del calendario, la etiqueta, la clasificación y la ausencia de fuga
docs/reglas_de_negocio.md     reglas de negocio y de limpieza confirmadas con la empresa
reports/                      cifras, diccionario de datos, variables y figuras generadas
data/                         datos (no se versionan, ver abajo)
```

## Ranking de gestión (uso real del modelo)

`experimentos/gestion_ranking.py` ordena las motos activas con 8 a 20 semanas por riesgo
de mora. Quedan fuera de la gestión las motos en realquiler, oficina, fiscalía, triage,
geocerca y varadas. La lista contiene contratos reales: se genera en `data/gestion/`,
que no se versiona, y no se comparte.

## Datos

Los datos son **confidenciales de la empresa** y no están en el repositorio. El notebook
espera la copia anonimizada en `data/anon/`:

| Archivo | Contenido |
|---|---|
| `data/anon/abonos.csv.gz` | historial de pagos (un registro por contrato y fecha) |
| `data/anon/motos_diario.csv.gz` | foto diaria de cada moto activa desde 2024-03-30 |
| `data/anon/rentabilidad.csv.gz` | episodios cerrados con su desenlace |
| `data/anon/dataset_modelo.csv.gz` | dataset de episodios con variables y etiqueta (notebook 02) |

La copia no tiene nombres, teléfonos, placas, titulares, barrios ni evidencias, y el
número de contrato se reemplazó por un código (`C00001`...). El equipo la comparte por
un canal privado. Para reproducir el análisis, se descargan los archivos y se
colocan en `data/anon/`.

Quien tenga acceso a la base de la empresa puede regenerar la copia: llenar `.env` con
las credenciales (plantilla en el mismo archivo, que no se versiona) y ejecutar
`python src/extraer.py`. El mapa entre contratos reales y códigos queda en
`data/raw/`, que nunca se comparte.

## Cómo ejecutar

Requiere Python 3.12 o superior.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (en Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

python -m pytest -q             # pruebas (no necesitan los datos reales)
jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb
```

**En Google Colab:** el equipo comparte por Drive la carpeta `ProyectoModelos2_Colab`, con el cuaderno
único `Modelo_Riesgo_Mora_Colab.ipynb`, los módulos `.py`, los `.csv.gz` anonimizados de `data/anon/` y
`reports/` (resultados de la Parte 5). Quien la recibe le agrega un acceso directo en "Mi unidad"
(clic derecho → Organizar → Agregar acceso directo), abre el cuaderno con Colab y usa
Entorno de ejecución → Ejecutar todo. El cuaderno conecta Drive, verifica los archivos, corre las 5 partes
(EDA, clustering, clasificación, selección/explicabilidad y mejoras) y termina con un control de calidad
que compara los resultados con el informe. Guarda las salidas en la sesión (`/content/salidas`), así que
funciona con acceso de solo lectura; se borran al cerrar la sesión.

El cuaderno completo tarda entre 15 y 30 minutos (la rejilla K/H/X es lo más lento). Sus parámetros (`K`, `H`, `X` e inicio de
la cohorte) están en la sección 1 y todo se recalcula al cambiarlos. Genera en
`reports/` el diccionario de datos, la tabla de variables candidatas, las cifras
clave (`cifras_eda.json`) y las figuras del documento.

## Definiciones principales

- **Unidad de análisis:** el episodio, un cliente con una moto. El número de contrato
  identifica la moto y se reasigna cuando se retira.
- **Hubo pago:** cualquier dinero entregado ese día (abono, transferencia, multa o
  repuesto). La mora se mide contra el calendario esperado: cada `dia_canon` (semanal)
  o cada 14 días (quincenal) desde la fecha de inicio.
- **Etiqueta:** `y = 1` si algún ciclo que vence entre las semanas 9 y 20 del episodio
  alcanza 14 o más días de atraso, o nunca se pagó porque el episodio se cerró.
- **Corte temporal:** las variables de entrada solo usan información de las primeras 8
  semanas.

El detalle y la justificación de cada regla están en `docs/reglas_de_negocio.md`.
