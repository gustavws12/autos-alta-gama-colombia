# -*- coding: utf-8 -*-
"""Construye el Excel de avisos BMW Z4 usados en Colombia."""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ---- Datos recolectados (WebSearch + portales, 2026-08-24) ----
# Campos: fuente, titulo, precio_cop (None si ND), año (None si ND), generacion,
#         cilindraje_cc (None si ND), km, ciudad, para_reparar, link, nota
ND = None
rows = [
    ("TuCarro", "BMW Z4 sDrive20i", 206_000_000, ND, "G29 (2019+)", 1998, ND, ND,
     "No indicado",
     "https://articulo.tucarro.com.co/MCO-3022543068-bmw-z4-sdrive20i-_JM",
     "Cilindraje derivado de la versión sDrive20i (motor 2.0T B48)"),
    ("TuCarro", "BMW Z4 M40i Roadster", 335_000_000, ND, "G29 (2019+)", 2998, ND, ND,
     "No indicado",
     "https://articulo.tucarro.com.co/MCO-1261722433-bmw-z4-m40i-roadster-_JM",
     "Cilindraje derivado de la versión M40i (motor 3.0T B58)"),
    ("TuCarro", "BMW Z4 2.0 sDrive20i", 105_000_000, ND, "E89 (2009-2016)", 1997, ND, ND,
     "No indicado",
     "https://articulo.tucarro.com.co/MCO-2867800666-bmw-z4-20-sdrive20i-_JM",
     "Cilindraje derivado de la versión sDrive20i E89 (motor 2.0T N20)"),
    ("TuCarro", "BMW Z4 M40i 3.0 2022", 290_000_000, 2022, "G29 (2019+)", 2998, ND, ND,
     "No indicado",
     "https://articulo.tucarro.com.co/MCO-4184920468-bmw-z4-m40i-30-2022-_JM",
     "Cilindraje derivado de la versión M40i (motor 3.0T B58)"),
    ("TuCarro", "BMW Z4 sDrive20i", ND, ND, "G29 (2019+)", 1998, ND, ND,
     "No indicado",
     "https://articulo.tucarro.com.co/MCO-3264022100-bmw-z4-sdrive20i-_JM",
     "Precio no visible en el resultado de búsqueda"),
    ("TuCarro", "BMW Z4 sDrive20i 2015", 120_000_000, 2015, "E89 (2009-2016)", 1997, ND, ND,
     "No indicado",
     "https://articulo.tucarro.com.co/MCO-1530792721-bmw-z4-sdrive-20i-2015-_JM",
     "Cilindraje derivado de la versión sDrive20i E89 (motor 2.0T N20)"),
    ("MercadoLibre CO", "BMW Z4 sDrive 2.0 Convertible", 198_900_000, ND, "G29 (2019+)", 1998, ND, ND,
     "No indicado",
     "https://carro.mercadolibre.com.co/MCO-2864275518-bmw-z4-sdrive-20-convertible-_JM",
     "Cilindraje derivado de la versión sDrive 2.0"),
    ("MercadoLibre CO", "BMW Z4 M40i (placa JQU291)", 280_000_000, ND, "G29 (2019+)", 2998, ND, ND,
     "No indicado",
     "https://carro.mercadolibre.com.co/MCO-909293961-bmw-z4-m40i-jqu291-_JM",
     "Cilindraje derivado de la versión M40i (motor 3.0T B58)"),
    ("MercadoLibre CO", "BMW Z4 M40i Convertible 2022", 249_900_000, 2022, "G29 (2019+)", 2998, ND, ND,
     "No indicado",
     "https://carro.mercadolibre.com.co/MCO-1528740285-bmw-z4-m40i-convertible-2022-_JM",
     "Cilindraje derivado de la versión M40i (motor 3.0T B58)"),
    ("MercadoLibre CO", "BMW Z4 (versión no especificada)", 196_000_000, ND, "ND", ND, ND, ND,
     "No indicado",
     "https://carro.mercadolibre.com.co/MCO-1588628127-bmw-z4-_JM",
     "El título del aviso no especifica versión ni año"),
    ("MercadoLibre CO", "BMW Z4 E86 Coupé 3.0si", 198_000_000, ND, "E86 (2006-2008)", 2996, ND, ND,
     "No indicado",
     "https://carro.mercadolibre.com.co/MCO-2913422548-bmw-z4-e86-coupe-30si-_JM",
     "Cilindraje derivado de la versión 3.0si (motor N52)"),
    ("MercadoLibre CO", "BMW Z4 2.5 sDrive23i", 107_000_000, ND, "E89 (2009-2016)", 2497, ND, ND,
     "No indicado",
     "https://carro.mercadolibre.com.co/MCO-2836955948-bmw-z4-_JM",
     "Cilindraje derivado de la versión sDrive23i (motor 2.5 N52)"),
    ("CarroYa", "BMW Z4 2022", ND, 2022, "G29 (2019+)", ND, ND, "Medellín",
     "No indicado",
     "https://www.carroya.com/detalle/usado/bmw/z4/2022/medellin/7a0917d0-534c-42da-ba82-0ca33e8c677e",
     "Portal CarroYa; precio y km se cargan por JavaScript y no fueron accesibles"),
]

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=10)
BASE = Font(name="Arial", size=10)
NOTE_FONT = Font(name="Arial", size=9, italic=True, color="595959")
LINK_FONT = Font(name="Arial", size=9, color="0563C1", underline="single")
THIN = Border(*[Side(style="thin", color="BFBFBF")]*4)

