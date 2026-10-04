"""Extrae la copia anonimizada de los datos desde la base de la empresa.

Uso (requiere el .env con credenciales y acceso a la VPN de la empresa):

    python src/extraer.py

Genera:
    data/anon/abonos.csv.gz         historial de pagos (np_his_abonos)
    data/anon/motos_diario.csv.gz   foto diaria de cada moto activa (motos_app_hist)
    data/anon/rentabilidad.csv.gz   episodios cerrados (rentabilidad_activos[_cartas])
    data/raw/mapa_contratos.csv     contrato real -> codigo (PRIVADO, nunca se comparte)

Solo se extraen las columnas del analisis: nada de nombres, telefonos, placas,
titulares, barrios ni evidencias. El numero de contrato se reemplaza por un codigo.
Las exclusiones de alcance (RASTREOYA, correos, Medellin) se aplican aqui porque
esos registros no deben salir de la empresa; las demas reglas (cartas, DIARIO,
fecha_inicio 0000-00-00...) se aplican en el notebook para que queden visibles.
Ver docs/reglas_de_negocio.md.
"""
import random

import pandas as pd

from conexion import RAIZ, consultar

BASE = "db_packgps"
DIR_RAW = RAIZ / "data" / "raw"
DIR_ANON = RAIZ / "data" / "anon"
MAPA = DIR_RAW / "mapa_contratos.csv"


def contratos_validos(abonos):
    """Contratos de leasing de Cartagena: numericos, sin RASTREOYA ni Medellin."""
    numerico = abonos.CONTRATO.str.fullmatch(r"\d+")
    rastreoya = abonos.empresa.eq("RASTREOYA")
    medellin = abonos.CARTAMOTIVO.fillna("").str.upper().str.contains("MEDELL")
    excluidos_medellin = set(abonos.loc[medellin, "CONTRATO"])
    validos = set(abonos.loc[numerico & ~rastreoya, "CONTRATO"]) - excluidos_medellin
    print(f"contratos validos: {len(validos)} (Medellin excluidos: {len(excluidos_medellin)})")
    return validos


def mapa_codigos(contratos):
    """Codigo estable por contrato. Se reutiliza el mapa existente para que una
    nueva extraccion no cambie los codigos; los contratos nuevos se agregan al final."""
    if MAPA.exists():
        mapa = pd.read_csv(MAPA, dtype=str)
    else:
        mapa = pd.DataFrame(columns=["contrato", "id_contrato"])
    nuevos = sorted(set(contratos) - set(mapa.contrato))
    # Orden aleatorio sin semilla, a proposito: el codigo no debe poder
    # reconstruirse a partir del numero de contrato real.
    random.SystemRandom().shuffle(nuevos)
    inicio = len(mapa) + 1
    mapa = pd.concat([mapa, pd.DataFrame({
        "contrato": nuevos,
        "id_contrato": [f"C{i:05d}" for i in range(inicio, inicio + len(nuevos))],
    })], ignore_index=True)
    MAPA.parent.mkdir(parents=True, exist_ok=True)
    mapa.to_csv(MAPA, index=False)
    return dict(zip(mapa.contrato, mapa.id_contrato))


def anonimizar(df, col, mapa):
    df = df[df[col].isin(mapa)].copy()
    df.insert(0, "id_contrato", df.pop(col).map(mapa))
    return df


def main():
    DIR_ANON.mkdir(parents=True, exist_ok=True)

    abonos = consultar("""
        SELECT TRIM(CONTRATO) CONTRATO, FECHA, ABONO, TRANSF, MULTA, REPUESTO,
               CARTA, CARTAMOTIVO, CONCEPTO, empresa
        FROM np_his_abonos""", base=BASE)
    validos = contratos_validos(abonos)
    mapa = mapa_codigos(validos)
    abonos = anonimizar(abonos, "CONTRATO", mapa).rename(columns=str.lower)
    abonos.to_csv(DIR_ANON / "abonos.csv.gz", index=False)
    print(f"abonos: {len(abonos)} filas, {abonos.id_contrato.nunique()} contratos")

    # '0000-00-00' en fecha_inicio es un valor con significado (cliente asignado con
    # tramites pendientes). El driver lo entrega como nulo aunque se pida como texto,
    # asi que se restituye para que la copia no lo confunda con un dato faltante.
    diario = consultar("""
        SELECT TRIM(contrato) contrato, fecha_registro, CAST(fecha_inicio AS CHAR) fecha_inicio,
               tipopago, dia_canon, cuota, no_canon, diassinpagar, JUSTIFICACION justificacion, empresa
        FROM motos_app_hist""", base=BASE)
    diario["fecha_inicio"] = diario.fecha_inicio.fillna("0000-00-00")
    diario = anonimizar(diario, "contrato", mapa)
    diario.to_csv(DIR_ANON / "motos_diario.csv.gz", index=False)
    print(f"motos_diario: {len(diario)} filas, {diario.id_contrato.nunique()} contratos")

    partes = []
    for tabla in ("rentabilidad_activos", "rentabilidad_activos_cartas"):
        partes.append(consultar(f"""
            SELECT TRIM(contrato) contrato, CONCEPTO concepto, fecha_inicio, FechaFinal fecha_final,
                   FechaRegistro fecha_registro, tipopago, dia_canon, cuota, no_canon
            FROM {tabla}""", base=BASE).assign(fuente=tabla))
    rent = anonimizar(pd.concat(partes, ignore_index=True), "contrato", mapa)
    rent.to_csv(DIR_ANON / "rentabilidad.csv.gz", index=False)
    print(f"rentabilidad: {len(rent)} filas, {rent.id_contrato.nunique()} contratos")


if __name__ == "__main__":
    main()
