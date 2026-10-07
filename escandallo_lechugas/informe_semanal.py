#!/usr/bin/env python3
"""Informe semanal de escandallo de lechugas (CPT: control post-tratamiento / conservación).

Lee el volcado CSV del ERP (una ficha por revisión a día 5, 7 y 10 de cada entrada
de almacén) y genera un informe HTML + PDF con una página por semana de recepción.

La semana se asigna SIEMPRE por la fecha de recepción en almacén (columna FECHA),
nunca por la fecha de la revisión. Así los tres controles de una misma entrada
quedan juntos en la semana en la que entró el producto.

Uso:
    python3 informe_semanal.py <csv> <dir_salida>
"""
import sys, os, re, html, datetime, collections, subprocess, shutil

EXCLUIR = {
    'LECHUGA ICEBERG',
    'PIMIENTO ROJO CALIFORNIA', 'PIMIENTO AMARILLO CALIFORNIA',
    'PIMIENTO VERDE CALIFORNIA', 'PIMIENTO NARANJA CALIFORNIA',
    'PMTO.PUNTIA.DULCE ROJO',
    '',  # registros sin producto
}

# Orden maestro de productos (el que se usa en cada semana). Lo que no esté aquí no entra en el informe.
ORDEN = [
    ('COLIRABANO', 'Colirrábano'),
    ('ECO LECH.MINI ROM', 'Mini romana ECO'),
    ('ECO LECH.ROMANA', 'Romana ECO'),
    ('ESCAROLA LISA', 'Escarola lisa'),
    ('ESCAROLA BLANCA', 'Escarola blanca Francia / blanqueada'),
    ('ESCAROLA RIZADA', 'Escarola rizada'),
    ('ESCAROLA FINA', 'Escarola fina'),
    ('LECHUGA ROMANA', 'Romana'),
    ('ROMANA MIDI', 'Romana midi'),
    ('L.ROMANA CRUJIENTE', 'Romana crunchy'),
    ('MINI ROMANA CRUJIENTE', 'Mini romana crunchy'),
    ('MINI ROMANA', 'Mini romana'),
    ('MINI ROMANA ROJA', 'Mini romana roja'),
    ('LITTLE GEM VERDE', 'Little gem'),
    ('ROBLE ROJA', 'Hoja de roble roja'),
    ('LOLLO ROSSO', 'Lollo rosso'),
    ('LOLLO BIONDO', 'Lollo biondo'),
    ('BATAVIA VERDE', 'Batavia verde'),
    ('FRILLICE', 'Frillice'),
    ('MULTILEAF VERDE', 'Multileaf verde'),
    ('MULTILEAF ROJO', 'Multileaf rojo'),
]
POS = {k: i for i, (k, _) in enumerate(ORDEN)}
NOMBRE = dict(ORDEN)


def nombre(prod):
    return NOMBRE.get(prod, prod)


# ---------------------------------------------------------------- lectura

def leer_csv(path):
    lines = open(path, encoding='latin-1').read().splitlines()
    recs = []
    i = 0
    while i < len(lines):
        if not lines[i].startswith('PRODUCTO;'):
            i += 1
            continue
        rec = lines[i + 1].split(';')
        rec += [''] * (14 - len(rec))
        j = i + 2
        section = None
        probs = {'MAY': [], 'MEN': []}
        while j < len(lines) and not lines[j].startswith('-.-.-'):
            l = lines[j]
            if l.startswith('PROBLEMAS MAYORES'):
                section = 'MAY'
            elif l.startswith('PROBLEMAS MENORES'):
                section = 'MEN'
            else:
                p = l.split(';')
                if p[0].strip().isdigit() and section:
                    probs[section].append((p[0].strip(), p[1].strip(), p[2].strip()))
            j += 1
        fecha = rec[9].strip()
        try:
            fdate = datetime.datetime.strptime(fecha, '%d/%m/%Y').date()
        except ValueError:
            fdate = None
        recs.append(dict(
            prod=rec[0].strip(), var=rec[1].strip(), marca=rec[2].strip(),
            cliente=rec[3].strip(), cal=rec[4].strip(),
            fcode=rec[5].strip(), fname=rec[6].strip(),
            fecha=fdate, sumesc=rec[10].strip(), sumpart=rec[11].strip(),
            sem=rec[12].strip(), dias=rec[13].strip(), probs=probs))
        i = j
    return recs


