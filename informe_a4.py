#!/usr/bin/env python3
"""Informe A4 del escandallo de melón 2026: portada con las 53 semanas y una
sección por semana (tipos -> variedades -> fincas) con firmeza y azúcar.

Uso:
    python3 informe_a4.py VOLCADO.csv [--salida "Escandallo semanal melon 2026"]

Genera <salida>.html (A4, listo para imprimir) y <salida>.pdf (con Chromium).
"""
import argparse
import datetime as dt
import html
import os
import subprocess
from pathlib import Path

from escandallo import AQUI, bandas_azucar, estadisticas
from tarjetas_completas import construir_semanas

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
                "Septiembre", "Octubre", "Noviembre", "Diciembre"]
COLOR = {"AMARILLO": "#d9a400", "CANTALOUPE": "#e07b2a", "CHARENTAIS": "#c9572f", "GALIA": "#6f9e2b",
         "GALIA LARGA VIDA": "#2f8a6c", "IVORY GAYA": "#a39470", "ORANGE CANDY": "#e0614a",
         "PIEL DE SAPO": "#2f5a36", "SUNUP": "#b8862a"}
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

e = html.escape


def d(dmy):
    return dt.datetime.strptime(dmy, "%d/%m/%Y").date()


def corto(f):
    return f"{f.day} {MESES[f.month - 1]}"


def n(v, dec=1):
    return "—" if v is None else f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v):
    return "—" if v is None else f"{round(v * 100)} %"


def entero(v):
    return f"{v:,}".replace(",", ".")


def escala(f, ancho=100):
    """Barra de firmeza en la escala 1-5: rango mín-máx y marca en la media."""
    if not f:
        return ""
    pos = lambda v: (min(max(v, 1), 5) - 1) / 4 * 100
    return (f'<span class="scale" style="width:{ancho}%"><i class="r" style="left:{pos(f[1]):.1f}%;'
            f'right:{100 - pos(f[2]):.1f}%"></i><i class="m" style="left:{pos(f[0]):.1f}%"></i></span>')


def celdas(r):
    fz, az, bd = r["firmeza"], r["azucar"], r["bandas"]
    out = [f'<td class="n">{r["albaranes"]}</td>', f'<td class="n">{r["medidas"]}</td>']
    out += [f'<td class="n fzv">{n(fz[0], 2)}</td><td class="n mm">{n(fz[1])}–{n(fz[2])}</td>'
            f'<td class="bar">{escala(fz)}</td>'] if fz else ['<td class="n">—</td><td></td><td></td>']
    out += [f'<td class="n azv">{n(az[0])}</td><td class="n mm">{n(az[1])}–{n(az[2])}</td>'] if az \
        else ['<td class="n">—</td><td></td>']
    out += [f'<td class="n b{" hi" if i == 3 else ""}">{pct(bd[i]) if bd else "—"}</td>' for i in range(4)]
    return "".join(out)


def tabla_tipo(t):
    S = t["total"]
    col = COLOR.get(t["tipo"], "#7a8075")
    filas = []
    for v in t["variedades"]:
        nombre = e(v["nombre"]) if v["nombre"] else '<span class="muted">sin nombre</span>'
        filas.append(f'<tbody class="grupo"><tr class="var"><td><span class="code">{e(v["codigo"])}</span> '
                     f'<b>{nombre}</b></td><td class="n">{v["fincas"]}</td>{celdas(v)}</tr>')
        for f in v["fincas_detalle"]:
            cat = f' <span class="cat">{e(f["cat"])}</span>' if f["cat"] else ""
            filas.append(f'<tr class="finca"><td>{e(f["finca"])} <span class="cod">{e(f["cod"])}</span>{cat}</td>'
                         f'<td></td>{celdas(f)}</tr>')
        filas.append("</tbody>")
    fz, az, bd = S["firmeza"], S["azucar"], S["bandas"]
    sub = (f'{len(t["variedades"])} var. · {S["fincas"]} fincas · {S["albaranes"]} alb. · '
           f'{S["medidas"]} medidas firmeza · firmeza <b>{n(fz[0], 2)}</b> · Brix <b>{n(az[0]) if az else "—"}</b>'
           f' · ≥12 <b>{pct(bd[3]) if bd else "—"}</b>')
    return f'''<section class="tipo" style="--c:{col}">
  <h3><span class="dot"></span>{e(t["tipo"])}<span class="sub">{sub}</span></h3>
  <table>
    <colgroup><col class="c-var"><col class="c-n"><col class="c-n"><col class="c-n"><col class="c-n"><col class="c-mm">
      <col class="c-bar"><col class="c-n"><col class="c-mm"><col class="c-b"><col class="c-b"><col class="c-b"><col class="c-b"></colgroup>
    <thead><tr class="grp"><th colspan="4"></th><th colspan="3" class="g-fz">Firmeza (1–5)</th>
      <th colspan="6" class="g-az">Azúcar °Brix · temporada</th></tr>
    <tr><th>Variedad / finca</th><th class="n">Fincas</th><th class="n">Alb.</th><th class="n">Medidas</th>
      <th class="n">Media</th><th class="n">Mín–máx</th><th></th><th class="n">Medio</th><th class="n">Mín–máx</th>
      <th class="n">&lt;9</th><th class="n">9–10</th><th class="n">10–12</th><th class="n">≥12</th></tr></thead>
    {"".join(filas)}
  </table>
</section>'''


