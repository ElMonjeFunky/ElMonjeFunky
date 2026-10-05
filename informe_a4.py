#!/usr/bin/env python3
"""Informe imprimible A4 del escandallo de melón 2026: portada con las 53 semanas
y UNA página por semana con datos (tipo -> variedad), sin cortes entre páginas.

Uso:
    python3 informe_a4.py VOLCADO.csv [--salida "Escandallo semanal melon 2026"] [--lienzo CARPETA]

Genera <salida>.html y <salida>.pdf (A4, una hoja por página). Con --lienzo
escribe además las mismas páginas como mesas de trabajo de Design en
CARPETA/project/ (canvas.json + *.dc.html).

Cada página mide 794x1123 px (A4 a 96 ppp). Las filas tienen alto fijo y los
textos largos se recortan con «…», así que nada se superpone. El alto de fila
se ajusta para que la semana entera quepa en su página.
"""
import argparse
import datetime as dt
import html
import json
import os
import subprocess
from pathlib import Path

from escandallo import bandas_azucar, estadisticas
from tarjetas_completas import construir_semanas

W, H = 794, 1123
PAD = 38                       # margen de la hoja
PIE = 30                       # alto del pie
CAB = 92                       # alto de la cabecera de semana
THEAD = 34                     # dos filas de cabecera de tabla
UTIL_TABLA = H - 2 * PAD - PIE - CAB - 10 - THEAD
FILA_MAX, FILA_MIN = 21, 15

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
COLOR = {"AMARILLO": "#c99700", "CANTALOUPE": "#d9701f", "CHARENTAIS": "#c0502a", "GALIA": "#5f8f22",
         "GALIA LARGA VIDA": "#2a7d62", "IVORY GAYA": "#8f8160", "ORANGE CANDY": "#d65640",
         "PIEL DE SAPO": "#2e5935", "SUNUP": "#a87a20"}
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
TITULO = "Escandallo semanal de melón 2026"

e = html.escape


def d(dmy):
    return dt.datetime.strptime(dmy, "%d/%m/%Y").date()


def corto(f):
    return f"{f.day} {MESES[f.month - 1]}"


def n(v, dec=1):
    return "—" if v is None else f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v):
    return "—" if v is None else f"{round(v * 100)}%"


def entero(v):
    return f"{v:,}".replace(",", ".")


def escala(f):
    """Barra de firmeza en la escala 1-5: rango mín-máx y marca en la media."""
    if not f:
        return ""
    pos = lambda v: (min(max(v, 1), 5) - 1) / 4 * 100
    return (f'<span class="scale"><i class="r" style="left:{pos(f[1]):.1f}%;right:{100 - pos(f[2]):.1f}%"></i>'
            f'<i class="m" style="left:{pos(f[0]):.1f}%"></i></span>')


