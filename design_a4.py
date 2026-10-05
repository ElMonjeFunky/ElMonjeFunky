#!/usr/bin/env python3
"""Genera el informe A4 como lienzo de Design: una mesa de trabajo de 794x1123 px
(A4 a 96 ppp) por página, paginada aquí con alturas de fila fijas.

Uso:
    python3 design_a4.py VOLCADO.csv CARPETA_SALIDA

Escribe CARPETA_SALIDA/project/canvas.json y CARPETA_SALIDA/project/*.dc.html.
"""
import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

from informe_a4 import COLOR, celdas, corto, d, e, entero, escala, n, pct, portada
from tarjetas_completas import construir_semanas

W, H = 794, 1123
MARGEN_SUP, MARGEN_LAT, PIE = 40, 40, 44
UTIL = H - MARGEN_SUP - PIE - 12           # alto disponible para contenido
ALTO = {"cab_semana": 112, "tipo": 66, "var": 19, "finca": 15, "vacias_cab": 30, "vacias_fila": 34, "vacias_pie": 14}

CSS = """
body{margin:0}
a{color:#2e5935}a:hover{color:#1d3a22}
.pg{width:794px;height:1123px;box-sizing:border-box;padding:40px 40px 0;position:relative;overflow:hidden;background:#fff;color:#1c221b;font:12px/1.4 "Source Sans 3","Segoe UI",system-ui,sans-serif}
.pie{position:absolute;left:40px;right:40px;bottom:18px;display:flex;justify-content:space-between;border-top:1px solid #d9ded1;padding-top:6px;font-size:10px;color:#5f685a}
.pie b{color:#1c221b;font-weight:600}
.n{text-align:right;font-variant-numeric:tabular-nums}
.muted{color:#5f685a;font-weight:400}
.eyebrow{font:500 10px "IBM Plex Mono",monospace;letter-spacing:.08em;text-transform:uppercase;color:#5f685a}
h1{font:800 40px/1 "Bricolage Grotesque",system-ui,sans-serif;color:#2e5935;margin:8px 0 10px;letter-spacing:-.01em}
.lead{margin:0 0 14px;color:#5f685a;max-width:520px;font-size:12.5px}
.resumen{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:#d9ded1;border:1px solid #d9ded1;border-radius:6px;overflow:hidden;margin:0 0 16px}
.resumen div{background:#f3f5ef;padding:7px 10px}
.resumen dt,.counts dt{font:500 8.5px "IBM Plex Mono",monospace;letter-spacing:.07em;text-transform:uppercase;color:#5f685a}
.resumen dd{margin:0;font:700 19px "Bricolage Grotesque",sans-serif;font-variant-numeric:tabular-nums}
.resumen dd small{font:400 10px "IBM Plex Mono",monospace;color:#5f685a;margin-left:5px}
.cal-t{font:500 16px "Bricolage Grotesque",sans-serif;margin:0 0 7px}
.cal-t small,.vacias h2 small{font:400 10px "IBM Plex Mono",monospace;color:#5f685a;margin-left:6px}
.cal{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:4px}
.wk{display:grid;padding:4px 7px;border:1px solid #d9ded1;border-radius:4px;text-decoration:none;color:#1c221b;background:#e6eedf;line-height:1.25}
.wk b{font:700 12.5px "Bricolage Grotesque",sans-serif;color:#2e5935}
.wk span{font-size:9.5px;font-weight:600}
.wk em,.wk i{font:400 8.5px "IBM Plex Mono",monospace;font-style:normal;color:#5f685a}
.wk i{color:#1c221b}
.wk.off{background:#fff;border-style:dashed}
.wk.off b{color:#5f685a}
.leyenda{display:flex;flex-wrap:wrap;gap:4px 14px;margin:12px 0;font:500 9px "IBM Plex Mono",monospace;color:#5f685a;text-transform:uppercase;letter-spacing:.04em}
.leyenda span{display:inline-flex;gap:5px;align-items:center}
.leyenda i{width:9px;height:9px;border-radius:50%}
.notas{border-top:1px solid #d9ded1;padding-top:7px;display:grid;gap:4px;font-size:10px;color:#5f685a}
.notas p{margin:0}.notas b{color:#1c221b}
.vacias{margin-bottom:14px}
.vacias h2{font:600 17px/30px "Bricolage Grotesque",sans-serif;color:#5f685a;margin:0;height:30px}
.vacias ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:4px}
.vacias li{border:1px dashed #cfd5c6;border-radius:4px;padding:3px 7px;font-size:9.5px;display:grid;height:30px;box-sizing:border-box;line-height:1.2}
.vacias li b{font:700 11.5px "Bricolage Grotesque",sans-serif;color:#5f685a}
.sem-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 14px;align-items:end;background:#e6eedf;border-radius:8px;padding:10px 12px;margin-bottom:6px;height:106px;box-sizing:border-box}
.sem-id{display:flex;gap:10px;align-items:baseline}
.sem-n{font:800 38px/0.9 "Bricolage Grotesque",sans-serif;color:#2e5935}
.sem-r{font:700 15px "Source Sans 3",sans-serif}
.sem-r small{display:block;font:400 9.5px "IBM Plex Mono",monospace;color:#5f685a}
.counts{display:flex;gap:16px;margin:0;grid-column:1}
.counts dd{margin:0;font:700 16px "Bricolage Grotesque",sans-serif;font-variant-numeric:tabular-nums}
.kpis{grid-column:2;grid-row:1 / span 2;display:flex;gap:6px;align-self:stretch}
.kpi{background:#fff;border:1px solid #d9ded1;border-radius:6px;padding:6px 9px;width:168px;box-sizing:border-box;display:grid;gap:2px;align-content:start}
.kpi .lab{font:500 8.5px "IBM Plex Mono",monospace;letter-spacing:.07em;text-transform:uppercase;color:#5f685a;display:flex;justify-content:space-between;gap:6px}
.kpi .big{font:800 23px/1 "Bricolage Grotesque",sans-serif;font-variant-numeric:tabular-nums}
.kpi .big small{font:400 10px "IBM Plex Mono",monospace;color:#5f685a;margin-left:4px}
.kpi.fz .big{color:#2e5935}.kpi.az .big{color:#b0561a}
.delta{font:500 9.5px "IBM Plex Mono",monospace}.delta.up{color:#2e7d4f}.delta.down{color:#b5482c}
.tag{font:500 8px "IBM Plex Mono",monospace;text-transform:uppercase;padding:0 4px;border-radius:3px;background:#fbe9d8;color:#a24e15;letter-spacing:.04em}
.bandas{display:grid;grid-template-columns:repeat(4,auto);gap:4px;font:500 10px "IBM Plex Mono",monospace}
.bandas em{display:block;font-style:normal;font-size:8px;color:#5f685a}
.tipo{margin-top:8px}
.tipo h3{display:flex;align-items:baseline;gap:8px;margin:0;height:22px;line-height:20px;border-bottom:2px solid var(--c);font:600 12px "IBM Plex Mono",monospace;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap;overflow:hidden;box-sizing:border-box}
.dot{width:9px;height:9px;border-radius:50%;background:var(--c);display:inline-block;align-self:center;flex:none}
.tipo h3 .sub{font:400 9.5px "IBM Plex Mono",monospace;color:#5f685a;letter-spacing:0;text-transform:none;overflow:hidden;text-overflow:ellipsis}
.tipo h3 .sub b{color:#1c221b;font-weight:500}
.tipo h3 .cont{font:400 9.5px "IBM Plex Mono",monospace;color:#5f685a;text-transform:none;letter-spacing:0}
table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:10px}
col.c-var{width:27%}col.c-n{width:5.4%}col.c-mm{width:8.6%}col.c-bar{width:8.6%}col.c-b{width:5.2%}
th{font:500 8px "IBM Plex Mono",monospace;letter-spacing:.05em;text-transform:uppercase;color:#5f685a;text-align:left;padding:0 3px;height:17px;white-space:nowrap}
th.n{text-align:right}
tr.grp th{text-align:center;height:15px}
th.g-fz{color:#2e5935;border-bottom:1px solid #d9ded1}th.g-az{color:#a24e15;border-bottom:1px solid #d9ded1}
td{padding:0 3px;vertical-align:middle;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
td.n{font-family:"IBM Plex Mono",monospace;font-size:9.5px}
tr.var td{border-top:1px solid #d9ded1;height:18px;font-weight:600}
tr.var td.n{font-weight:500}
tr.var .code{font:500 9px "IBM Plex Mono",monospace;padding:0 4px;border-radius:3px;background:color-mix(in srgb,var(--c) 16%,white);border:1px solid color-mix(in srgb,var(--c) 50%,transparent)}
tr.finca td{color:#5f685a;font-size:9.5px;height:15px}
tr.finca td:first-child{padding-left:16px}
tr.finca td.n{font-size:9px}
tr.finca .cod{font:400 8px "IBM Plex Mono",monospace}
.cat{font:500 7.5px "IBM Plex Mono",monospace;border:1px solid #d9ded1;border-radius:2px;padding:0 3px}
td.fzv{color:#2e5935}td.azv{color:#b0561a}
tr.finca td.fzv,tr.finca td.azv{color:#5f685a}
td.mm,td.b{color:#5f685a}td.b.hi{color:#1c221b}
.scale{position:relative;display:inline-block;height:7px;border-radius:3px;background:#f3f5ef;border:1px solid #d9ded1;vertical-align:middle}
.scale .r{position:absolute;top:1px;bottom:1px;border-radius:2px;background:#2e5935;opacity:.32}
.scale .m{position:absolute;top:-2px;width:2px;height:9px;margin-left:-1px;background:#2e5935;border-radius:1px}
.kpi .scale{width:100%;height:8px;margin:2px 0}
tr.finca .scale{opacity:.6}
"""