def seccion_semana(s):
    T = s["total"]
    ini, fin = d(s["desde"]), d(s["hasta"])
    delta = ""
    if s["firmeza_anterior"] is not None:
        dif = T["firmeza"][0] - s["firmeza_anterior"]
        delta = (f'<span class="delta {"up" if dif >= 0 else "down"}">{"▲" if dif >= 0 else "▼"} '
                 f'{n(abs(dif), 2)} vs semana anterior</span>')
    bd = T["bandas"]
    bandas = "".join(f'<span><em>{l}</em>{pct(bd[i]) if bd else "—"}</span>'
                     for i, l in enumerate(["<9", "9–10", "10–12", "≥12"]))
    return f'''<section class="semana" id="{s["etiqueta"]}">
  <header class="sem-head">
    <div class="sem-id"><span class="sem-n">{s["etiqueta"]}</span>
      <span class="sem-r">{corto(ini)} – {corto(fin)} {fin.year}<small>lunes {s["desde"]} · domingo {s["hasta"]}</small></span></div>
    <dl class="counts"><div><dt>Tipos</dt><dd>{len(s["tipos"])}</dd></div><div><dt>Variedades</dt><dd>{s["variedades"]}</dd></div>
      <div><dt>Fincas</dt><dd>{T["fincas"]}</dd></div><div><dt>Albaranes</dt><dd>{T["albaranes"]}</dd></div>
      <div><dt>Medidas firmeza</dt><dd>{entero(T["medidas"])}</dd></div></dl>
    <div class="kpis">
      <div class="kpi fz"><div class="lab">Firmeza media (1–5)</div>
        <div class="big">{n(T["firmeza"][0], 2)}<small>{n(T["firmeza"][1])}–{n(T["firmeza"][2])}</small></div>
        {escala(T["firmeza"])}{delta}</div>
      <div class="kpi az"><div class="lab">Brix medio <span class="tag">temporada</span></div>
        <div class="big">{n(T["azucar"][0]) if T["azucar"] else "—"}<small>{f"{n(T['azucar'][1])}–{n(T['azucar'][2])}" if T["azucar"] else ""}</small></div>
        <div class="bandas">{bandas}</div></div>
    </div>
  </header>
  {"".join(tabla_tipo(t) for t in s["tipos"])}
</section>'''


def tramo_vacio(grupo):
    ini, fin = d(grupo[0]["desde"]), d(grupo[-1]["hasta"])
    chips = "".join(f'<li><b>{s["etiqueta"]}</b>{corto(d(s["desde"]))} – {corto(d(s["hasta"]))}</li>' for s in grupo)
    return f'''<section class="vacias">
  <h2>{grupo[0]["etiqueta"]}–{grupo[-1]["etiqueta"]} <small>{corto(ini)} {ini.year} – {corto(fin)} {fin.year} · sin escandallos</small></h2>
  <ul>{chips}</ul>
</section>'''