CSS = """
body{margin:0;background:#fff}
a{color:#2e5935}a:hover{color:#1d3a22}
.pg{width:794px;height:1123px;box-sizing:border-box;padding:38px 38px 0;display:flex;flex-direction:column;overflow:hidden;background:#fff;color:#1c221b;font:11px/1.35 "Source Sans 3","Segoe UI",Arial,sans-serif}
.cuerpo{flex:1;min-height:0;overflow:hidden}
.pie{flex:none;height:30px;box-sizing:border-box;display:flex;justify-content:space-between;align-items:center;border-top:1px solid #cdd3c4;font-size:9.5px;color:#4f584b}
.pie b{color:#1c221b;font-weight:600}
.clip{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mono{font-family:"IBM Plex Mono",Consolas,monospace}
.lab{font:500 8px "IBM Plex Mono",Consolas,monospace;letter-spacing:.06em;text-transform:uppercase;color:#4f584b}
/* portada */
.eyebrow{font:500 9px "IBM Plex Mono",Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;color:#4f584b}
.h1{font:800 34px/1.05 "Bricolage Grotesque","Segoe UI",Arial,sans-serif;color:#2e5935;margin:6px 0 6px}
.lead{margin:0 0 12px;color:#4f584b;font-size:11.5px;max-width:560px}
.resumen{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:#cdd3c4;border:1px solid #cdd3c4;border-radius:5px;overflow:hidden;margin-bottom:14px}
.resumen div{background:#f3f5ef;padding:6px 9px;height:46px;box-sizing:border-box;overflow:hidden}
.resumen b{display:block;font:700 17px/1.2 "Bricolage Grotesque","Segoe UI",Arial,sans-serif;white-space:nowrap}
.resumen b small{font:400 9px "IBM Plex Mono",Consolas,monospace;color:#4f584b;margin-left:4px}
.cal-t{display:flex;justify-content:space-between;align-items:baseline;margin:0 0 6px;font:600 14px "Bricolage Grotesque","Segoe UI",Arial,sans-serif}
.cal{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:4px}
.wk{display:block;height:58px;box-sizing:border-box;padding:4px 6px;border:1px solid #cdd3c4;border-radius:4px;text-decoration:none;color:#1c221b;background:#e6eedf;overflow:hidden;line-height:13px}
.wk b{display:block;font:700 12px/14px "Bricolage Grotesque","Segoe UI",Arial,sans-serif;color:#2e5935}
.wk span{display:block;font-size:9px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wk em{display:block;font:400 8px/12px "IBM Plex Mono",Consolas,monospace;font-style:normal;color:#4f584b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wk.off{background:#fff;border-style:dashed}.wk.off b{color:#6b7466}
.leyenda{display:flex;flex-wrap:wrap;gap:3px 12px;margin:10px 0;font:500 8px "IBM Plex Mono",Consolas,monospace;color:#4f584b;text-transform:uppercase}
.leyenda span{display:inline-flex;gap:4px;align-items:center}.leyenda i{width:8px;height:8px;border-radius:50%;display:inline-block}
.notas{border-top:1px solid #cdd3c4;padding-top:6px;font-size:9.5px;color:#4f584b}
.notas p{margin:0 0 3px}.notas b{color:#1c221b}
/* semana */
.sh{height:92px;box-sizing:border-box;display:grid;grid-template-columns:minmax(0,1fr) 168px 168px;gap:8px;margin-bottom:10px}
.sh-a{background:#e6eedf;border-radius:6px;padding:8px 10px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden}
.sh-t{display:flex;gap:10px;align-items:baseline;white-space:nowrap;overflow:hidden}
.sh-n{font:800 32px/1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif;color:#2e5935}
.sh-r{font:700 14px/1.1 "Source Sans 3","Segoe UI",Arial,sans-serif}
.sh-r small{display:block;font:400 8.5px/1.4 "IBM Plex Mono",Consolas,monospace;color:#4f584b}
.cnt{display:flex;gap:14px;white-space:nowrap}
.cnt div{display:flex;flex-direction:column}
.cnt b{font:700 14px/1.1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif}
.kpi{border:1px solid #cdd3c4;border-radius:6px;padding:7px 9px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden}
.kpi .big{font:800 22px/1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif;white-space:nowrap}
.kpi .big small{font:400 9px "IBM Plex Mono",Consolas,monospace;color:#4f584b;margin-left:4px}
.kpi.fz .big{color:#2e5935}.kpi.az .big{color:#a24e15}
.delta{font:500 8.5px "IBM Plex Mono",Consolas,monospace;white-space:nowrap}.up{color:#2e7d4f}.down{color:#b5482c}
.tag{font:500 7px "IBM Plex Mono",Consolas,monospace;text-transform:uppercase;padding:0 3px;border-radius:2px;background:#fbe9d8;color:#a24e15}
.bandas{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));font:500 9px/1.2 "IBM Plex Mono",Consolas,monospace;white-space:nowrap}
.bandas em{display:block;font-style:normal;font-size:7px;color:#4f584b}
.kpi .scale{width:100%;height:7px}
table{width:100%;border-collapse:collapse;table-layout:fixed}
col.c-v{width:33%}col.c-s{width:3.6%}col.c-f{width:5.4%}col.c-mm{width:9%}col.c-bar{width:7%}col.c-b{width:4.4%}
th{height:17px;padding:0 3px;font:500 7.5px/17px "IBM Plex Mono",Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;color:#4f584b;text-align:right;white-space:nowrap;overflow:hidden}
th.l{text-align:left}
tr.g th{text-align:center;border-bottom:1px solid #cdd3c4}
th.gfz{color:#2e5935}th.gaz{color:#a24e15}
td{padding:0 3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right;font:400 9.5px "IBM Plex Mono",Consolas,monospace;border-top:1px solid #e3e7dc;box-sizing:border-box}
td.l{text-align:left;font:400 10px "Source Sans 3","Segoe UI",Arial,sans-serif}
tr.t td{background:color-mix(in srgb,var(--c) 14%,white);border-top:1.5px solid var(--c);font-weight:600}
tr.t td.l{font:700 9.5px "IBM Plex Mono",Consolas,monospace;letter-spacing:.05em;text-transform:uppercase}
tr.t td.l i{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--c);margin-right:5px;vertical-align:baseline}
tr.v td.l .code{font:500 8.5px "IBM Plex Mono",Consolas,monospace;color:#4f584b;margin-right:5px}
tr.v td.l b{font-weight:600}tr.v td.l b.lg{font-size:8.5px;letter-spacing:-.01em}
td.fz{color:#2e5935;font-weight:500}td.az{color:#a24e15;font-weight:500}
td.mm,td.b{color:#4f584b}td.hi{color:#1c221b;font-weight:500}
td.bar{text-align:left}
.scale{position:relative;display:inline-block;width:100%;height:6px;border-radius:3px;background:#f3f5ef;border:1px solid #cdd3c4;vertical-align:middle;box-sizing:border-box}
.scale .r{position:absolute;top:1px;bottom:1px;border-radius:2px;background:#2e5935;opacity:.3}
.scale .m{position:absolute;top:-2px;width:2px;height:8px;margin-left:-1px;background:#2e5935}
"""