FUENTES = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;'
           '12..96,800&amp;family=Source+Sans+3:wght@400;600;700&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap">')


def thead():
    return ('<colgroup><col class="c-var"><col class="c-n"><col class="c-n"><col class="c-n"><col class="c-n"><col class="c-mm">'
            '<col class="c-bar"><col class="c-n"><col class="c-mm"><col class="c-b"><col class="c-b"><col class="c-b"><col class="c-b"></colgroup>'
            '<thead><tr class="grp"><th colspan="4"></th><th colspan="3" class="g-fz">Firmeza (1–5)</th>'
            '<th colspan="6" class="g-az">Azúcar °Brix · temporada</th></tr>'
            '<tr><th>Variedad / finca</th><th class="n">Fincas</th><th class="n">Alb.</th><th class="n">Medidas</th>'
            '<th class="n">Media</th><th class="n">Mín–máx</th><th></th><th class="n">Medio</th><th class="n">Mín–máx</th>'
            '<th class="n">&lt;9</th><th class="n">9–10</th><th class="n">10–12</th><th class="n">≥12</th></tr></thead>')


def grupo_html(v):
    nombre = e(v["nombre"]) if v["nombre"] else '<span class="muted">sin nombre</span>'
    filas = [f'<tr class="var"><td><span class="code">{e(v["codigo"])}</span> <b>{nombre}</b></td>'
             f'<td class="n">{v["fincas"]}</td>{celdas(v)}</tr>']
    for f in v["fincas_detalle"]:
        cat = f' <span class="cat">{e(f["cat"])}</span>' if f["cat"] else ""
        filas.append(f'<tr class="finca"><td>{e(f["finca"])} <span class="cod">{e(f["cod"])}</span>{cat}</td>'
                     f'<td></td>{celdas(f)}</tr>')
    return "".join(filas)


