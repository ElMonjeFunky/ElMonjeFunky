#!/usr/bin/env python3
"""Tarjetas semanales completas: por semana, cada tipo de melón y variedad con
fincas, albaranes, firmeza (media/mín/máx de esa semana) y azúcar (media/mín/máx).

Uso:
    python3 tarjetas_completas.py VOLCADO.csv [--semanas S27 S28] [--salida tarjetas_completas_2026.html]

Sin --semanas salen las 53 semanas del año, también las vacías.
El volcado no trae fecha para el azúcar: se muestra el de toda la temporada de
esas fincas y variedad, marcado como "temporada".
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from escandallo import AQUI, bandas_azucar, cargar_variedades, estadisticas, leer_bloques, tipo_y_categoria


def resumen(items):
    """items: [(bloque, medidas de la semana)] -> cifras de la semana.
    'medidas' son solo medidas de firmeza; las de azúcar no se cuentan porque
    el volcado no da su número exacto."""
    valores = [v for _, med in items for _, _, v in med]
    az = estadisticas([b for b, _ in items])
    return {
        "fincas": len({b["cod_finca"] for b, _ in items}),
        "albaranes": len({(b["cod_finca"], a) for b, med in items for _, a, _ in med}),
        "medidas": len(valores),
        "firmeza": [round(mean(valores), 2), min(valores), max(valores)] if valores else None,
        "azucar": az[:3] if az[0] is not None else None,
        "bandas": bandas_azucar([b for b, _ in items]),
        "muestras_azucar": az[3] if az[0] is not None else None,
    }


def construir_semanas(volcado, ruta_variedades=AQUI / "variedades.csv"):
    """Las 53 semanas con sus tipos, variedades y fincas (y sus cifras)."""
    tabla = json.loads((AQUI / "semanas_2026_ia.json").read_text(encoding="utf-8"))
    nombres = cargar_variedades(ruta_variedades)
    bloques = leer_bloques(volcado)

    # semana -> tipo -> variedad -> [(bloque, medidas de esa semana)]
    arbol = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for b in bloques:
        por_sem = defaultdict(list)
        for m in b["firmeza"]:
            por_sem[tabla["fecha_a_semana"][m[0].strftime("%d/%m/%Y")]].append(m)
        for sem, med in por_sem.items():
            arbol[sem][tipo_y_categoria(b["producto"])[0]][b["variedad"]].append((b, med))

    semanas, anterior = [], None
    for s in tabla["semanas"]:
        tipos = arbol.get(s["etiqueta"], {})
        todos = [it for vs in tipos.values() for its in vs.values() for it in its]
        tarjeta = {"etiqueta": s["etiqueta"], "desde": s["desde"], "hasta": s["hasta"], "tipos": [],
                   "total": resumen(todos) if todos else None,
                   "variedades": sum(len(v) for v in tipos.values())}
        for t in sorted(tipos):
            vs = tipos[t]
            tarjeta["tipos"].append({
                "tipo": t, "total": resumen([it for its in vs.values() for it in its]),
                "variedades": [{
                    "codigo": v, "nombre": nombres.get(v, ""), **resumen(vs[v]),
                    "fincas_detalle": [{"finca": b["finca"], "cod": b["cod_finca"],
                                        "cat": tipo_y_categoria(b["producto"])[1], **resumen([(b, med)])}
                                       for b, med in sorted(vs[v], key=lambda x: x[0]["finca"])],
                } for v in sorted(vs)],
            })
        prev = anterior["total"]["firmeza"][0] if anterior and anterior["total"] and anterior["total"]["firmeza"] else None
        tarjeta["firmeza_anterior"] = prev
        semanas.append(tarjeta)
        anterior = tarjeta
    return semanas, bloques


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--semanas", nargs="*", help="solo estas semanas (ej. S27)")
    ap.add_argument("--salida", type=Path, default=Path("tarjetas_completas_2026.html"))
    ap.add_argument("--variedades", type=Path, default=AQUI / "variedades.csv")
    args = ap.parse_args()

    semanas, _ = construir_semanas(args.volcado, args.variedades)
    if args.semanas:
        semanas = [s for s in semanas if s["etiqueta"] in args.semanas]
    datos = {"origen": args.volcado.name, "semanas": semanas, "azucar_temporada": True}
    plantilla = (AQUI / "plantilla_tarjetas_completas.html").read_text(encoding="utf-8")
    args.salida.write_text(plantilla.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False)),
                           encoding="utf-8")
    print(f"{len(semanas)} semanas -> {args.salida}")


if __name__ == "__main__":
    main()