# ---------------------------------------------------------------- agrupación

def piezas(r):
    try:
        return max(int(r['sumesc']), 1)
    except ValueError:
        return 1


def columna_dia(d):
    """Asigna el nº de días de la revisión a la columna 5 / 7 / 10 más cercana."""
    try:
        n = int(d)
    except ValueError:
        return None, d
    if n <= 6:
        col = 5
    elif n <= 8:
        col = 7
    else:
        col = 10
    return col, n


def agrupar(recs):
    """Agrupa las fichas por entrada (producto, variedad, calibre, finca, fecha)."""
    grupos = collections.OrderedDict()
    for r in recs:
        if r['prod'] in EXCLUIR or r['prod'] not in POS or r['fecha'] is None:
            continue
        key = (r['prod'], r['var'], r['cal'], r['fcode'], r['fname'], r['fecha'])
        g = grupos.setdefault(key, dict(
            prod=r['prod'], var=r['var'], cal=r['cal'], fcode=r['fcode'],
            fname=r['fname'], fecha=r['fecha'], sumesc=r['sumesc'],
            dias={5: [], 7: [], 10: []}, otros=[]))
        col, n = columna_dia(r['dias'])
        if col is None:
            g['otros'].append(r)
        else:
            g['dias'][col].append((n, r))
    out = list(grupos.values())
    for g in out:
        fichas = sorted(((n, r) for col in (5, 7, 10) for n, r in g['dias'][col]), key=lambda x: x[0])
        if not fichas:
            continue
        # piezas iniciales = las de la primera revisión de la entrada
        pz0 = piezas(fichas[0][1])
        fix = None
        if pz0 > 50:
            alts = [piezas(r) for n, r in fichas[1:] if piezas(r) <= 50]
            if alts:
                fix = pz0
                pz0 = collections.Counter(alts).most_common(1)[0][0]
        g['pz0'] = pz0
        for n, r in fichas:
            r['pz0'] = pz0
            r['pz_fix'] = fix
    return out


def semana_iso(d):
    y, w, _ = d.isocalendar()
    return (y, w)


def lunes(y, w):
    return datetime.date.fromisocalendar(y, w, 1)


def rango_semanas(d0, d1):
    """Todas las semanas ISO entre dos fechas (inclusive)."""
    y, w = semana_iso(d0)
    out = []
    cur = lunes(y, w)
    while cur <= d1:
        out.append(semana_iso(cur))
        cur += datetime.timedelta(days=7)
    return out


def campana(d0, d1):
    """Campaña de lechuga: de la semana del 1 de septiembre a la última de mayo.
    Devuelve (año_inicio, año_fin, lista de semanas). Si los datos se salen, se amplía."""
    y0 = d0.year if d0.month >= 9 else d0.year - 1
    ini = datetime.date(y0, 9, 1)
    fin = datetime.date(y0 + 1, 5, 31)
    ini = min(ini, d0)
    fin = max(fin, d1)
    return y0, y0 + 1, rango_semanas(ini, fin)


# ---------------------------------------------------------------- formato

MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
DIAS_SEM = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def fcorta(d):
    return f"{d.day} {MESES[d.month - 1]}"


def flarga(d):
    return d.strftime('%d/%m/%Y')


def esc(s):
    return html.escape(str(s))


def fmt_pct(v):
    v = v.replace('.', ',')
    return v + '%' if v else ''


PALETA = ['#c9a227', '#d9613c', '#b8413c', '#5a9c4a', '#2f7a5d', '#9a8a6a', '#e4723a',
          '#3c6e47', '#c08a2a', '#7a4f8a', '#4a7fb5', '#8a6d3b', '#6b8e23', '#b05c7a',
          '#2a8c8c', '#a0522d', '#556b2f', '#8b7355', '#4682b4', '#9c6b30', '#5f7f5f',
          '#c76b3a', '#3b6d8c', '#a3763a']