def tipo_cab(t, continua):
    S = t["total"]
    fz, az, bd = S["firmeza"], S["azucar"], S["bandas"]
    if continua:
        sub = '<span class="cont">(continuación)</span>'
    else:
        sub = (f'<span class="sub">{len(t["variedades"])} var. · {S["fincas"]} fincas · {S["albaranes"]} alb. · '
               f'{S["medidas"]} medidas firmeza · firmeza <b>{n(fz[0], 2)}</b> · Brix <b>{n(az[0]) if az else "—"}</b>'
               f' · ≥12 <b>{pct(bd[3]) if bd else "—"}</b></span>')
    return f'<h3><span class="dot"></span>{e(t["tipo"])}{sub}</h3>'


def cab_semana(s):
    T = s["total"]
    ini, fin = d(s["desde"]), d(s["hasta"])
    delta = ""
    if s["firmeza_anterior"] is not None:
        dif = T["firmeza"][0] - s["firmeza_anterior"]
        delta = (f'<span class="delta {"up" if dif >= 0 else "down"}">{"▲" if dif >= 0 else "▼"} '
                 f'{n(abs(dif), 2)} vs semana anterior</span>')
    bd = T["bandas"]
    bandas = "".join(f'<span><em>{l}</em>{pct(bd[i]) if bd else "—"}</span>'
                     for i, l in enumerate(["&lt;9", "9–10", "10–12", "≥12"]))
    az = T["azucar"]
    return f'''<header class="sem-head">
<div class="sem-id"><span class="sem-n">{s["etiqueta"]}</span><span class="sem-r">{corto(ini)} – {corto(fin)} {fin.year}<small>lunes {s["desde"]} · domingo {s["hasta"]}</small></span></div>
<dl class="counts"><div><dt>Tipos</dt><dd>{len(s["tipos"])}</dd></div><div><dt>Variedades</dt><dd>{s["variedades"]}</dd></div><div><dt>Fincas</dt><dd>{T["fincas"]}</dd></div><div><dt>Albaranes</dt><dd>{T["albaranes"]}</dd></div><div><dt>Medidas firmeza</dt><dd>{entero(T["medidas"])}</dd></div></dl>
<div class="kpis">
<div class="kpi fz"><div class="lab">Firmeza media (1–5)</div><div class="big">{n(T["firmeza"][0], 2)}<small>{n(T["firmeza"][1])}–{n(T["firmeza"][2])}</small></div>{escala(T["firmeza"])}{delta}</div>
<div class="kpi az"><div class="lab">Brix medio <span class="tag">temporada</span></div><div class="big">{n(az[0]) if az else "—"}<small>{f"{n(az[1])}–{n(az[2])}" if az else ""}</small></div><div class="bandas">{bandas}</div></div>
</div>
</header>'''


