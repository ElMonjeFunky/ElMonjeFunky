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
td{height:21px;padding:0 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-top:1px solid #e3e7dc;font-size:10.5px}
tr.ini td{border-top:1px solid #9aa393}
td.num{color:#8a9184;font:400 9px "IBM Plex Mono",Consolas,monospace}
td.ag{font-weight:600}
td.rep{color:#8a9184}
td.erp{font:400 9.5px "IBM Plex Mono",Consolas,monospace;color:#4f584b}
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
    ap.add_argument("--salida", default="Nombres de fincas revision")
    args = ap.parse_args()

    mapa = list(csv.DictReader(open(Path(__file__).with_name("fincas_nombres.csv"), encoding="utf-8"), delimiter=";"))
    codigos = defaultdict(set)
    for fila in csv.reader(open(args.volcado, encoding="latin-1"), delimiter=";"):
        if len(fila) > 8 and fila[8] == "00/00/0000":
            codigos[fila[5]].add(fila[4])
    grupos = defaultdict(list)
    for m in mapa:
        grupos[m["agricultor"]].append(m)

    filas, num = [], 0
    for agr in sorted(grupos, key=lambda s: s.lower().replace("á", "a").replace("ú", "u")):
        num += 1
        for j, m in enumerate(grupos[agr]):
            paraje = e(m["paraje"]) if m["paraje"] else '<span class="rep">—</span>'
            if m["paraje"].endswith("…"):
                paraje = f'<span class="cut">{paraje}</span>'
            if "comprobar" in m["nota"]:
                paraje += '<span class="chk">comprobar</span>'
            filas.append(f'<tr class="{"ini" if j == 0 else ""}"><td class="num">{num if j == 0 else ""}</td>'
                         f'<td class="{"ag" if j == 0 else "rep"}">{e(agr) if j == 0 else "〃"}</td>'
                         f'<td class="erp">{erp_visible(m["nombre_erp"])}</td><td class="par">{paraje}</td>'
                         f'<td class="n cod">{len(codigos[m["nombre_erp"]])}</td></tr>')

    cab = ('<table><thead><tr><th style="width:4%"></th><th style="width:31%">Agricultor propuesto</th>'
           '<th style="width:33%">Nombre en el ERP (tal cual)</th><th style="width:24%">Paraje propuesto</th>'
           '<th class="n" style="width:8%">Códigos</th></tr></thead><tbody>')
    intro = f'''<div class="lab">Revisión de nombres · volcado de escandallo melón 2026</div>
<h1>Nombres de fincas y agricultores</h1>
<div class="res"><div><span class="lab">Códigos de finca</span><b>{sum(len(v) for v in codigos.values())}</b></div>
<div><span class="lab">Nombres en el ERP</span><b>{len(mapa)}</b></div><div><span class="lab">Agricultores propuestos</span><b>{len(grupos)}</b></div></div>
<div class="intro">
<p><b>Cómo vienen del ERP:</b> en mayúsculas y sin tildes, cortados a 30 caracteres, agricultor y paraje pegados, con nº de parcela
(18/2, 23/, 21/2026), espacios dobles (marcados <span style="color:#b5482c">␣</span>) y abreviaturas (EXPLOT, VERD., HORTOFRUTIC., SDAD COOP).</p>
<p><b>Corrección propuesta:</b> mayúsculas normales con tildes; personas como «Apellidos, Nombre»; sociedades con S.L., S.A., S. Coop.;
agricultor y paraje separados, sin nº de parcela. Parajes deducidos marcados <span class="chk">comprobar</span>; los que no se pueden deducir,
en rojo con «…». «Códigos» = nº de códigos de finca del ERP con ese nombre.</p>
</div>'''
    paginas, primera_cap = [], FILAS_POR_PAGINA - 9
    trozos = [filas[:primera_cap]] + [filas[i:i + FILAS_POR_PAGINA] for i in range(primera_cap, len(filas), FILAS_POR_PAGINA)]
    for i, trozo in enumerate(trozos):
        cuerpo = (intro if i == 0 else '<h2>Nombres de fincas y agricultores (continuación)</h2>') + cab + "".join(trozo) + "</tbody></table>"
        paginas.append(f'<div class="pg"><div class="cuerpo">{cuerpo}</div><div class="pie"><span>Nombres de fincas · revisión</span>'
                       f'<span>Página {i + 1} de {len(trozos)}</span></div></div>')
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Nombres de fincas</title>{FUENTES}'
           f'<style>{CSS}</style></head><body>{"".join(paginas)}</body></html>')
    ruta_html, ruta_pdf = Path(args.salida + ".html"), Path(args.salida + ".pdf")
    ruta_html.write_text(doc, encoding="utf-8")
    if os.path.exists(CHROME):
        subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={ruta_pdf.resolve()}", ruta_html.resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f"{len(paginas)} páginas, {len(filas)} filas -> {ruta_html}, {ruta_pdf}")


if __name__ == "__main__":
    main()
