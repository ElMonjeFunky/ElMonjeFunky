#!/usr/bin/env python3
"""Medias de problemas (mayores y menores) por tipo de melón, sobre todas las
fincas y variedades juntas.

Uso:
    python3 problemas.py VOLCADO.csv [--salida problemas_por_tipo_melon_2026.xlsx]

Cada escandallo (variedad + finca) trae el % de cada problema para toda la
temporada, sin fecha. La media de un tipo pondera cada escandallo por sus
medidas de firmeza (≈ melones escandallados); si un escandallo no tiene un
problema, cuenta como 0 %. El mismo problema con dos códigos se junta por nombre.
"""
import argparse
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from escandallo import FUENTE, hoja, leer_bloques, tipo_y_categoria


def medias_por_tipo(bloques):
    """{tipo: {"escandallos", "medidas", "mayores": [(problema, media, % escandallos)], "menores": [...]}}"""
    por_tipo = defaultdict(list)
    for b in bloques:
        if b["firmeza"]:
            por_tipo[tipo_y_categoria(b["producto"])[0]].append(b)
    res = {}
    for tipo, bs in sorted(por_tipo.items()):
        peso = sum(len(b["firmeza"]) for b in bs)
        r = {"escandallos": len(bs), "medidas": peso}
        for sec in ("mayores", "menores"):
            filas = []
            for nombre in {p for b in bs for p in b[sec]}:
                media = sum(b[sec].get(nombre, 0) * len(b["firmeza"]) for b in bs) / peso
                frec = sum(1 for b in bs if b[sec].get(nombre, 0) > 0) / len(bs)
                filas.append((nombre, round(media, 2), frec))
            r[sec] = sorted(filas, key=lambda f: -f[1])
        res[tipo] = r
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--salida", type=Path, default=Path("problemas_por_tipo_melon_2026.xlsx"))
    args = ap.parse_args()

    res = medias_por_tipo(leer_bloques(args.volcado))
    wb = Workbook()
    hoja(wb, "Resumen", ["Tipo melón", "Escandallos", "Medidas firmeza (peso)", "Nº problemas mayores",
                         "Suma % mayores", "Nº problemas menores", "Suma % menores"],
         [[t, r["escandallos"], r["medidas"], len(r["mayores"]), round(sum(f[1] for f in r["mayores"]), 2),
           len(r["menores"]), round(sum(f[1] for f in r["menores"]), 2)] for t, r in res.items()],
         {"E": "0.00", "G": "0.00"}, [20, 12, 14, 12, 12, 12, 12], primera=True)
    for sec, titulo in (("mayores", "Problemas mayores"), ("menores", "Problemas menores")):
        filas = [[t, i, nombre, media, frec] for t, r in res.items()
                 for i, (nombre, media, frec) in enumerate(r[sec], start=1)]
        hoja(wb, titulo, ["Tipo melón", "Puesto", "Problema", "Media %", "% escandallos con el problema"],
             filas, {"D": "0.00", "E": "0%"}, [20, 8, 28, 10, 16])
    notas = wb.create_sheet("Notas")
    for linea in [
        "Cómo se calculan las medias",
        "Cada escandallo (variedad + finca) trae el % de cada problema para toda la temporada; el volcado no trae fecha de los problemas.",
        "Media % del tipo = media de todos sus escandallos, cada uno pesa según sus medidas de firmeza (≈ melones escandallados).",
        "Si un escandallo no tiene un problema, cuenta como 0 %. Escandallos sin medidas de firmeza no entran (no hay con qué pesarlos).",
        "% escandallos con el problema = en cuántos escandallos del tipo aparece (es la frecuencia, no la gravedad).",
        "El mismo problema con dos códigos se junta por nombre (p. ej. PODRIDO PEQUEÑO 115 y 852). Problemas marcados con '·' en el ERP (internos) van sin el punto.",
    ]:
        notas.append([linea])
    notas["A1"].font = Font(name=FUENTE, bold=True, size=13)
    for c in notas["A"][1:]:
        c.font = Font(name=FUENTE)
    notas.column_dimensions["A"].width = 130
    wb.save(args.salida)
    print(f"{len(res)} tipos -> {args.salida}")


if __name__ == "__main__":
    main()