wb = Workbook()

# ================= Hoja 1: Avisos =================
ws = wb.active
ws.title = "Avisos"
headers = ["#", "Fuente", "Modelo / Versión", "Precio venta (COP)", "Año modelo",
           "Generación", "Cilindraje (cc)", "Kilometraje (km)", "Ciudad",
           "¿Para reparar?", "Link del aviso", "Nota / supuesto"]
ws.append(headers)
for c in range(1, len(headers)+1):
    cell = ws.cell(row=1, column=c)
    cell.fill, cell.font = HDR_FILL, HDR_FONT
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = THIN

for i, r in enumerate(rows, start=1):
    fuente, titulo, precio, anio, gen, cc, km, ciudad, reparar, link, nota = r
    vals = [i, fuente, titulo,
            precio if precio is not None else "ND",
            anio if anio is not None else "ND",
            gen,
            cc if cc is not None else "ND",
            km if km is not None else "ND",
            ciudad if ciudad is not None else "ND",
            reparar, link, nota]
    ws.append(vals)
    rr = i + 1
    for c in range(1, len(headers)+1):
        cell = ws.cell(row=rr, column=c)
        cell.font = BASE
        cell.border = THIN
        cell.alignment = Alignment(vertical="top", wrap_text=(c in (3, 12)))
    ws.cell(row=rr, column=4).number_format = '$#,##0'
    lc = ws.cell(row=rr, column=11)
    lc.hyperlink = link
    lc.font = LINK_FONT
    lc.alignment = Alignment(vertical="top", wrap_text=True)
    ws.cell(row=rr, column=12).font = NOTE_FONT

widths = [4, 15, 26, 16, 9, 16, 12, 13, 10, 12, 46, 40]
for c, w in enumerate(widths, start=1):
    ws.column_dimensions[get_column_letter(c)].width = w
ws.freeze_panes = "A2"

n = len(rows)
last = n + 1
note_row = last + 2
ws.cell(row=note_row, column=1,
        value=("ND = dato no disponible públicamente en el resultado de búsqueda. TuCarro, MercadoLibre, "
               "CarroYa, Mitula y otros portales colombianos bloquean la lectura automatizada de sus páginas "
               "(error 403 / robots.txt), por lo que kilometraje y ciudad no pudieron extraerse aviso por aviso. "
               "Datos recolectados el 24-08-2026 vía resultados de búsqueda indexados de cada aviso.")).font = NOTE_FONT
ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row+2, end_column=12)
ws.cell(row=note_row, column=1).alignment = Alignment(wrap_text=True, vertical="top")