def vacias_html(grupo):
    ini, fin = d(grupo[0]["desde"]), d(grupo[-1]["hasta"])
    chips = "".join(f'<li><b>{s["etiqueta"]}</b>{corto(d(s["desde"]))} – {corto(d(s["hasta"]))}</li>' for s in grupo)
    return (f'<section class="vacias"><h2>{grupo[0]["etiqueta"]}–{grupo[-1]["etiqueta"]} <small>{corto(ini)} {ini.year} – '
            f'{corto(fin)} {fin.year} · sin escandallos</small></h2><ul>{chips}</ul></section>')


def alto_vacias(grupo):
    return ALTO["vacias_cab"] + math.ceil(len(grupo) / 6) * ALTO["vacias_fila"] + ALTO["vacias_pie"]


class Paginador:
    """Va llenando páginas de UTIL px; cada página guarda su HTML y su etiqueta."""

    def __init__(self):
        self.paginas, self.html, self.usado, self.etiqueta = [], [], 0, ""
        self.tabla_abierta = False

    def cerrar_tabla(self):
        if self.tabla_abierta:
            self.html.append("</table></section>")
            self.tabla_abierta = False

    def nueva(self):
        self.cerrar_tabla()
        if self.html:
            self.paginas.append((self.etiqueta, "".join(self.html)))
        self.html, self.usado = [], 0

    def cabe(self, alto):
        return self.usado + alto <= UTIL

    def poner(self, html, alto):
        self.html.append(html)
        self.usado += alto