FUENTES = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;'
           '12..96,800&amp;family=Source+Sans+3:wght@400;600;700&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap">')


def fila(clase, primera, r, estilo=""):
    fz, az, bd = r["firmeza"], r["azucar"], r["bandas"]
    c = [f'<td class="l">{primera}</td>', f'<td>{r["fincas"]}</td>', f'<td>{r["albaranes"]}</td>',
         f'<td>{entero(r["medidas"])}</td>']
    c += ([f'<td class="fz">{n(fz[0], 2)}</td>', f'<td class="mm">{n(fz[1])}–{n(fz[2])}</td>',
           f'<td class="bar">{escala(fz)}</td>'] if fz else ["<td>—</td>", "<td></td>", "<td></td>"])
    c += ([f'<td class="az">{n(az[0])}</td>', f'<td class="mm">{n(az[1])}–{n(az[2])}</td>'] if az
          else ["<td>—</td>", "<td></td>"])
    c += [f'<td class="b{" hi" if i == 3 else ""}">{pct(bd[i]) if bd else "—"}</td>' for i in range(4)]
    return f'<tr class="{clase}"{estilo}>{"".join(c)}</tr>'


def tabla_semana(s):
    filas = sum(1 + len(t["variedades"]) for t in s["tipos"])
    alto = max(FILA_MIN, min(FILA_MAX, UTIL_TABLA // filas))
    cuerpo = []
    for t in s["tipos"]:
        cuerpo.append(fila("t", f'<i></i>{e(t["tipo"])} · {len(t["variedades"])} var.', t["total"],
                           f' style="--c:{COLOR.get(t["tipo"], "#6b7466")}"'))
        for v in t["variedades"]:
            nombre = e(v["nombre"]) if v["nombre"] else "sin nombre"
            largo = ' class="lg"' if len(v["codigo"]) + len(v["nombre"]) > 30 else ""
            cuerpo.append(fila("v", f'<span class="code">{e(v["codigo"])}</span><b{largo}>{nombre}</b>', v))
    return (f'<style>.s-{s["etiqueta"]} td{{height:{alto}px}}</style>'
            f'<table class="s-{s["etiqueta"]}"><colgroup><col class="c-v"><col class="c-s"><col class="c-s"><col class="c-f">'
            '<col class="c-f"><col class="c-mm"><col class="c-bar"><col class="c-f"><col class="c-mm">'
            '<col class="c-b"><col class="c-b"><col class="c-b"><col class="c-b"></colgroup>'
            '<thead><tr class="g"><th colspan="4"></th><th colspan="3" class="gfz">Firmeza · escala 1–5</th>'
            '<th colspan="6" class="gaz">Azúcar °Brix · temporada</th></tr>'
            '<tr><th class="l">Tipo / variedad</th><th>Fin.</th><th>Alb.</th><th>Medidas</th><th>Media</th>'
            '<th>Mín–máx</th><th></th><th>Medio</th><th>Mín–máx</th><th>&lt;9</th><th>9–10</th><th>10–12</th>'
            f'<th>≥12</th></tr></thead><tbody>{"".join(cuerpo)}</tbody></table>')


def pagina_semana(s):
    T = s["total"]
    ini, fin = d(s["desde"]), d(s["hasta"])
    delta = ""
    if s["firmeza_anterior"] is not None:
        dif = T["firmeza"][0] - s["firmeza_anterior"]
        delta = (f'<span class="delta {"up" if dif >= 0 else "down"}">{"▲" if dif >= 0 else "▼"} '
                 f'{n(abs(dif), 2)} vs semana anterior</span>')
    else:
        delta = '<span class="delta">&#160;</span>'
    bd, az = T["bandas"], T["azucar"]
    bandas = "".join(f'<span><em>{l}</em>{pct(bd[i]) if bd else "—"}</span>'
                     for i, l in enumerate(["&lt;9", "9–10", "10–12", "≥12"]))
    cnt = "".join(f'<div><span class="lab">{k}</span><b>{v}</b></div>' for k, v in [
        ("Tipos", len(s["tipos"])), ("Variedades", s["variedades"]), ("Fincas", T["fincas"]),
        ("Albaranes", T["albaranes"]), ("Medidas firmeza", entero(T["medidas"]))])
    cab = f'''<div class="sh">
<div class="sh-a"><div class="sh-t"><span class="sh-n">{s["etiqueta"]}</span><span class="sh-r">{corto(ini)} – {corto(fin)} {fin.year}<small>lunes {s["desde"]} · domingo {s["hasta"]}</small></span></div>
<div class="cnt">{cnt}</div></div>
<div class="kpi fz"><span class="lab">Firmeza media</span><span class="big">{n(T["firmeza"][0], 2)}<small>{n(T["firmeza"][1])}–{n(T["firmeza"][2])}</small></span>{escala(T["firmeza"])}{delta}</div>
<div class="kpi az"><span class="lab">Brix medio <span class="tag">temporada</span></span><span class="big">{n(az[0]) if az else "—"}<small>{f"{n(az[1])}–{n(az[2])}" if az else ""}</small></span><div class="bandas">{bandas}</div></div>
</div>'''
    return cab + tabla_semana(s)


def pagina_portada(semanas, bloques, origen, enlaces):
    con = [s for s in semanas if s["total"]]
    fechas = [f for b in bloques for f, _, _ in b["firmeza"]]
    fv = [v for b in bloques for _, _, v in b["firmeza"]]
    az, bd = estadisticas(bloques), bandas_azucar(bloques)
    celdas = []
    for s in semanas:
        ini, fin = d(s["desde"]), d(s["hasta"])
        if s["total"]:
            T = s["total"]
            href = enlaces.get(s["etiqueta"], "")
            celdas.append(f'<a class="wk" href="{href}"><b>{s["etiqueta"]}</b><span>{corto(ini)} – {corto(fin)}</span>'
                          f'<em>{s["variedades"]} var · {T["fincas"]} fincas</em>'
                          f'<em>F {n(T["firmeza"][0], 2)} · B {n(T["azucar"][0]) if T["azucar"] else "—"}</em></a>')
        else:
            celdas.append(f'<div class="wk off"><b>{s["etiqueta"]}</b><span>{corto(ini)} – {corto(fin)}</span>'
                          f'<em>sin escandallos</em></div>')
    resumen = "".join(f'<div><span class="lab">{k}</span><b>{v}</b></div>' for k, v in [
        ("Semanas con datos", f"{len(con)}<small>de 53</small>"), ("Periodo", f"{corto(min(fechas))} – {corto(max(fechas))}"),
        ("Escandallos", len(bloques)), ("Variedades", len({b["variedad"] for b in bloques})),
        ("Fincas", len({b["cod_finca"] for b in bloques})), ("Medidas firmeza", entero(len(fv))),
        ("Firmeza media", n(sum(fv) / len(fv), 2)), ("Brix medio", f"{n(az[0])}<small>≥12: {pct(bd[3])}</small>")])
    leyenda = "".join(f'<span><i style="background:{c}"></i>{t}</span>' for t, c in COLOR.items())
    return f'''<div class="eyebrow">Control de calidad · Melón · {e(origen)}</div>
<div class="h1">Escandallo semanal de melón 2026</div>
<p class="lead">Una página por semana (lunes a domingo) con los tipos de melón y variedades escandallados: fincas, albaranes,
medidas de firmeza, firmeza de esa semana y azúcar (°Brix) de temporada de esas fincas.</p>
<div class="resumen">{resumen}</div>
<div class="cal-t"><span>Las 53 semanas</span><span class="lab">F = firmeza media · B = Brix medio</span></div>
<div class="cal">{"".join(celdas)}</div>
<div class="leyenda">{leyenda}</div>
<div class="notas">
<p><b>Firmeza:</b> medidas de firmeza de esa semana, escala 1–5; la barra va del mínimo al máximo y la marca es la media. «Medidas» cuenta solo medidas de firmeza. Se excluyen 5 medidas fuera de escala (23, 27, 33, 41, 45: falta la coma).</p>
<p><b>Azúcar:</b> el volcado no trae fecha para el azúcar: se da el de toda la temporada de esas fincas y variedad. Rangos calculados con los valores de °Brix uno a uno (el 12 exacto va en ≥12). No se da el nº de muestras de azúcar porque el volcado no lo trae.</p>
<p><b>Filas de tipo</b> (sombreadas): totales del tipo esa semana. El detalle por finca está en el Excel «informe_escandallo_melon_2026.xlsx».</p>
</div>'''


def hoja(cuerpo, etiqueta, num, total):
    return (f'<div class="pg"><div class="cuerpo">{cuerpo}</div><div class="pie"><span>{TITULO} · <b>{e(etiqueta)}</b></span>'
            f'<span>Página {num} de {total}</span></div></div>')


def artboard(titulo, contenido):
    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{e(titulo)}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
{FUENTES}
<style>{CSS}</style>
</helmet>
{contenido}
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{W},"height":{H}}}}}'>
class Component extends DCLogic {{
renderVals() {{
return {{}};
}}
}}
</script>
</body>
</html>
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--salida", default="Escandallo semanal melon 2026")
    ap.add_argument("--lienzo", type=Path)
    args = ap.parse_args()

    semanas, bloques = construir_semanas(args.volcado)
    con = [s for s in semanas if s["total"]]
    total = len(con) + 1
    ficheros = {s["etiqueta"]: f'{s["etiqueta"]}.dc.html' for s in con}

    def paginas(enlaces):
        yield "Portada", "Portada", pagina_portada(semanas, bloques, args.volcado.name, enlaces)
        for s in con:
            ini, fin = d(s["desde"]), d(s["hasta"])
            yield s["etiqueta"], f'{s["etiqueta"]} · {corto(ini)} – {corto(fin)}', pagina_semana(s)

    # Versión imprimible
    hojas = [hoja(c, etq, i, total) for i, (_, etq, c) in enumerate(paginas({}), start=1)]
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{TITULO}</title>{FUENTES}'
           f'<style>@page{{size:A4;margin:0}}{CSS}.pg{{break-after:page}}.pg:last-child{{break-after:auto}}'
           f'@media screen{{html,body{{background:#e3e6dd}}.pg{{margin:16px auto;box-shadow:0 1px 4px rgb(0 0 0/.15)}}}}</style>'
           f'</head><body>{"".join(hojas)}</body></html>')
    ruta_html, ruta_pdf = Path(args.salida + ".html"), Path(args.salida + ".pdf")
    ruta_html.write_text(doc, encoding="utf-8")
    if os.path.exists(CHROME):
        subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={ruta_pdf.resolve()}", ruta_html.resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f"{total} páginas -> {ruta_html}, {ruta_pdf}")

    # Lienzo de Design: una mesa de trabajo por página
    if args.lienzo:
        proyecto = args.lienzo / "project"
        proyecto.mkdir(parents=True, exist_ok=True)
        for viejo in proyecto.glob("*.dc.html"):
            viejo.unlink()
        enlaces = {etq: f for etq, f in ficheros.items()}
        nombres, boards = [], {}
        for i, (clave, etq, c) in enumerate(paginas(enlaces)):
            nombre = "Main.dc.html" if clave == "Portada" else ficheros[clave]
            nombres.append(nombre)
            (proyecto / nombre).write_text(artboard(f"{TITULO} · {etq}", hoja(c, etq, i + 1, total)), encoding="utf-8")
            boards[nombre] = {"x": (i % 6) * (W + 80), "y": (i // 6) * (H + 120), "w": W, "h": H,
                              "title": f"{i + 1} · {etq}", "paper": "a4"}
        indice = {"v": 3, "createdOnFiles": {"v": 1, "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                  "title": "Escandallo semanal melón 2026", "launch": {"view": "canvas"}, "pages": [],
                  "boards": boards, "order": nombres, "notes": {}, "designSystems": []}
        (proyecto / "canvas.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"lienzo: {len(nombres)} mesas -> {proyecto}")


if __name__ == "__main__":
    main()