# ================= Hoja 2: Análisis =================
wa = wb.create_sheet("Análisis de precios")
wa.column_dimensions["A"].width = 42
for col, w in zip("BCDE", (18, 18, 18, 18)):
    wa.column_dimensions[col].width = w

def title_cell(row, text):
    c = wa.cell(row=row, column=1, value=text)
    c.font = Font(name="Arial", bold=True, size=11, color="1F4E79")
    return c

def kv(row, label, formula, fmt='$#,##0'):
    a = wa.cell(row=row, column=1, value=label); a.font = BASE; a.border = THIN
    b = wa.cell(row=row, column=2, value=formula); b.font = BASE; b.border = THIN
    b.number_format = fmt

title_cell(1, "Caracterización de precios — BMW Z4 usado en Colombia (24-ago-2026)")

price_rng = f"Avisos!D2:D{last}"
kv(3,  "Avisos encontrados (total)", f"=COUNTA(Avisos!A2:A{last})", '0')
kv(4,  "Avisos con precio publicado", f"=COUNT({price_rng})", '0')
kv(5,  "Precio mínimo", f"=MIN({price_rng})")
kv(6,  "Precio máximo", f"=MAX({price_rng})")
kv(7,  "Precio promedio", f"=AVERAGE({price_rng})")
kv(8,  "Mediana", f"=MEDIAN({price_rng})")
kv(9,  "Desviación estándar", f"=STDEV({price_rng})")
kv(10, "Cuartil 1 (25%)", f"=QUARTILE({price_rng},1)")
kv(11, "Cuartil 3 (75%)", f"=QUARTILE({price_rng},3)")

title_cell(13, "Precios por segmento / generación")
seg_headers = ["Segmento", "N.º avisos con precio", "Promedio", "Mínimo", "Máximo"]
for c, h in enumerate(seg_headers, start=1):
    cell = wa.cell(row=14, column=c, value=h)
    cell.fill, cell.font, cell.border = HDR_FILL, HDR_FONT, THIN
    cell.alignment = Alignment(horizontal="center", wrap_text=True)

gen_rng = f"Avisos!F2:F{last}"
segments = [("E86 (2006-2008) — coupé 3.0si", "E86*"),
            ("E89 (2009-2016) — sDrive20i / 23i", "E89*"),
            ("G29 (2019+) — sDrive20i", "G29*~?sDrive20i-part"),  # placeholder, replaced below
            ("G29 (2019+) — M40i", None)]
# Simpler: segment by generación only, and separately by cilindraje
seg_rows = [("E86 (2006-2008)", '"E86*"'),
            ("E89 (2009-2016)", '"E89*"'),
            ("G29 (2019 en adelante)", '"G29*"')]
r0 = 15
for i, (name, crit) in enumerate(seg_rows):
    r = r0 + i
    wa.cell(row=r, column=1, value=name)
    wa.cell(row=r, column=2, value=f'=COUNTIFS({gen_rng},{crit},{price_rng},">0")')
    wa.cell(row=r, column=3, value=f'=IFERROR(AVERAGEIFS({price_rng},{gen_rng},{crit}),"—")')
    wa.cell(row=r, column=4, value=f'=IFERROR(SUMPRODUCT(MIN(IF(({gen_rng}={crit})*({price_rng}>0),{price_rng}))),"—")')
    wa.cell(row=r, column=5, value=f'=IFERROR(SUMPRODUCT(MAX(({gen_rng}={crit})*({price_rng}))),"—")')