def celda_dia(revs):
    """HTML de la celda de un día: problemas mayores y menores de la(s) ficha(s)."""
    if not revs:
        return '<td class="dia vacio">—</td>'
    partes = []
    for n, r in sorted(revs, key=lambda x: x[0]):
        bloque = []
        nota = f'<span class="nota">día {n}</span>' if n not in (5, 7, 10) else ''
        may = r['probs']['MAY']
        men = r['probs']['MEN']
        if not may and not men:
            bloque.append(f'<div class="ok">sin incidencias{(" · " + nota) if nota else ""}</div>')
        else:
            if nota:
                bloque.append(f'<div>{nota}</div>')
            if may:
                bloque.append('<div class="may"><span class="lbl">MAYORES</span>' +
                              ''.join(f'<span class="p">{esc(d)} <b>{esc(fmt_pct(v))}</b></span>' for c, d, v in may) + '</div>')
            if men:
                bloque.append('<div class="men"><span class="lbl">menores</span>' +
                              ''.join(f'<span class="p">{esc(d)} <b>{esc(fmt_pct(v))}</b></span>' for c, d, v in men) + '</div>')
        partes.append(''.join(bloque))
    return '<td class="dia">' + '<hr class="sep">'.join(partes) + '</td>'


def celda_unificada(revs):
    """Celda de un día para varias fichas unificadas: % ponderado por nº de piezas.
    Un problema que no aparece en una ficha cuenta como 0% en esa ficha."""
    if not revs:
        return '<td class="dia vacio">—</td>'
    tot = 0          # piezas iniciales de las entradas presentes en la celda
    acc = collections.OrderedDict()   # piezas afectadas por problema
    dias_raros = set()
    fixes = []
    for n, r in sorted(revs, key=lambda x: x[0]):
        pz_ficha = piezas(r)            # base sobre la que el ERP calculó el % de esta ficha
        pz0 = r.get('pz0', pz_ficha)    # piezas iniciales de la entrada
        tot += pz0
        if r.get('pz_fix'):
            fixes.append(f"{r['pz_fix']}→{pz0}")
        if n not in (5, 7, 10):
            dias_raros.add(n)
        for sec in ('MAY', 'MEN'):
            for c, d, v in r['probs'][sec]:
                try:
                    val = float(v.replace(',', '.'))
                except ValueError:
                    continue
                acc[(sec, d)] = acc.get((sec, d), 0.0) + val * pz_ficha / 100.0
    partes = []
    info = [f'{len(revs)} fichas · {tot} pzas' if len(revs) > 1 else f'{tot} pzas']
    if dias_raros:
        info.append('día ' + '/'.join(str(x) for x in sorted(dias_raros)))
    if fixes:
        info.append('pzas corregidas ' + ', '.join(fixes))
    partes.append('<div class="nota">' + ' · '.join(info) + '</div>')
    if not acc:
        partes.append('<div class="ok">sin incidencias</div>')
    else:
        for sec, cls, lbl in (('MAY', 'may', 'MAYORES'), ('MEN', 'men', 'menores')):
            items = [(d, acc[(sc, d)] * 100.0 / tot) for (sc, d) in acc if sc == sec]
            if items:
                items.sort(key=lambda x: -x[1])
                partes.append(f'<div class="{cls}"><span class="lbl">{lbl}</span>' +
                              ''.join(f'<span class="p">{esc(d)} <b>{fmt_num(x)}%</b></span>' for d, x in items) + '</div>')
    return '<td class="dia">' + ''.join(partes) + '</td>'


def fmt_num(x):
    t = f'{x:.1f}'.rstrip('0').rstrip('.')
    return t.replace('.', ',')


# ---------------------------------------------------------------- HTML

