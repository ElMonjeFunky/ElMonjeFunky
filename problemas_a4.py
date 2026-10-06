#!/usr/bin/env python3
"""HTML imprimible A4 con una tabla por página y tipo de melón: todos los
problemas mayores y menores con su media % y su frecuencia.

Uso:
    python3 problemas_a4.py VOLCADO.csv [--salida "Problemas por tipo melon 2026"]

Genera <salida>.html y <salida>.pdf.
"""
import argparse
import html
import os
import subprocess
from pathlib import Path

from escandallo import leer_bloques
from informe_a4 import CHROME, COLOR, FUENTES
from problemas import medias_por_tipo

e = html.escape
TITULO = "Problemas por tipo de melón 2026"

CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box}
body{margin:0;background:#fff}
.pg{width:794px;height:1123px;padding:38px 38px 0;display:flex;flex-direction:column;overflow:hidden;background:#fff;color:#1c221b;font:11px/1.35 "Source Sans 3","Segoe UI",Arial,sans-serif;break-after:page}
.pg:last-child{break-after:auto}
@media screen{html,body{background:#e3e6dd}.pg{margin:16px auto;box-shadow:0 1px 4px rgb(0 0 0/.15)}}
.cuerpo{flex:1;min-height:0;overflow:hidden}
.pie{flex:none;height:30px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid #cdd3c4;font-size:9.5px;color:#4f584b}
.pie b{color:#1c221b;font-weight:600}
.lab{font:500 8px "IBM Plex Mono",Consolas,monospace;letter-spacing:.06em;text-transform:uppercase;color:#4f584b}
.cab{display:grid;grid-template-columns:minmax(0,1fr) 150px 150px;gap:8px;height:86px;margin-bottom:12px}
.tit{border-radius:6px;padding:9px 12px;display:flex;flex-direction:column;justify-content:space-between;background:color-mix(in srgb,var(--c) 14%,white);border-left:0}
.tit h1{margin:0;font:800 28px/1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif;color:#1c221b;display:flex;align-items:center;gap:10px}
.tit h1 i{width:14px;height:14px;border-radius:50%;background:var(--c);display:inline-block}
.tit p{margin:0;color:#4f584b;font-size:10.5px}
.kpi{border:1px solid #cdd3c4;border-radius:6px;padding:8px 10px;display:flex;flex-direction:column;justify-content:space-between}
.kpi b{font:800 24px/1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif}
.kpi.may b{color:#a3361c}.kpi.men b{color:#8a6a12}
.kpi span:last-child{font-size:9.5px;color:#4f584b}
.grp{display:flex;font:600 8px/16px "IBM Plex Mono",Consolas,monospace;letter-spacing:.06em;text-transform:uppercase}
.grp span{text-align:center;border-bottom:1.5px solid}
.grp .gm{color:#a3361c}.grp .gn{color:#8a6a12}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th{height:20px;padding:0 5px;font:500 7.5px "IBM Plex Mono",Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;color:#4f584b;text-align:right;white-space:nowrap}
th.l{text-align:left}
td{padding:0 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right;font:400 10px "IBM Plex Mono",Consolas,monospace;border-top:1px solid #e3e7dc}
td.l{text-align:left;font:600 10.5px "Source Sans 3","Segoe UI",Arial,sans-serif}
td.n{color:#8a9184;font-size:9px}
td.f{color:#4f584b}
td.sep{border-left:1px solid #cdd3c4}
td.vm{color:#a3361c;font-weight:500}td.vn{color:#8a6a12;font-weight:500}
.bar{display:inline-block;height:7px;border-radius:2px;vertical-align:middle;margin-right:5px}
.bm{background:#a3361c;opacity:.55}.bn{background:#c9a227;opacity:.6}
tr.tot td{border-top:1.5px solid #1c221b;font-weight:700}
.nota{margin-top:10px;font-size:9.5px;color:#4f584b;line-height:1.45}
"""


def num(v):
    return f"{v:.2f}".replace(".", ",")


def pagina(tipo, r, idx, total):
    M, m = r["mayores"], r["menores"]
    filas_n = max(len(M), len(m))
    alto = max(18, min(26, (1123 - 76 - 30 - 86 - 12 - 16 - 20 - 26 - 60) // (filas_n + 1)))
    maxm = max((x[1] for x in M), default=1) or 1
    maxn = max((x[1] for x in m), default=1) or 1
    filas = []
    for i in range(filas_n):
        celdas = [f'<td class="n">{i + 1}</td>']
        for lista, cls, mx, barra, sep in ((M, "vm", maxm, "bm", ""), (m, "vn", maxn, "bn", " sep")):
            if i < len(lista):
                nombre, media, frec = lista[i]
                ancho = max(1, round(media / mx * 46))
                celdas += [f'<td class="l{sep}">{e(nombre.capitalize())}</td>',
                           f'<td class="{cls}"><span class="bar {barra}" style="width:{ancho}px"></span>{num(media)}</td>',
                           f'<td class="f">{round(frec * 100)}%</td>']
            else:
                celdas += [f'<td class="l{sep}"></td>', "<td></td>", "<td></td>"]
        filas.append(f'<tr style="height:{alto}px">{"".join(celdas)}</tr>')
    sm, sn = sum(x[1] for x in M), sum(x[1] for x in m)
    filas.append(f'<tr class="tot" style="height:{alto}px"><td></td><td class="l">Suma mayores</td>'
                 f'<td class="vm">{num(sm)}</td><td></td><td class="l sep">Suma menores</td>'
                 f'<td class="vn">{num(sn)}</td><td></td></tr>')
    anchos = [4, 26, 13, 7, 26, 13, 7]
    ths = "".join(f'<th class="{c}" style="width:{w}%">{t}</th>' for t, w, c in zip(
        ["#", "Problema mayor", "Media %", "% esc.", "Problema menor", "Media %", "% esc."], anchos,
        ["", "l", "", "", "l", "", ""]))
    cuerpo = f'''<div class="cab" style="--c:{COLOR.get(tipo, "#6b7466")}">
<div class="tit"><span class="lab">Problemas · todas las fincas y variedades</span><h1><i></i>{e(tipo.title())}</h1>
<p>{r["escandallos"]} escandallos · {len(M)} problemas mayores · {len(m)} problemas menores</p></div>
<div class="kpi may"><span class="lab">Suma mayores</span><b>{num(sm)}%</b><span>{e(M[0][0].capitalize()) if M else "—"} el primero</span></div>
<div class="kpi men"><span class="lab">Suma menores</span><b>{num(sn)}%</b><span>{e(m[0][0].capitalize()) if m else "—"} el primero</span></div>
</div>
<div class="grp"><span style="width:4%;border:0"></span><span class="gm" style="width:46%">Problemas mayores</span><span class="gn" style="width:46%">Problemas menores</span></div>
<table><thead><tr>{ths}</tr></thead><tbody>{"".join(filas)}</tbody></table>
<p class="nota"><b>Media %</b>: media del problema en todos los escandallos del tipo; cada escandallo pesa según sus melones medidos
(medidas de firmeza) y, si no tiene el problema, cuenta como 0 %. <b>% esc.</b>: en qué porcentaje de los escandallos del tipo aparece.
Datos de toda la temporada (el volcado no trae fecha de los problemas). El mismo problema con dos códigos va junto por nombre.</p>'''
    return (f'<div class="pg"><div class="cuerpo">{cuerpo}</div><div class="pie"><span>{TITULO} · <b>{e(tipo.title())}</b>'
            f'</span><span>Página {idx} de {total}</span></div></div>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--salida", default="Problemas por tipo melon 2026")
    args = ap.parse_args()

    res = medias_por_tipo(leer_bloques(args.volcado))
    paginas = [pagina(t, r, i, len(res)) for i, (t, r) in enumerate(res.items(), start=1)]
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{TITULO}</title>{FUENTES}'
           f'<style>{CSS}</style></head><body>{"".join(paginas)}</body></html>')
    ruta_html, ruta_pdf = Path(args.salida + ".html"), Path(args.salida + ".pdf")
    ruta_html.write_text(doc, encoding="utf-8")
    if os.path.exists(CHROME):
        subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={ruta_pdf.resolve()}", ruta_html.resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f"{len(paginas)} páginas -> {ruta_html}, {ruta_pdf}")


if __name__ == "__main__":
    main()
