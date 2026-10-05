#!/usr/bin/env python3
"""Informe semanal de melón: azúcar (°Brix) y firmeza por semana y variedad.

Uso:
    python3 informe_semanal.py datos_brutos.xlsx            # o .csv
    python3 informe_semanal.py datos.csv --fecha "F. muestreo" --variedad Var \
        --azucar Brix --firmeza "Firmeza (kg)"

Genera <entrada>_informe.xlsx con tres hojas:
    Resumen            semana x variedad: nº muestras, azúcar y firmeza media/mín/máx
    Datos etiquetados  los datos brutos con la columna 'semana' añadida
    Sin semana         filas cuya fecha no se pudo leer o cae fuera de 2026
y muestra el resumen por pantalla en Markdown.
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

TABLA_SEMANAS = Path(__file__).with_name("semanas_2026_ia.json")

# Palabras clave para detectar cada columna si no se indica a mano.
CLAVES = {
    "fecha": ["fecha", "date", "dia"],
    "variedad": ["variedad", "variety", "var", "cultivar", "producto"],
    "azucar": ["azucar", "brix", "sugar", "ss", "solidos"],
    "firmeza": ["firmeza", "firmness", "dureza", "presion", "penetrometro"],
}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return texto.lower().strip()


def detectar_columna(columnas, campo):
    for col in columnas:
        nombre = normalizar(col)
        if any(clave == nombre or clave in nombre.split() or nombre.startswith(clave)
               for clave in CLAVES[campo]):
            return col
    return None


def leer_datos(ruta):
    if ruta.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(ruta)
    # CSV: detecta el separador (; es habitual en Excel en español)
    return pd.read_csv(ruta, sep=None, engine="python", encoding="utf-8-sig")


def a_numero(serie):
    if not pd.api.types.is_numeric_dtype(serie):
        serie = serie.astype(str).str.replace(",", ".", regex=False).str.strip()
    return pd.to_numeric(serie, errors="coerce")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("entrada", type=Path)
    for campo in CLAVES:
        p.add_argument(f"--{campo}", help=f"nombre de la columna de {campo}")
    p.add_argument("--salida", type=Path)
    args = p.parse_args()

    df = leer_datos(args.entrada)
    cols = {}
    for campo in CLAVES:
        col = getattr(args, campo) or detectar_columna(df.columns, campo)
        if col is None or col not in df.columns:
            sys.exit(f"No encuentro la columna de '{campo}'. Columnas: {list(df.columns)}. "
                     f"Indícala con --{campo} \"NOMBRE\"")
        cols[campo] = col
    print("Columnas usadas:", cols, file=sys.stderr)

    fecha_a_semana = json.loads(TABLA_SEMANAS.read_text(encoding="utf-8"))["fecha_a_semana"]
    fechas = df[cols["fecha"]]
    if not pd.api.types.is_datetime64_any_dtype(fechas):
        fechas = pd.to_datetime(fechas, dayfirst=True, errors="coerce")
    df["semana"] = fechas.dt.strftime("%d/%m/%Y").map(fecha_a_semana).fillna("SIN_SEMANA")

    df["_azucar"] = a_numero(df[cols["azucar"]])
    df["_firmeza"] = a_numero(df[cols["firmeza"]])
    df["_variedad"] = df[cols["variedad"]].astype(str).str.strip()

    validas = df[df["semana"] != "SIN_SEMANA"]
    resumen = (validas.groupby(["semana", "_variedad"])
               .agg(muestras=("_azucar", "size"),
                    azucar_media=("_azucar", "mean"), azucar_min=("_azucar", "min"), azucar_max=("_azucar", "max"),
                    firmeza_media=("_firmeza", "mean"), firmeza_min=("_firmeza", "min"), firmeza_max=("_firmeza", "max"))
               .round(2).reset_index().rename(columns={"_variedad": "variedad"}))

    salida = args.salida or args.entrada.with_name(args.entrada.stem + "_informe.xlsx")
    with pd.ExcelWriter(salida) as xl:
        resumen.to_excel(xl, sheet_name="Resumen", index=False)
        df.drop(columns=["_azucar", "_firmeza", "_variedad"]).to_excel(xl, sheet_name="Datos etiquetados", index=False)
        df[df["semana"] == "SIN_SEMANA"].drop(columns=["_azucar", "_firmeza", "_variedad"]) \
            .to_excel(xl, sheet_name="Sin semana", index=False)

    print(resumen.to_markdown(index=False) if len(resumen) else "Sin datos válidos.")
    sin = (df["semana"] == "SIN_SEMANA").sum()
    if sin:
        print(f"\nAviso: {sin} fila(s) sin semana (fecha ilegible o fuera de rango).")
    print(f"\nInforme guardado en {salida}", file=sys.stderr)


if __name__ == "__main__":
    main()
