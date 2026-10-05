#!/usr/bin/env python3
"""Tarjetas semanales: qué melones (tipo y variedad) tienen escandallo cada semana,
con su firmeza de esa semana y el azúcar de temporada de esas fincas.

Uso:
    python3 tarjetas_semanales.py VOLCADO.csv [--desde 01/09/2026] [--hasta 30/09/2026]
                                  [--salida tarjetas_septiembre.html]

La semana de cada escandallo sale de la fecha de sus medidas de firmeza y de
semanas_2026_ia.json. El volcado no trae fecha para el azúcar, así que en cada
fila se muestra el azúcar de toda la temporada de esas fincas y variedad.
"""
import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from escandallo import AQUI, cargar_variedades, estadisticas, leer_bloques, tipo_y_categoria


def fecha(texto):
    return dt.datetime.strptime(texto, "%d/%m/%Y").date()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--desde", type=fecha, default=dt.date(2026, 9, 1))
    ap.add_argument("--hasta", type=fecha, default=dt.date(2026, 9, 30))
    ap.add_argument("--salida", type=Path, default=Path("tarjetas_septiembre.html"))
    ap.add_argument("--variedades", type=Path, default=AQUI / "variedades.csv")
    args = ap.parse_args()

    tabla = json.loads((AQUI / "semanas_2026_ia.json").read_text(encoding="utf-8"))
    semana_de = tabla["fecha_a_semana"]
    nombres = cargar_variedades(args.variedades)
    bloques = leer_bloques(args.volcado)
    ultima = max(f for b in bloques for f, _, _ in b["firmeza"])

    # Semanas que tocan el periodo, con su rango recortado al periodo
    semanas = []
    for s in tabla["semanas"]:
        ini, fin = max(fecha(s["desde"]), args.desde), min(fecha(s["hasta"]), args.hasta)
        if ini <= fin:
            semanas.append({"etiqueta": s["etiqueta"], "desde": s["desde"], "hasta": s["hasta"],
                            "periodo_desde": ini.isoformat(), "periodo_hasta": fin.isoformat()})

    # semana -> (tipo, variedad) -> [(bloque, medidas de esa semana)]
    grupos = defaultdict(lambda: defaultdict(list))
    for b in bloques:
        por_semana = defaultdict(list)
        for f, alb, v in b["firmeza"]:
            if args.desde <= f <= args.hasta:
                por_semana[semana_de[f.strftime("%d/%m/%Y")]].append((f, alb, v))
        for sem, medidas in por_semana.items():
            grupos[sem][(tipo_y_categoria(b["producto"])[0], b["variedad"])].append((b, medidas))

    for s in semanas:
        filas = []
        for (tipo, var), items in sorted(grupos[s["etiqueta"]].items()):
            valores = [v for _, med in items for _, _, v in med]
            az = estadisticas([b for b, _ in items])[:5]
            filas.append({
                "tipo": tipo, "variedad": var, "nombre": nombres.get(var, ""),
                "fincas": sorted({f"{b['finca']} ({b['cod_finca']})" for b, _ in items}),
                "albaranes": len({(b["cod_finca"], a) for b, med in items for _, a, _ in med}),
                "medidas": len(valores),
                "firmeza": [round(mean(valores), 2), min(valores), max(valores)],
                "azucar_temporada": az[:3], "mayor12_temporada": az[4],
                "fechas": sorted({f.isoformat() for _, med in items for f, _, _ in med}),
            })
        s["filas"] = filas

    datos = {"desde": args.desde.isoformat(), "hasta": args.hasta.isoformat(),
             "ultima_fecha_volcado": ultima.isoformat(), "origen": args.volcado.name, "semanas": semanas}
    plantilla = (AQUI / "plantilla_tarjetas.html").read_text(encoding="utf-8")
    args.salida.write_text(plantilla.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False)),
                           encoding="utf-8")
    print(f"{len(semanas)} semanas, {sum(len(s['filas']) for s in semanas)} filas -> {args.salida}")


if __name__ == "__main__":
    main()