CSS = r"""
@page { size: A4; margin: 14mm 12mm 16mm 12mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: 'Source Sans 3', 'Source Sans Pro', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
       color: #222; font-size: 9.5pt; line-height: 1.25; background: #fff; }
.mono { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', Menlo, Consolas, monospace; }
.kicker { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 7.5pt; letter-spacing: .12em;
          text-transform: uppercase; color: #6b6b6b; }
h1 { font-size: 24pt; margin: 2px 0 6px; color: #2e6b3e; letter-spacing: -.01em; }
.lead { color: #444; margin: 0 0 10px; max-width: 170mm; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-bottom: 10px; }
.card { border: 1px solid #ddd; border-radius: 4px; padding: 5px 9px; background: #f7f7f4; }
.card .k { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 6.8pt; letter-spacing: .1em;
           text-transform: uppercase; color: #6b6b6b; }
.card .v { font-size: 13pt; font-weight: 700; margin-top: 1px; }
.card .v small { font-size: 8pt; font-weight: 400; color: #666; }
h2 { font-size: 12pt; margin: 8px 0 5px; color: #333; display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
h2 .kicker { text-transform: none; letter-spacing: .04em; font-size: 7pt; text-align: right; }
.cal { display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px; }
.wk { border: 1px dashed #c8c8c8; border-radius: 3px; padding: 4px 6px; min-height: 40px; font-size: 7pt; line-height: 1.2; }
.wk.has { background: #dfe9d3; border: 1px solid #b7c9a5; }
.wk .s { font-weight: 700; font-size: 9.5pt; color: #999; }
.wk .s .y { font-size: 6.5pt; font-weight: 400; color: #999; }
.wk.has .s { color: #2e6b3e; }
.wk.has .s .y { color: #5a8a5e; }
.wk .d { font-weight: 600; margin: 0; color: #666; }
.wk.has .d { color: #222; }
.wk .m { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 6.3pt; color: #666; }
.yr { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px; margin: 3px 0; font-family: 'IBM Plex Mono', monospace;
      font-size: 7pt; letter-spacing: .12em; text-transform: uppercase; color: #8a6d3b; }
.yr::before, .yr::after { content: ''; flex: 1; border-top: 2px solid #c9a227; }
.legend { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px 14px; font-family: 'IBM Plex Mono', monospace;
          font-size: 7pt; letter-spacing: .06em; text-transform: uppercase; color: #444; }
.dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
.notas { margin-top: 10px; font-size: 8pt; color: #333; border-top: 1px solid #ddd; padding-top: 8px; }
.notas p { margin: 3px 0; }

.page { page-break-before: always; break-before: page; }
.wh { display: grid; grid-template-columns: 1.6fr 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.whead { background: #e8efe0; border-radius: 4px; padding: 8px 12px; }
.whead .s { font-size: 24pt; font-weight: 800; color: #2e6b3e; line-height: 1; }
.whead .r { font-size: 12pt; font-weight: 700; margin-left: 10px; }
.whead .sub { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 7.5pt; color: #555; margin: 3px 0 6px; }
.whead .st { display: flex; gap: 14px; }
.whead .st div { font-family: 'IBM Plex Mono', monospace; font-size: 6.8pt; letter-spacing: .08em; text-transform: uppercase; color: #666; }
.whead .st b { display: block; font-family: 'Source Sans 3', sans-serif; font-size: 12pt; color: #222; letter-spacing: 0; }
.box { border: 1px solid #ddd; border-radius: 4px; padding: 8px 10px; }
.box .k { font-family: 'IBM Plex Mono', monospace; font-size: 6.8pt; letter-spacing: .1em; text-transform: uppercase; color: #666; }
.box .v { font-size: 17pt; font-weight: 700; color: #2e6b3e; }
.box ul { margin: 3px 0 0; padding-left: 0; list-style: none; font-size: 8pt; }
.box li { display: flex; justify-content: space-between; gap: 6px; }

table.t { width: 100%; border-collapse: collapse; table-layout: fixed; }
table.t th { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-weight: 400; font-size: 6.8pt;
             letter-spacing: .08em; text-transform: uppercase; color: #555; text-align: left;
             border-bottom: 1px solid #999; padding: 3px 5px; }
table.t th.dia { border-left: 1px solid #e3e3e3; }
table.t td { padding: 4px 5px; vertical-align: top; border-bottom: 1px solid #e6e6e6; font-size: 8.3pt; }
table.t td.dia { border-left: 1px solid #e3e3e3; }
table.t td.vacio { color: #aaa; text-align: center; }
tbody.prod { break-inside: avoid; page-break-inside: avoid; }
tr { break-inside: avoid; page-break-inside: avoid; }
tr.ph td { background: #f3f0e6; font-weight: 700; font-size: 8.5pt; padding: 5px 5px; border-bottom: 1px solid #d8d2c0; }
tr.ph td .dot { width: 8px; height: 8px; }
tr.ph td .n { font-weight: 400; color: #666; font-family: 'IBM Plex Mono', monospace; font-size: 7pt; letter-spacing: .06em; }
td.id .var { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 7.5pt; color: #666; }
td.id .fin { font-weight: 700; }
td.id .meta { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-size: 7pt; color: #666; margin-top: 1px; }
.lbl { font-family: 'IBM Plex Mono', monospace; font-size: 6.5pt; letter-spacing: .08em; margin-right: 4px; }
.may .lbl { color: #b8413c; font-weight: 700; }
.men .lbl { color: #777; }
.may { color: #8c2f2a; }
.men { color: #333; }
.p { display: inline-block; margin-right: 7px; white-space: nowrap; }
.p b { font-family: 'IBM Plex Mono', 'DejaVu Sans Mono', monospace; font-weight: 600; font-size: 7.6pt; }
.ok { color: #3c7a3e; }
.nota { font-family: 'IBM Plex Mono', monospace; font-size: 6.5pt; color: #8a6d3b; background: #faf3dc;
        padding: 0 3px; border-radius: 2px; }
hr.sep { border: 0; border-top: 1px dashed #ccc; margin: 3px 0; }
.foot { font-size: 7.5pt; color: #777; }
"""