# MIN/MAX with wildcards won't work in SUMPRODUCT; use MINIFS/MAXIFS with _xlfn prefix instead
for i, (name, crit) in enumerate(seg_rows):
    r = r0 + i
    wa.cell(row=r, column=4, value=f'=IFERROR(_xlfn.MINIFS({price_rng},{gen_rng},{crit}),"—")')
    wa.cell(row=r, column=5, value=f'=IFERROR(_xlfn.MAXIFS({price_rng},{gen_rng},{crit}),"—")')
    for c in range(1, 6):
        cell = wa.cell(row=r, column=c)
        cell.font, cell.border = BASE, THIN
        if c >= 3:
            cell.number_format = '$#,##0'
        if c == 2:
            cell.number_format = '0'

title_cell(20, "Precios por cilindraje")
cc_headers = ["Cilindraje (cc)", "N.º avisos con precio", "Promedio", "Mínimo", "Máximo"]
for c, h in enumerate(cc_headers, start=1):
    cell = wa.cell(row=21, column=c, value=h)
    cell.fill, cell.font, cell.border = HDR_FILL, HDR_FONT, THIN
    cell.alignment = Alignment(horizontal="center", wrap_text=True)
cc_rng = f"Avisos!G2:G{last}"
cc_vals = [("≈2.000 cc (2.0 turbo)", 1997, 1998), ("2.497 cc (2.5)", 2497, 2497), ("≈3.000 cc (3.0)", 2996, 2998)]
for i, (label, lo, hi) in enumerate(cc_vals):
    r = 22 + i
    wa.cell(row=r, column=1, value=label)
    wa.cell(row=r, column=2, value=f'=COUNTIFS({cc_rng},">="&{lo},{cc_rng},"<="&{hi},{price_rng},">0")')
    wa.cell(row=r, column=3, value=f'=IFERROR(AVERAGEIFS({price_rng},{cc_rng},">="&{lo},{cc_rng},"<="&{hi}),"—")')
    wa.cell(row=r, column=4, value=f'=IFERROR(_xlfn.MINIFS({price_rng},{cc_rng},">="&{lo},{cc_rng},"<="&{hi}),"—")')
    wa.cell(row=r, column=5, value=f'=IFERROR(_xlfn.MAXIFS({price_rng},{cc_rng},">="&{lo},{cc_rng},"<="&{hi}),"—")')
    for c in range(1, 6):
        cell = wa.cell(row=r, column=c)
        cell.font, cell.border = BASE, THIN
        if c >= 3:
            cell.number_format = '$#,##0'
        if c == 2:
            cell.number_format = '0'

title_cell(26, "Hallazgos")
findings = [
    "• Se identificaron 13 avisos activos de BMW Z4 usado en Colombia (12 con link directo en TuCarro/MercadoLibre y 1 en CarroYa); 11 publican precio.",
    "• El mercado se divide en dos bloques claros: generaciones anteriores E86/E89 (2006-2016) entre $105 y $198 millones, y la generación actual G29 (2019+) entre $196 y $335 millones.",
    "• Dentro de la G29, la versión de entrada sDrive20i (2.0T, 1.998 cc) ronda $196-206 millones, mientras la M40i (3.0T, 2.998 cc) va de $250 a $335 millones.",
    "• Ningún aviso se anuncia como chocado o 'para reparar'; todos se ofrecen como vehículos funcionales. Una búsqueda específica de Z4 chocados en Colombia no arrojó resultados.",
    "• Por localización solo hay datos parciales: agregadores reportan 4 avisos en Bogotá y 2 en Cali (Mitula) y 1 en Medellín (CarroYa); los portales no permitieron extraer la ciudad de cada aviso individual.",
    "• Limitación: TuCarro/MercadoLibre, CarroYa, Mitula y similares bloquean la lectura automatizada (403/robots.txt), por lo que kilometraje y ciudad por aviso no están disponibles; el cilindraje se derivó de la versión indicada en el título de cada aviso.",
]
for i, f in enumerate(findings):
    r = 27 + i
    cell = wa.cell(row=r, column=1, value=f)
    cell.font = BASE
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    wa.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    wa.row_dimensions[r].height = 30

wb.save("/home/claude/bmw_z4_usados_colombia.xlsx")
print("saved")