def paginar(semanas):
    p = Paginador()
    vacias = []

    def volcar_vacias():
        nonlocal vacias
        if vacias:
            if not p.cabe(alto_vacias(vacias)):
                p.nueva()
            p.etiqueta = p.etiqueta or f'{vacias[0]["etiqueta"]}–{vacias[-1]["etiqueta"]}'
            p.poner(vacias_html(vacias), alto_vacias(vacias))
            vacias = []

    for s in semanas:
        if not s["total"]:
            if not vacias:
                p.nueva()
                p.etiqueta = ""
            vacias.append(s)
            continue
        if vacias:
            volcar_vacias()
            if not p.cabe(ALTO["cab_semana"] + ALTO["tipo"] + 4 * ALTO["var"]):
                p.nueva()
        else:
            p.nueva()
        p.etiqueta = s["etiqueta"] if not p.etiqueta or p.usado == 0 else f'{p.etiqueta} · {s["etiqueta"]}'
        p.poner(cab_semana(s), ALTO["cab_semana"])
        for t in s["tipos"]:
            primera = True
            for v in t["variedades"]:
                alto_g = ALTO["var"] + ALTO["finca"] * len(v["fincas_detalle"])
                necesita = alto_g + (0 if p.tabla_abierta else ALTO["tipo"])
                if not p.cabe(necesita):
                    p.nueva()
                    p.etiqueta = f'{s["etiqueta"]} (cont.)'
                if not p.tabla_abierta:
                    p.html.append(f'<section class="tipo" style="--c:{COLOR.get(t["tipo"], "#7a8075")}">'
                                  f'{tipo_cab(t, not primera)}<table>{thead()}')
                    p.usado += ALTO["tipo"]
                    p.tabla_abierta = True
                p.poner(f"<tbody>{grupo_html(v)}</tbody>", alto_g)
                primera = False
            p.cerrar_tabla()
    volcar_vacias()
    p.nueva()
    return p.paginas


def artboard(titulo, cuerpo, pie_izq, num, total):
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
<div class="pg">
{cuerpo}
<footer class="pie"><span>Escandallo semanal de melón 2026 · <b>{e(pie_izq)}</b></span><span>Página {num} de {total}</span></footer>
</div>
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
    ap.add_argument("salida", type=Path)
    args = ap.parse_args()

    semanas, bloques = construir_semanas(args.volcado)
    paginas = paginar(semanas)
    total = len(paginas) + 1
    nombres = ["Main.dc.html"] + [f"P{i:02d}.dc.html" for i in range(2, total + 1)]

    # Enlaces del calendario de la portada a la primera página de cada semana
    primera = {}
    for i, (etq, _) in enumerate(paginas, start=2):
        for parte in etq.replace(" (cont.)", "").split(" · "):
            if parte.startswith("S") and "–" not in parte:
                primera.setdefault(parte, nombres[i - 1])
    cuerpo_portada = portada(semanas, bloques, args.volcado.name)
    for etq, fichero in primera.items():
        cuerpo_portada = cuerpo_portada.replace(f'href="#{etq}"', f'href="{fichero}"')
    cuerpo_portada = cuerpo_portada.replace('<section class="portada">', "").rsplit("</section>", 1)[0]

    proyecto = args.salida / "project"
    proyecto.mkdir(parents=True, exist_ok=True)
    (proyecto / "Main.dc.html").write_text(artboard("Portada", cuerpo_portada, "Portada", 1, total), encoding="utf-8")
    boards, por_fila = {}, 6
    for i, nombre in enumerate(nombres):
        etq = "Portada" if i == 0 else paginas[i - 1][0]
        boards[nombre] = {"x": (i % por_fila) * (W + 80), "y": (i // por_fila) * (H + 120), "w": W, "h": H,
                          "title": f"{i + 1} · {etq}", "paper": "a4"}
        if i:
            (proyecto / nombre).write_text(artboard(f"Página {i + 1} · {etq}", paginas[i - 1][1], etq, i + 1, total),
                                           encoding="utf-8")
    indice = {"v": 3, "createdOnFiles": {"v": 1, "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
              "title": "Escandallo semanal melón 2026", "launch": {"view": "canvas"}, "pages": [],
              "boards": boards, "order": nombres, "notes": {}, "designSystems": []}
    (proyecto / "canvas.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{total} páginas -> {proyecto}", file=sys.stderr)


if __name__ == "__main__":
    main()
