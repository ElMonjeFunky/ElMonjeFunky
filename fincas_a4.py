#!/usr/bin/env python3
"""HTML imprimible A4 con los nombres de finca tal cual vienen del ERP y la
corrección propuesta (agricultor y paraje), agrupados por agricultor.

Uso:
    python3 fincas_a4.py VOLCADO.csv [--salida "Nombres de fincas revision"]
"""
import argparse
import csv
import html
import os
import subprocess
from collections import defaultdict
from pathlib import Path

from informe_a4 import CHROME, FUENTES

e = html.escape
FILAS_POR_PAGINA = 40

CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box}
body{margin:0;background:#fff}
.pg{width:794px;height:1123px;padding:38px 38px 0;display:flex;flex-direction:column;overflow:hidden;background:#fff;color:#1c221b;font:11px/1.35 "Source Sans 3","Segoe UI",Arial,sans-serif;break-after:page}
.pg:last-child{break-after:auto}
@media screen{html,body{background:#e3e6dd}.pg{margin:16px auto;box-shadow:0 1px 4px rgb(0 0 0/.15)}}
.cuerpo{flex:1;min-height:0;overflow:hidden}
.pie{flex:none;height:30px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid #cdd3c4;font-size:9.5px;color:#4f584b}
.lab{font:500 8px "IBM Plex Mono",Consolas,monospace;letter-spacing:.06em;text-transform:uppercase;color:#4f584b}
h1{margin:4px 0 6px;font:800 26px/1.05 "Bricolage Grotesque","Segoe UI",Arial,sans-serif;color:#2e5935}
.intro{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;margin:0 0 12px;font-size:9.5px;color:#4f584b}
.intro p{margin:0}.intro b{color:#1c221b}
.res{display:flex;gap:18px;margin:0 0 12px}
.res div{display:flex;flex-direction:column}.res b{font:700 16px "Bricolage Grotesque","Segoe UI",Arial,sans-serif}
h2{margin:0 0 8px;font:600 14px "Bricolage Grotesque","Segoe UI",Arial,sans-serif;color:#2e5935}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th{height:20px;padding:0 5px;font:500 7.5px "IBM Plex Mono",Consolas,monospace;letter-spacing:.05em;text-transform:uppercase;color:#4f584b;text-align:left;border-bottom:1.5px solid #1c221b;white-space:nowrap}
th.n,td.n{text-align:right}
td{height:24px;padding:3px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-top:1px solid #e3e7dc;font-size:10.5px}
tr.ini td{border-top:1px solid #9aa393}
td.num{color:#8a9184;font:400 9px "IBM Plex Mono",Consolas,monospace}
td.fin{font:600 12.5px "Source Sans 3","Segoe UI",Arial,sans-serif}
.jun{display:inline-block;font:500 7px "IBM Plex Mono",Consolas,monospace;text-transform:uppercase;color:#2e5935;background:#e6eedf;border-radius:2px;padding:0 3px;margin-left:4px}
td.rep{color:#8a9184}
td.erp{font:400 8.5px/13px "IBM Plex Mono",Consolas,monospace;color:#8a9184}
td.erp i{font-style:normal;color:#b5482c;background:#fbe9d8;border-radius:2px;padding:0 1px}
td.par{color:#1c221b}
td.cod{font:400 9.5px "IBM Plex Mono",Consolas,monospace}
.chk{display:inline-block;font:500 7px "IBM Plex Mono",Consolas,monospace;text-transform:uppercase;color:#8a6a12;background:#fbf1d3;border-radius:2px;padding:0 3px;margin-left:4px}
.cut{color:#b5482c}
"""


def erp_visible(nombre):
    """Muestra los espacios dobles del ERP marcados."""
    return e(nombre).replace("  ", " <i>␣</i>")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--salida", default="Nombres de fincas preliminar")
    args = ap.parse_args()

    mapa = list(csv.DictReader(open(Path(__file__).with_name("fincas_nombres.csv"), encoding="utf-8"), delimiter=";"))
    codigos = defaultdict(set)
    for fila in csv.reader(open(args.volcado, encoding="latin-1"), delimiter=";"):
        if len(fila) > 8 and fila[8] == "00/00/0000":
            codigos[fila[5]].add(fila[4])
    grupos = defaultdict(list)
    for m in mapa:
        grupos[m["nombre_final"]].append(m)

    def orden(t):
        return t.lower().translate(str.maketrans("áéíóúü", "aeiouu"))

    filas = []
    for i, nombre in enumerate(sorted(grupos, key=orden), start=1):
        ms = grupos[nombre]
        erp = "<br>".join(erp_visible(m["nombre_erp"]) for m in ms)
        n_cod = sum(len(codigos[m["nombre_erp"]]) for m in ms)
        aviso = '<span class="chk">revisar</span>' if any(m["revisar"] for m in ms) else ""
        junta = f'<span class="jun">junta {len(ms)}</span>' if len(ms) > 1 else ""
        filas.append((len(ms), f'<tr class="ini"><td class="num">{i}</td><td class="fin">{e(nombre)}{aviso}{junta}</td>'
                               f'<td class="erp">{erp}</td><td class="n cod">{n_cod}</td></tr>'))

    cab = ('<table><thead><tr><th style="width:5%"></th><th style="width:47%">Nombre en el informe</th>'
           '<th style="width:38%">Nombre(s) en el ERP que agrupa</th><th class="n" style="width:10%">Códigos</th></tr></thead><tbody>')
    intro = f'''<div class="lab">Lista preliminar · nombres de finca para los informes</div>
<h1>Nombres de fincas</h1>
<div class="res"><div><span class="lab">Nombres en el informe</span><b>{len(grupos)}</b></div>
<div><span class="lab">Nombres en el ERP</span><b>{len(mapa)}</b></div><div><span class="lab">Códigos de finca</span><b>{sum(len(v) for v in codigos.values())}</b></div></div>
<div class="intro">
<p><b>Criterio:</b> un solo nombre corto, como se dice en el día a día: persona como «Nombre Apellido (Paraje)», sociedad con su palabra
reconocible + paraje (HSI Jumilla, Explot Chinchilla Ba, Fruveg El Jeringal). Abreviaturas: C.Criptana, A.San Gregorio.</p>
<p><b>Cómo leerla:</b> a la derecha, en gris, los nombres tal cual vienen del ERP que van bajo ese nombre (<span class="jun">junta 2</span> = varios
nombres del ERP en uno). <span class="chk">revisar</span> = agrupación o abreviatura que he supuesto yo. «Códigos» = códigos de finca del ERP.</p>
</div>'''
    paginas = []
    trozos, actual, usado, cap = [], [], 0, 850
    for alto, html_fila in filas:
        h = 24 + 13 * (alto - 1)
        if usado + h > cap:
            trozos.append(actual)
            actual, usado, cap = [], 0, 960
        actual.append(html_fila)
        usado += h
    trozos.append(actual)
    for i, trozo in enumerate(trozos):
        cuerpo = (intro if i == 0 else '<h2>Nombres de fincas (continuación)</h2>') + cab + "".join(trozo) + "</tbody></table>"
        paginas.append(f'<div class="pg"><div class="cuerpo">{cuerpo}</div><div class="pie"><span>Nombres de fincas · lista preliminar</span>'
                       f'<span>Página {i + 1} de {len(trozos)}</span></div></div>')
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Nombres de fincas</title>{FUENTES}'
           f'<style>{CSS}</style></head><body>{"".join(paginas)}</body></html>')
    ruta_html, ruta_pdf = Path(args.salida + ".html"), Path(args.salida + ".pdf")
    ruta_html.write_text(doc, encoding="utf-8")
    if os.path.exists(CHROME):
        subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={ruta_pdf.resolve()}", ruta_html.resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f"{len(paginas)} páginas, {len(filas)} nombres -> {ruta_html}, {ruta_pdf}")


if __name__ == "__main__":
    main()
