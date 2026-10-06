#!/usr/bin/env python3
"""Informe A4 de problemas por tipo de melón y finca: una página por tipo, una
fila por finca (todas sus variedades juntas) con los problemas mayores y menores
que pasan el umbral, y la suma de todos.

Uso:
    python3 problemas_fincas.py VOLCADO.csv [--mayores 4] [--menores 7]
                                [--salida "Problemas por finca 2026"]

Nombre de finca: columna nombre_final de fincas_nombres.csv (con los asociados GGN ya
convertidos a su agricultor; columna por_tipo para excepciones por tipo de melón). Los % son de toda la
temporada (el volcado no trae fecha de los problemas). Si una finca tiene varias
variedades o códigos, cada escandallo pesa según sus melones medidos (medidas de
firmeza; mínimo 1) y un problema que no aparece cuenta como 0 %.
"""
import argparse
import csv
import html
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

from escandallo import AQUI, leer_bloques, tipo_y_categoria
from informe_a4 import CHROME, COLOR, FUENTES

e = html.escape
TITULO = "Problemas por finca · melón 2026"
W, H = 794, 1123

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
.cab{display:grid;grid-template-columns:minmax(0,1fr) 150px 150px;gap:8px;height:92px;margin-bottom:10px}
.tit{border-radius:6px;padding:9px 12px;display:flex;flex-direction:column;justify-content:space-between;background:color-mix(in srgb,var(--c) 14%,white);overflow:hidden}
.tit h1{margin:0;font:800 28px/1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif;display:flex;align-items:center;gap:10px}
.tit h1 i{width:14px;height:14px;border-radius:50%;background:var(--c);display:inline-block}
.cnt{display:flex;gap:16px;white-space:nowrap}
.cnt div{display:flex;flex-direction:column}
.cnt b{font:700 14px/1.1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif}
.kpi{border:1px solid #cdd3c4;border-radius:6px;padding:7px 10px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden}
.kpi b{font:800 22px/1 "Bricolage Grotesque","Segoe UI",Arial,sans-serif}
.kpi.may b{color:#a3361c}.kpi.men b{color:#8a6a12}
.kpi small{font-size:9px;color:#4f584b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.grp{display:flex;font:600 7.5px/15px "IBM Plex Mono",Consolas,monospace;letter-spacing:.05em;text-transform:uppercase}
.grp span{text-align:center}
.grp .gm{color:#a3361c;border-bottom:1.5px solid #a3361c}.grp .gn{color:#8a6a12;border-bottom:1.5px solid #c9a227}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th{height:20px;padding:0 4px;font:500 7.5px "IBM Plex Mono",Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;color:#4f584b;text-align:right;white-space:nowrap;overflow:hidden}
th.l{text-align:left}
th{letter-spacing:0;padding:0 3px}
td{padding:0 3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right;font:400 9.5px "IBM Plex Mono",Consolas,monospace;border-top:1px solid #e3e7dc}
td.l{text-align:left;font:600 10px "Source Sans 3","Segoe UI",Arial,sans-serif}
td.num{color:#8a9184;font-size:8.5px}
td.sep{border-left:1px solid #cdd3c4}
td.lista{text-align:left;font:400 8.6px "Source Sans 3","Segoe UI",Arial,sans-serif}
td.lista b{font:600 8.5px "IBM Plex Mono",Consolas,monospace}
td.lista.m b{color:#a3361c}td.lista.m b.bajo{color:#7d847a;font-weight:500}td.lista.n b{color:#8a6a12}
td.lista.largo{font-size:8px;letter-spacing:-.02em}td.lista.largo b{font-size:7.6px}
td.lista.largo4{font-size:7.3px;letter-spacing:-.03em}td.lista.largo4 b{font-size:7px}
td.l.largo{font-size:8.6px;letter-spacing:-.02em}
td.sem{text-align:left;font:400 9.5px "Source Sans 3","Segoe UI",Arial,sans-serif;color:#4f584b}
td.lista em{font-style:normal;color:#a7ad9f}
td.vm{color:#a3361c;font-weight:500}td.vn{color:#8a6a12;font-weight:500}
tr.t td{background:color-mix(in srgb,var(--c) 14%,white);border-top:1.5px solid var(--c);font-weight:600}
tr.t td.l{font:700 9.5px "IBM Plex Mono",Consolas,monospace;letter-spacing:.05em;text-transform:uppercase}
.nota{margin-top:8px;font-size:9px;color:#4f584b;line-height:1.45}
.nota b{color:#1c221b}
"""


AJUSTE = """<script>
// Si un texto no cabe en su celda (con 3 px de margen, porque al imprimir el ancho varía algo),
// baja la letra de esa celda poco a poco, sin pasar de 6,5 px.
function ancho(td) { var r = document.createRange(); r.selectNodeContents(td); return r.getBoundingClientRect().width; }
function ajustar() {
  document.querySelectorAll("td.lista, td.sem, td.l").forEach(function (td) {
    var cs = getComputedStyle(td), t = 0, tam = parseFloat(cs.fontSize);
    var hueco = td.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 3;
    while (ancho(td) > hueco && tam > 6.5 && t++ < 40) {
      tam -= 0.2; td.style.fontSize = tam + "px";
      td.querySelectorAll("b").forEach(function (b) { b.style.fontSize = (tam - 0.4) + "px"; });
    }
  });
}
ajustar();
if (document.fonts) document.fonts.ready.then(ajustar);   // otra vez cuando estén cargadas las fuentes
</script>"""


def miles(n):
    return f"{n:,}".replace(",", ".")


def pc(v, dec=1):
    return f"{v:.{dec}f}".replace(".", ",")


def medias(bloques):
    """Media ponderada (por melones medidos) de cada problema mayor y menor."""
    peso = sum(max(len(b["firmeza"]), 1) for b in bloques)
    out = {}
    for sec in ("mayores", "menores"):
        acum = defaultdict(float)
        for b in bloques:
            for p, v in b[sec].items():
                acum[p] += v * max(len(b["firmeza"]), 1)
        out[sec] = sorted(((p, v / peso) for p, v in acum.items()), key=lambda x: -x[1])
    return out


SEMANA_DE = json.loads((AQUI / "semanas_2026_ia.json").read_text(encoding="utf-8"))["fecha_a_semana"]


def semanas_txt(bloques):
    """Semanas con escandallo (fechas de las medidas de firmeza) en tramos: «S32-34 y S37»."""
    ns = sorted({int(SEMANA_DE[f.strftime("%d/%m/%Y")][1:]) for b in bloques for f, _, _ in b["firmeza"]})
    tramos, i = [], 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        tramos.append(f"S{ns[i]}" if i == j else f"S{ns[i]}-{ns[j]}")
        i = j + 1
    if not tramos:
        return "—"
    return tramos[0] if len(tramos) == 1 else ", ".join(tramos[:-1]) + " y " + tramos[-1]


# Nombres largos abreviados dentro de las listas (leyenda al pie de cada página)
ABREVIATURAS = {
    "PODRIDO PEQUEÑO": "Podrido peq.", "PODRIDO GRANDE": "Podrido gr.", "MANCHAS TRATAMIENTO": "Manchas trat.",
    "SEMILLA DESPRENDIDA": "Semilla desp.", "PRINCIPIO DE AVINADO": "Princ. avinado",
    "PEDUNCULO AGRIETADO": "Pedúnc. agrietado", "ESCRITURADO CAIDO": "Escrit. caído", "MAL ESCRITURADO": "Mal escrit.",
    "DEFECTO DE COLOR": "Def. color", "CUERPOS EXTRAÑOS": "Cuerpos extr.", "DAÑO POR PIEDRA": "Daño piedra",
}
LEYENDA = ("peq. = pequeño · gr. = grande · trat. = tratamiento · desp. = desprendida · Princ. = principio · "
           "Pedúnc. = pedúnculo · Escrit. = escriturado · Def. = defecto · extr. = extraños")

SUMA_MAYORES_MIN3 = 7.5   # si la suma de mayores pasa de esto, salen al menos los 3 más abundantes


def lista(problemas, umbral, clase, minimo=0):
    """Problemas desde el umbral; con minimo=3 salen además los 3 más abundantes
    aunque no lleguen (esos van en gris para distinguirlos)."""
    sel = [(p, v) for i, (p, v) in enumerate(problemas) if v > 0 and (v >= umbral or i < minimo)]
    if not sel:
        return f'<td class="lista {clase} sep"><em>—</em></td>'
    # el % va en la cabecera; los valores redondos sin ",0" (10 en vez de 10,0) para ahorrar sitio
    partes = []
    for p, v in sel:
        cls = "" if v >= umbral else ' class="bajo"'
        partes.append(f"<b{cls}>{pc(v).removesuffix(',0')}</b> {e(ABREVIATURAS.get(p, p.capitalize()))}")
    txt = " · ".join(partes)
    # con 3 o más problemas, letra algo más pequeña para que quepa en la fila
    largo = " largo4" if len(sel) >= 4 else (" largo" if len(sel) == 3 else "")
    return f'<td class="lista {clase} sep{largo}">{txt}</td>'


def pagina(tipo, fincas, num, total, umb_may, umb_men):
    todos = [b for bs in fincas.values() for b in bs]
    M = medias(todos)
    sm, sn = sum(v for _, v in M["mayores"]), sum(v for _, v in M["menores"])
    melones = sum(len(b["firmeza"]) for b in todos)
    filas_datos = []
    for finca, bs in fincas.items():
        m = medias(bs)
        filas_datos.append((finca, bs, m, sum(v for _, v in m["mayores"]), sum(v for _, v in m["menores"])))
    filas_datos.sort(key=lambda f: (-f[3], -f[4], f[0]))
    n_filas = len(filas_datos) + 1
    alto = max(16, min(24, (H - 76 - 30 - 92 - 10 - 15 - 20 - 46) // n_filas))
    col = COLOR.get(tipo, "#6b7466")
    filas = [f'<tr class="t" style="height:{alto}px;--c:{col}"><td class="num"></td><td class="l">Media del tipo</td><td class="sem">{semanas_txt(todos)}</td>'
             f'<td>{miles(melones)}</td>'
             + lista(M["mayores"], umb_may, "m", 3 if sm > SUMA_MAYORES_MIN3 else 0) + f'<td class="vm">{pc(sm)}</td>'
             + lista(M["menores"], umb_men, "n") + f'<td class="vn">{pc(sn)}</td></tr>']
    for i, (finca, bs, m, fm, fn) in enumerate(filas_datos, start=1):
        mel = sum(len(b["firmeza"]) for b in bs)
        filas.append(f'<tr style="height:{alto}px"><td class="num">{i}</td><td class="l{" largo" if len(finca) > 20 else ""}">{e(finca)}</td><td class="sem">{semanas_txt(bs)}</td>'
                     f'<td>{miles(mel)}</td>'
                     + lista(m["mayores"], umb_may, "m", 3 if fm > SUMA_MAYORES_MIN3 else 0) + f'<td class="vm">{pc(fm)}</td>'
                     + lista(m["menores"], umb_men, "n") + f'<td class="vn">{pc(fn)}</td></tr>')
    cols = [("#", 2.3, ""), ("Finca", 15.5, "l"), ("Semanas", 14.5, "l"), ("Mel.", 5.2, ""),
            (f"% · desde {umb_may}% · de más a menos", 27.5, "l"), ("Suma %", 4.5, ""),
            (f"% · desde {umb_men}% · de más a menos", 26, "l"), ("Suma %", 4.5, "")]
    ths = "".join(f'<th class="{c}" style="width:{w}%">{t}</th>' for t, w, c in cols)
    ancho_m = cols[4][1] + cols[5][1]
    ancho_n = cols[6][1] + cols[7][1]
    banda = (f'<div class="grp"><span style="width:{100 - ancho_m - ancho_n}%"></span>'
             f'<span class="gm" style="width:{ancho_m}%">Problemas mayores</span>'
             f'<span class="gn" style="width:{ancho_n}%">Problemas menores</span></div>')
    top_m = M["mayores"][0][0].capitalize() if M["mayores"] else "—"
    top_n = M["menores"][0][0].capitalize() if M["menores"] else "—"
    cuerpo = f'''<div class="cab">
<div class="tit" style="--c:{col}"><span class="lab">Problemas por finca · toda la temporada</span><h1><i></i>{e(tipo.title())}</h1>
<div class="cnt"><div><span class="lab">Fincas</span><b>{len(fincas)}</b></div><div><span class="lab">Escandallos</span><b>{len(todos)}</b></div>
<div><span class="lab">Variedades</span><b>{len({b["variedad"] for b in todos})}</b></div><div><span class="lab">Melones medidos</span><b>{melones:,}</b></div></div></div>
<div class="kpi may"><span class="lab">Suma problemas mayores</span><b>{pc(sm, 2)}%</b><small>El que más: {e(top_m)}</small></div>
<div class="kpi men"><span class="lab">Suma problemas menores</span><b>{pc(sn, 2)}%</b><small>El que más: {e(top_n)}</small></div>
</div>{banda}<table><thead><tr>{ths}</tr></thead><tbody>{"".join(filas)}</tbody></table>
<p class="nota">Fincas ordenadas de más a menos problemas mayores. En cada fila salen, con su %, los problemas mayores de {umb_may}% o más y los menores de {umb_men}% o más.
Si la suma de mayores pasa de {pc(SUMA_MAYORES_MIN3)}%, salen al menos los 3 mayores más abundantes; los que no llegan al {umb_may}% van con el número en gris. Abreviaturas: {LEYENDA}.
<b>Suma</b> = todos los problemas de esa clase, salgan o no en la lista. % de toda la temporada (el volcado no trae fecha de los problemas).
Si una finca tiene varias variedades, cada escandallo pesa según sus melones medidos. <b>Semanas</b> = semanas con escandallo (S32-34 = de la 32 a la 34). <b>Mel.</b> = melones medidos (medidas de firmeza).</p>'''.replace(f"{melones:,}", f"{melones:,}".replace(",", "."))
    return (f'<div class="pg"><div class="cuerpo">{cuerpo}</div><div class="pie"><span>{TITULO} · <b>{e(tipo.title())}</b></span>'
            f'<span>Página {num} de {total}</span></div></div>')


def nombre_finca(fila, tipo, por_defecto):
    """Nombre de la finca en el informe (fincas_nombres.csv). La columna por_tipo
    permite excepciones: «SUNUP=Vicente Alberca» = si el melón es Sunup, va a ese nombre."""
    if not fila:
        return por_defecto
    for regla in filter(None, fila.get("por_tipo", "").split("|")):
        t, nombre = regla.split("=", 1)
        if t.strip().upper() == tipo.upper():
            return nombre.strip()
    return fila["nombre_final"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("volcado", type=Path)
    ap.add_argument("--mayores", type=float, default=4)
    ap.add_argument("--menores", type=float, default=7)
    ap.add_argument("--salida", default="Problemas por finca 2026")
    args = ap.parse_args()

    nombres = {r["nombre_erp"]: r for r in csv.DictReader(open(AQUI / "fincas_nombres.csv", encoding="utf-8"), delimiter=";")}
    nombre_erp = {}
    for fila in csv.reader(open(args.volcado, encoding="latin-1"), delimiter=";"):
        if len(fila) > 8 and fila[8] == "00/00/0000":
            nombre_erp[fila[4]] = fila[5]
    por_tipo = defaultdict(lambda: defaultdict(list))
    for b in leer_bloques(args.volcado):
        tipo = tipo_y_categoria(b["producto"])[0]
        por_tipo[tipo][nombre_finca(nombres.get(nombre_erp.get(b["cod_finca"], "")), tipo, b["finca"])].append(b)

    umb_may = int(args.mayores) if args.mayores == int(args.mayores) else args.mayores
    umb_men = int(args.menores) if args.menores == int(args.menores) else args.menores
    tipos = sorted(por_tipo)
    paginas = [pagina(t, por_tipo[t], i, len(tipos), umb_may, umb_men) for i, t in enumerate(tipos, start=1)]
    doc = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{TITULO}</title>{FUENTES}'
           f'<style>{CSS}</style></head><body>{"".join(paginas)}{AJUSTE}</body></html>')
    ruta_html, ruta_pdf = Path(args.salida + ".html"), Path(args.salida + ".pdf")
    ruta_html.write_text(doc, encoding="utf-8")
    if os.path.exists(CHROME):
        subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={ruta_pdf.resolve()}", ruta_html.resolve().as_uri()],
                       check=True, capture_output=True, timeout=180)
    print(f"{len(paginas)} páginas -> {ruta_html}, {ruta_pdf}")


if __name__ == "__main__":
    main()
