# Modelo predictivo de riesgo de mora en contratos de leasing de motocicletas

Proyecto de aula de **Modelos y Simulación de Sistemas II** (Universidad de Antioquia),
Grupo 14: Juan Esteban Cardozo Rivera, Maria Carolina Cardona Calderon y Oliver Andres
Quiroz Mora.

El sistema tiene dos etapas encadenadas: (1) agrupar los contratos según su
comportamiento de pago en las primeras semanas (aprendizaje no supervisado) y (2)
estimar la probabilidad de que un contrato termine en riesgo grave de mora usando esas
variables y el perfil de la etapa 1 (aprendizaje supervisado).

Este repositorio contiene el **Entregable I**: análisis exploratorio de la base real,
definición de la variable objetivo y construcción de las variables candidatas.

## Estructura

```
notebooks/01_eda.ipynb       análisis exploratorio completo (ejecutado, con resultados)
src/ciclos.py                episodios y calendario de pagos esperado
src/variables.py             población, etiqueta y variables con corte temporal
src/extraer.py               extracción de la copia anonimizada (requiere acceso a la empresa)
src/conexion.py              conexión de solo lectura a la base
tests/test_ciclos.py         pruebas del calendario, la etiqueta y la ausencia de fuga
docs/reglas_de_negocio.md    reglas de negocio y de limpieza confirmadas con la empresa
docs/secciones_entregable1.md texto de las secciones 1.5 a 1.8 del documento
reports/                     cifras, diccionario de datos, variables y figuras generadas
data/                        datos (no se versionan, ver abajo)
```

## Datos

Los datos son **confidenciales de la empresa** y no están en el repositorio. El notebook
espera la copia anonimizada en `data/anon/`:

| Archivo | Contenido |
|---|---|
| `data/anon/abonos.csv.gz` | historial de pagos (un registro por contrato y fecha) |
| `data/anon/motos_diario.csv.gz` | foto diaria de cada moto activa desde 2024-03-30 |
| `data/anon/rentabilidad.csv.gz` | episodios cerrados con su desenlace |

La copia no tiene nombres, teléfonos, placas, titulares, barrios ni evidencias, y el
número de contrato se reemplazó por un código (`C00001`...). El equipo la comparte por
un canal privado. Para reproducir el análisis, se descargan los tres archivos y se
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

**En Google Colab:** subir a la sesión (panel Archivos), todos en la misma carpeta,
el notebook, `src/ciclos.py`, `src/variables.py` y los tres archivos de `data/anon/`.
El notebook detecta esa estructura sola. Los resultados quedan en `reports/` dentro de
la sesión y se borran al cerrarla, así que hay que descargarlos.

El notebook tarda alrededor de dos minutos. Sus parámetros (`K`, `H`, `X` e inicio de
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

El reporte final se redacta aparte en Overleaf, con la plantilla IEEE Transactions.