def portada(semanas, bloques, origen):
    con = [s for s in semanas if s["total"]]
    fechas = [f for b in bloques for f, _, _ in b["firmeza"]]
    az = estadisticas(bloques)
    bd = bandas_azucar(bloques)
    fv = [v for b in bloques for _, _, v in b["firmeza"]]
    celdas_sem = []
    for s in semanas:
        ini, fin = d(s["desde"]), d(s["hasta"])
        if s["total"]:
            T = s["total"]
            celdas_sem.append(
                f'<a class="wk" href="#{s["etiqueta"]}"><b>{s["etiqueta"]}</b><span>{corto(ini)} – {corto(fin)}</span>'
                f'<em>{s["variedades"]} var. · {T["fincas"]} fincas</em>'
                f'<i>F {n(T["firmeza"][0], 2)} · B {n(T["azucar"][0]) if T["azucar"] else "—"}</i></a>')
        else:
            celdas_sem.append(f'<div class="wk off"><b>{s["etiqueta"]}</b><span>{corto(ini)} – {corto(fin)}</span>'
                              f'<em>sin datos</em></div>')
    leyenda = "".join(f'<span><i style="background:{c}"></i>{t}</span>' for t, c in COLOR.items())
    return f'''<section class="portada">
  <div class="eyebrow">Control de calidad · Melón · {e(origen)}</div>
  <h1>Escandallo semanal<br>de melón 2026</h1>
  <p class="lead">Semanas de lunes a domingo (ISO). Para cada semana: tipos de melón, variedades y fincas
    con escandallo, firmeza de las medidas de esa semana y azúcar (°Brix) de temporada de esas fincas.</p>
  <dl class="resumen">
    <div><dt>Semanas con datos</dt><dd>{len(con)}<small>de 53</small></dd></div>
    <div><dt>Periodo</dt><dd>{corto(min(fechas))} – {corto(max(fechas))}</dd></div>
    <div><dt>Escandallos</dt><dd>{len(bloques)}</dd></div>
    <div><dt>Variedades</dt><dd>{len({b["variedad"] for b in bloques})}</dd></div>
    <div><dt>Fincas</dt><dd>{len({b["cod_finca"] for b in bloques})}</dd></div>
    <div><dt>Medidas firmeza</dt><dd>{entero(len(fv))}</dd></div>
    <div><dt>Firmeza media</dt><dd>{n(sum(fv) / len(fv), 2)}</dd></div>
    <div><dt>Brix medio</dt><dd>{n(az[0])}<small>≥12: {pct(bd[3])}</small></dd></div>
  </dl>
  <h2 class="cal-t">Las 53 semanas <small>F = firmeza media · B = Brix medio</small></h2>
  <div class="cal">{"".join(celdas_sem)}</div>
  <div class="leyenda">{leyenda}</div>
  <div class="notas">
    <p><b>Firmeza:</b> escala 1–5. La barra va del mínimo al máximo y la marca es la media. «Medidas» cuenta solo medidas de firmeza.
      Se excluyen 5 medidas fuera de escala (23, 27, 33, 41, 45: falta la coma).</p>
    <p><b>Azúcar:</b> el volcado no trae fecha para el azúcar, así que en cada semana se da el de toda la temporada de esas fincas y variedad.
      Los rangos (&lt;9, 9–10, 10–12, ≥12) se calculan con los valores de °Brix uno a uno; el 12 exacto va en ≥12, como en el ERP.
      El número de muestras de azúcar no se muestra porque el volcado no lo da.</p>
    <p><b>Variedades:</b> nombres según la lista de variedades por número. Las categorías C2 y G se indican junto a la finca.</p>
  </div>
</section>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--salida", default="Escandallo semanal melon 2026")
    args = ap.parse_args()

    semanas, bloques = construir_semanas(args.volcado)
    cuerpo, vacias = [], []
    for s in semanas:
        if s["total"]:
            if vacias:
                cuerpo.append(tramo_vacio(vacias))
                vacias = []
            cuerpo.append(seccion_semana(s))
        else:
            vacias.append(s)
    if vacias:
        cuerpo.append(tramo_vacio(vacias))

    plantilla = (AQUI / "plantilla_a4.html").read_text(encoding="utf-8")
    pagina = plantilla.replace("<!--CONTENIDO-->", portada(semanas, bloques, args.volcado.name) + "".join(cuerpo))
    ruta_html, ruta_pdf = Path(args.salida + ".html"), Path(args.salida + ".pdf")
    ruta_html.write_text(pagina, encoding="utf-8")
    if os.path.exists(CHROME):
        subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={ruta_pdf.resolve()}", ruta_html.resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f"{ruta_html} y {ruta_pdf}")


if __name__ == "__main__":
    main()