def generar_html(grupos, src_name, titulo):
    fechas = [g['fecha'] for g in grupos]
    d0, d1 = min(fechas), max(fechas)
    y_ini, y_fin, semanas = campana(d0, d1)
    por_sem = collections.defaultdict(list)
    for g in grupos:
        por_sem[semana_iso(g['fecha'])].append(g)

    productos = sorted({g['prod'] for g in grupos}, key=lambda p: POS[p])
    color = {p: PALETA[POS[p] % len(PALETA)] for p in productos}

    n_rev = sum(len(v) for g in grupos for v in g['dias'].values()) + sum(len(g['otros']) for g in grupos)
    n_fincas = len({g['fname'] for g in grupos})
    n_var = len({(g['prod'], g['var']) for g in grupos})
    n_piezas = 0
    for g in grupos:
        try:
            n_piezas += int(g['sumesc'])
        except ValueError:
            pass
    sem_con_datos = [s for s in semanas if por_sem.get(s)]

    def etiqueta_sem(s):
        y, w = s
        return f"S{w:02d}"

    out = []
    out.append(f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>{esc(titulo)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=Source+Sans+3:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>""")

    # ---------------- portada
    out.append(f"""
<div class="kicker">CONTROL DE CALIDAD · CPT LECHUGAS Y HOJA · CAMPAÑA {y_ini % 100:02d}/{y_fin % 100:02d} · {esc(src_name)}</div>
<h1>{esc(titulo)}</h1>
<p class="lead">Una página por semana de <b>recepción en almacén</b> (lunes a domingo). Cada entrada se agrupa en la semana
en la que entró el producto, con lo observado en las revisiones a <b>día 5</b>, <b>día 7</b> y <b>día 10</b> de conservación,
aunque esas revisiones caigan en semanas posteriores.</p>
<div class="cards">
 <div class="card"><div class="k">Semanas con datos</div><div class="v">{len(sem_con_datos)} <small>de {len(semanas)}</small></div></div>
 <div class="card"><div class="k">Periodo (recepción)</div><div class="v">{fcorta(d0)} {d0.year} – {fcorta(d1)} {d1.year}</div></div>
 <div class="card"><div class="k">Entradas escandalladas</div><div class="v">{len(grupos)}</div></div>
 <div class="card"><div class="k">Revisiones (fichas)</div><div class="v">{n_rev}</div></div>
 <div class="card"><div class="k">Productos</div><div class="v">{len(productos)}</div></div>
 <div class="card"><div class="k">Variedades</div><div class="v">{n_var}</div></div>
 <div class="card"><div class="k">Fincas</div><div class="v">{n_fincas}</div></div>
 <div class="card"><div class="k">Piezas muestreadas</div><div class="v">{f"{n_piezas:,}".replace(",", ".")}</div></div>
</div>
<h2>Campaña {y_ini % 100:02d}/{y_fin % 100:02d} · semana a semana <span class="kicker">septiembre {y_ini} → mayo {y_fin} · verde = semana con producto escandallado</span></h2>
<div class="cal">""")
    anio_actual = None
    for s in semanas:
        y, w = s
        a = lunes(y, w)
        b = a + datetime.timedelta(days=6)
        if y != anio_actual:
            if anio_actual is not None:
                out.append(f'<div class="yr"><span>cambio de año · {anio_actual} → {y}</span></div>')
            anio_actual = y
        gs = por_sem.get(s, [])
        cls = 'wk has' if gs else 'wk'
        if gs:
            m = f"{len(gs)} entr · {len({g['fname'] for g in gs})} fin · {len({g['prod'] for g in gs})} prod"
        else:
            m = 'sin escandallos'
        out.append(f'<div class="{cls}"><div class="s">{etiqueta_sem(s)} <span class="y">{y}</span></div>'
                   f'<div class="d">{fcorta(a)} – {fcorta(b)}</div><div class="m">{m}</div></div>')
    out.append('</div><div class="legend">')
    out.append('<span style="width:100%;letter-spacing:.1em">Orden maestro de productos:</span>')
    for p in productos:
        out.append(f'<span><span class="dot" style="background:{color[p]}"></span>{esc(nombre(p))}</span>')
    out.append('</div>')
    out.append("""<div class="notas">
<p><b>Semana:</b> semana ISO (lunes–domingo) de la fecha de recepción en almacén del CSV (columna FECHA). La fecha de cada revisión no se usa para asignar semana.</p>
<p><b>Filas unificadas:</b> dentro de cada semana, todas las entradas de la misma finca y el mismo producto van en una sola fila. Se indican variedades, fechas de recepción, nº de entradas, piezas totales y albaranes.</p>
<p><b>Piezas y porcentajes:</b> el nº de piezas de cada entrada es el de su <b>primera revisión</b> (piezas iniciales) y se mantiene en día 7 y día 10. El % de cada problema es piezas afectadas ÷ piezas iniciales. Si una ficha trae un nº de piezas distinto, se pasan sus % a piezas afectadas y se recalculan sobre las iniciales. Si la primera ficha trae un nº disparatado (más de 50) se usa el de las otras revisiones y la celda lo indica («pzas corregidas»). Cuando hay varias fichas unificadas, el % es piezas afectadas totales ÷ piezas iniciales totales; la celda indica cuántas fichas y piezas se han unido. Fichas con otro nº de días (11, 12, 13…) van a la columna más cercana con la etiqueta <span class="nota">día n</span>. «—» = sin ficha para ese día.</p>
<p><b>Problemas:</b> MAYORES y menores tal y como vienen en la ficha, con el % de piezas afectadas, ordenados de mayor a menor. «Sin incidencias» = ninguna ficha anota problemas.</p>
<p><b>Identificación:</b> código de variedad, finca, fecha de recepción, nº de entradas y albarán. El nº de piezas se indica en cada celda, porque puede variar entre revisiones.</p>
<p><b>Calendario de portada:</b> campaña completa de septiembre a mayo; las semanas en verde tienen producto escandallado, las blancas no. La línea dorada marca el cambio de año.</p>
<p><b>Orden de productos:</b> en cada semana los productos aparecen siempre en el orden maestro de la leyenda; solo se listan los que tienen entradas esa semana.</p>
<p><b>Fuera del informe:</b> lechuga iceberg (convencional y ECO), pimientos, melones y registros sin producto.</p>
</div>""")

    # ---------------- páginas por semana
    for s in sem_con_datos:
        y, w = s
        a = lunes(y, w)
        b = a + datetime.timedelta(days=6)
        gs = sorted(por_sem[s], key=lambda g: (POS[g['prod']], g['fecha'], g['var'], g['fname'], g['cal']))
        n_f = len({g['fname'] for g in gs})
        n_p = len({g['prod'] for g in gs})
        n_v = len({(g['prod'], g['var']) for g in gs})
        # recuento de problemas de la semana
        cnt_may = collections.Counter()
        cnt_men = collections.Counter()
        n_fichas = 0
        for g in gs:
            for col, revs in g['dias'].items():
                for n, r in revs:
                    n_fichas += 1
                    for c, d, v in r['probs']['MAY']:
                        cnt_may[d] += 1
                    for c, d, v in r['probs']['MEN']:
                        cnt_men[d] += 1
        top_may = ''.join(f'<li><span>{esc(k)}</span><b>{n}</b></li>' for k, n in cnt_may.most_common(4)) or '<li><span>ninguno</span></li>'
        top_men = ''.join(f'<li><span>{esc(k)}</span><b>{n}</b></li>' for k, n in cnt_men.most_common(4)) or '<li><span>ninguno</span></li>'

        out.append(f"""<div class="page">
<div class="wh">
 <div class="whead"><span class="s">{etiqueta_sem(s)}</span><span class="r">{fcorta(a)} – {fcorta(b)} {b.year}</span>
  <div class="sub">{DIAS_SEM[0]} {flarga(a)} · {DIAS_SEM[6]} {flarga(b)} · semana de recepción</div>
  <div class="st"><div>Productos<b>{n_p}</b></div><div>Variedades<b>{n_v}</b></div><div>Fincas<b>{n_f}</b></div>
       <div>Entradas<b>{len(gs)}</b></div><div>Fichas<b>{n_fichas}</b></div></div>
 </div>
 <div class="box"><div class="k">Problemas mayores · nº de fichas</div><ul>{top_may}</ul></div>
 <div class="box"><div class="k">Problemas menores · nº de fichas</div><ul>{top_men}</ul></div>
</div>
<table class="t"><colgroup><col style="width:28%"><col style="width:24%"><col style="width:24%"><col style="width:24%"></colgroup>
<thead><tr><th>Producto · variedad · finca</th><th class="dia">Día 5</th><th class="dia">Día 7</th><th class="dia">Día 10</th></tr></thead>""")
        # unificar: misma finca y mismo producto dentro de la semana
        filas = collections.OrderedDict()
        for g in gs:
            k = (g['prod'], g['fname'])
            f = filas.setdefault(k, dict(prod=g['prod'], fname=g['fname'], entradas=[], dias={5: [], 7: [], 10: []}))
            f['entradas'].append(g)
            for col in (5, 7, 10):
                f['dias'][col].extend(g['dias'][col])
        prod_actual = None
        for (prod, fname), f in filas.items():
            if prod != prod_actual:
                if prod_actual is not None:
                    out.append('</tbody>')
                prod_actual = prod
                n_e = sum(1 for x in gs if x['prod'] == prod)
                n_vv = len({x['var'] for x in gs if x['prod'] == prod})
                n_ff = sum(1 for (pp, _) in filas if pp == prod)
                out.append(f'<tbody class="prod"><tr class="ph"><td colspan="4"><span class="dot" style="background:{color[prod]}"></span>'
                           f'{esc(nombre(prod))} <span class="n">{esc(prod)} · {n_vv} var · {n_ff} fincas · {n_e} entradas</span></td></tr>')
            ent = f['entradas']
            vars_ = sorted({g['var'] or 'sin variedad' for g in ent})
            albs = sorted({g['fcode'] for g in ent if g['fcode']})
            fechas_e = sorted({g['fecha'] for g in ent})
            pz = sum(piezas(g['dias'][5][0][1]) if g['dias'][5] else
                     piezas(g['dias'][7][0][1]) if g['dias'][7] else
                     piezas(g['dias'][10][0][1]) if g['dias'][10] else 0 for g in ent)
            fin = fname or 'finca no indicada'
            meta = []
            meta.append(('rec ' if len(fechas_e) == 1 else 'rec ') + ', '.join(d.strftime('%d/%m') for d in fechas_e) + f'/{fechas_e[0].year}')
            if len(ent) > 1:
                meta.append(f'{len(ent)} entradas')
            if albs:
                meta.append('alb ' + ', '.join(albs))
            out.append(f'<tr><td class="id"><span class="var">{esc(", ".join(vars_))}</span> <span class="fin">{esc(fin)}</span>'
                       f'<div class="meta">{" · ".join(meta)}</div></td>'
                       + celda_unificada(f['dias'][5]) + celda_unificada(f['dias'][7]) + celda_unificada(f['dias'][10]) + '</tr>')
        if prod_actual is not None:
            out.append('</tbody>')
        out.append('</table></div>')

    out.append('</body></html>')
    return ''.join(out), semanas, sem_con_datos


# ---------------------------------------------------------------- PDF

NODE_PDF = r"""
const { chromium } = require('playwright');
(async () => {
  const [html, pdf, titulo] = process.argv.slice(2);
  const br = await chromium.launch();
  const pg = await br.newPage();
  await pg.goto('file://' + html, { waitUntil: 'networkidle' });
  await pg.emulateMedia({ media: 'print' });
  const footer = '<div style="width:100%;font-size:7pt;color:#777;font-family:Helvetica,Arial,sans-serif;' +
    'padding:0 12mm;display:flex;justify-content:space-between;"><span>' + titulo +
    '</span><span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>';
  await pg.pdf({ path: pdf, format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<div></div>', footerTemplate: footer, preferCSSPageSize: false,
    margin: { top: '14mm', bottom: '16mm', left: '12mm', right: '12mm' } });
  await br.close();
})().catch(e => { console.error(e); process.exit(1); });
"""


def html_a_pdf(html_path, pdf_path, titulo):
    js = os.path.join(os.path.dirname(os.path.abspath(pdf_path)), '_pdf.js')
    with open(js, 'w', encoding='utf-8') as f:
        f.write(NODE_PDF)
    env = dict(os.environ)
    env.setdefault('NODE_PATH', '/usr/lib/node_modules:/usr/local/lib/node_modules')
    r = subprocess.run(['node', js, os.path.abspath(html_path), os.path.abspath(pdf_path), titulo],
                       capture_output=True, text=True, env=env)
    if r.returncode == 0:
        return 'playwright'
    sys.stderr.write('node/playwright falló: ' + r.stderr[-800:] + '\nuso chromium headless\n')
    chrome = shutil.which('chromium') or '/opt/pw-browsers/chromium'
    if os.path.isdir(chrome):
        for root, dirs, files in os.walk(chrome):
            if 'chrome' in files:
                chrome = os.path.join(root, 'chrome')
                break
    subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
                    f'--print-to-pdf={pdf_path}', 'file://' + os.path.abspath(html_path)],
                   check=True, capture_output=True)
    return 'chromium'


def main():
    csv_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    recs = leer_csv(csv_path)
    grupos = agrupar(recs)
    titulo = 'Escandallo semanal CPT lechugas · campaña 25/26'
    html_txt, semanas, con_datos = generar_html(grupos, os.path.basename(csv_path), titulo)
    base = os.path.join(out_dir, 'informe_cpt_lechugas_semanal')
    with open(base + '.html', 'w', encoding='utf-8') as f:
        f.write(html_txt)
    motor = html_a_pdf(base + '.html', base + '.pdf', titulo)
    print(f'fichas leídas: {len(recs)}  entradas agrupadas: {len(grupos)}  semanas: {len(con_datos)}/{len(semanas)}  pdf: {motor}')
    print(base + '.pdf')


if __name__ == '__main__':
    main()
