#!/usr/bin/env python3
"""Tarjetas de las 53 semanas de 2026 con los melones (tipo y variedad) que
tienen escandallo cada semana, incluidas las semanas sin datos.

Uso:
    python3 tarjetas_anuales.py VOLCADO.csv [--salida tarjetas_semanas_2026.html]

La semana de cada escandallo sale de la fecha de sus medidas de firmeza
(el azúcar no trae fecha) y de semanas_2026_ia.json.
"""
import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

from escandallo import AQUI, cargar_variedades, leer_bloques, tipo_y_categoria


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--salida", type=Path, default=Path("tarjetas_semanas_2026.html"))
    ap.add_argument("--variedades", type=Path, default=AQUI / "variedades.csv")
    args = ap.parse_args()

    tabla = json.loads((AQUI / "semanas_2026_ia.json").read_text(encoding="utf-8"))
    nombres = cargar_variedades(args.variedades)
    bloques = leer_bloques(args.volcado)

    # semana -> tipo -> variedad -> fincas
    por_semana = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    sin_fecha = 0
    for b in bloques:
        if not b["firmeza"]:
            sin_fecha += 1
        tipo = tipo_y_categoria(b["producto"])[0]
        for f, _, _ in b["firmeza"]:
            sem = tabla["fecha_a_semana"][f.strftime("%d/%m/%Y")]
            por_semana[sem][tipo][b["variedad"]].add(b["cod_finca"])

    semanas = []
    for s in tabla["semanas"]:
        tipos = por_semana.get(s["etiqueta"], {})
        semanas.append({
            "etiqueta": s["etiqueta"], "desde": s["desde"], "hasta": s["hasta"],
            "tipos": [{"tipo": t, "variedades": [{"codigo": v, "nombre": nombres.get(v, ""),
                                                  "fincas": len(tipos[t][v])} for v in sorted(tipos[t])]}
                      for t in sorted(tipos)],
        })

    fechas = [f for b in bloques for f, _, _ in b["firmeza"]]
    datos = {"origen": args.volcado.name, "primera": min(fechas).isoformat(), "ultima": max(fechas).isoformat(),
             "hoy": dt.date.today().isoformat(), "sin_fecha": sin_fecha, "semanas": semanas}
    plantilla = (AQUI / "plantilla_tarjetas_anuales.html").read_text(encoding="utf-8")
    args.salida.write_text(plantilla.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False)),
                           encoding="utf-8")
    con = sum(1 for s in semanas if s["tipos"])
    print(f"{len(semanas)} semanas ({con} con datos) -> {args.salida}")


if __name__ == "__main__":
    main()
