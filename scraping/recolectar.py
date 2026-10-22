#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recoleccion de avisos de autos deportivos y de alta gama en Colombia,
usando la API oficial de MercadoLibre (que es la misma plataforma de TuCarro).

Uso tipico
----------
    python recolectar.py                 # corrida normal
    python recolectar.py --simular       # prueba sin internet ni credenciales
    python recolectar.py --sin-red       # rearma el Excel con lo ya descargado
    python recolectar.py --solo Porsche  # una sola marca
    python recolectar.py --max 100       # tope de avisos por busqueda

Que produce
-----------
    deportivos_alta_gama_colombia.xlsx   hoja "Avisos" + hoja "Calidad"
    fotos.csv                            id,url para el marketplace del tablero
    datos_crudos/<marca>_<modelo>.json   el JSON tal cual lo devolvio la API
    reporte_calidad.txt                  resumen legible de la corrida

El Excel conserva EXACTAMENTE las columnas que espera app.R, asi que el
tablero de Shiny sigue funcionando sin tocar una linea.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_ml import (ApiML, ErrorAPI, ErrorCredenciales, LIMITE_PAGINA,
                    TOPE_OFFSET, cargar_credenciales)
from extraer import clave, esta_vivo, normalizar


AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent                      # la carpeta del proyecto
CRUDOS = AQUI / "datos_crudos"
FIXTURES = AQUI / "pruebas" / "fixtures"

ARCHIVO_BUSQUEDAS = AQUI / "busquedas.csv"
ARCHIVO_CREDENCIALES = AQUI / "credenciales.json"
SALIDA_XLSX = RAIZ / "deportivos_alta_gama_colombia.xlsx"
SALIDA_FOTOS = RAIZ / "fotos.csv"
SALIDA_REPORTE = AQUI / "reporte_calidad.txt"

# Encabezados EXACTOS que lee app.R. No cambiar el orden ni el texto inicial
# de cada uno sin revisar la funcion col() del tablero.
COLUMNAS = [
    "#", "Marca", "Modelo", "Fuente", "Título del aviso",
    "Precio venta (COP)", "Año modelo", "Versión / generación",
    "Cilindraje (cc)", "Kilometraje (km)", "Ciudad", "¿Para reparar?",
    "Registro", "Link del aviso", "Nota / supuesto",
    # Columnas nuevas: el tablero las ignora, pero sirven para auditar.
    "Departamento", "Estado del aviso", "Condición", "ID del aviso",
    "URL de la foto", "Precio en moneda original", "Moneda",
    "Marca buscada", "Modelo buscado", "Búsqueda que lo encontró",
    "Fecha de recolección",
]


def marca_coincide(registro: dict) -> bool:
    """
    Descarta el ruido de la busqueda. Consultar "Porsche 911" tambien devuelve
    accesorios y carros de otras marcas; si el aviso declara su marca y no es
    la que se buscaba, no entra. Cuando el aviso no declara marca se conserva,
    porque no hay con que contradecir la busqueda.
    """
    if not registro.get("marca_api"):
        return True
    a = clave(registro["marca_api"]).replace("-", " ").replace("benz", "").strip()
    b = clave(registro.get("marca_buscada")).replace("-", " ").replace("benz", "").strip()
    return a.startswith(b) or b.startswith(a)


# ============================================================ configuracion
def leer_busquedas(ruta: Path) -> list[dict]:
    if not ruta.exists():
        raise SystemExit(
            f"No encuentro {ruta.name}. Deberia estar junto a este script.")
    filas = []
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        for i, fila in enumerate(csv.DictReader(f), start=2):
            fila = {(k or "").strip().lower(): (v or "").strip()
                    for k, v in fila.items()}
            if clave(fila.get("activo", "si")) in ("no", "0", "false", ""):
                continue
            if not fila.get("marca") or not fila.get("consulta"):
                print(f"  aviso: fila {i} de busquedas.csv sin marca o consulta, "
                      "se salta")
                continue
            filas.append({
                "marca": fila["marca"],
                "modelo": fila.get("modelo") or fila["marca"],
                "consulta": fila["consulta"],
                "precio_min": _num(fila.get("precio_min")),
                "precio_max": _num(fila.get("precio_max")),
            })
    if not filas:
        raise SystemExit("busquedas.csv no tiene ninguna fila activa.")
    return filas


def _num(x):
    x = (x or "").replace(".", "").replace(",", "").strip()
    return int(x) if x.isdigit() else None


# ================================================================= descarga
def recolectar_busqueda(api: ApiML, fila: dict, tope: int,
                        condicion: str | None) -> list[dict]:
    """
    Trae los avisos de una busqueda. La busqueda publica solo deja llegar
    hasta el aviso 1000; cuando hay mas, se parte por rangos de precio para
    no perder nada.
    """
    vistos: dict[str, dict] = {}
    rangos = [(fila["precio_min"], fila["precio_max"])]

    while rangos:
        pmin, pmax = rangos.pop(0)
        offset = 0
        total = None
        while offset < TOPE_OFFSET and len(vistos) < tope:
            pagina = api.buscar_pagina(fila["consulta"], offset=offset,
                                       precio_min=pmin, precio_max=pmax,
                                       condicion=condicion)
            resultados = pagina.get("results") or []
            if total is None:
                total = int((pagina.get("paging") or {}).get("total", 0))
                if total > TOPE_OFFSET and (pmin is None or pmax is None
                                            or pmax - pmin > 5_000_000):
                    corte = _punto_medio(pmin, pmax)
                    if corte:
                        print(f"    {total} avisos: se parte el rango de precio "
                              f"en {corte:,}".replace(",", "."))
                        rangos.append((pmin, corte))
                        rangos.append((corte + 1, pmax))
                        break
            if not resultados:
                break
            for it in resultados:
                if it.get("id"):
                    vistos[it["id"]] = it
            offset += LIMITE_PAGINA
    return list(vistos.values())


def _punto_medio(pmin, pmax):
    bajo = pmin if pmin is not None else 20_000_000
    alto = pmax if pmax is not None else 1_500_000_000
    medio = (bajo + alto) // 2
    return medio if alto - bajo > 5_000_000 else None


def enriquecer(api: ApiML, resultados: list[dict]) -> list[dict]:
    """
    El resultado de busqueda ya trae precio, permalink y ubicacion, pero el
    detalle del aviso trae ademas todos los atributos (ano, cilindraje,
    kilometraje) y las fotos en tamano grande. Se mezclan los dos.
    """
    por_id = {r["id"]: dict(r) for r in resultados if r.get("id")}
    detalles = api.items(list(por_id))
    for det in detalles:
        base = por_id.get(det.get("id"))
        if base is None:
            continue
        # El detalle manda, pero se conserva 'address' de la busqueda porque
        # el detalle a veces solo trae seller_address.
        direccion = base.get("address")
        base.update(det)
        if direccion and not det.get("address"):
            base["address"] = direccion
    return list(por_id.values())


# ================================================================== armado
def deduplicar(registros: list[dict]) -> tuple[list[dict], int]:
    """
    Un mismo aviso puede aparecer en varias busquedas y bajo los dos dominios
    (TuCarro y MercadoLibre). El id del aviso es el mismo, asi que ese es el
    criterio. Se marca cual quedo como unico y cual como espejo.
    """
    por_id: dict[str, dict] = {}
    espejos = 0
    for r in registros:
        clave_id = r.get("id_aviso")
        if not clave_id:
            continue
        if clave_id in por_id:
            espejos += 1
            previo = por_id[clave_id]
            # Se prefiere el que tenga precio, y luego el que tenga foto.
            mejor = max((previo, r),
                        key=lambda x: ((x["precio"] is not None),
                                       (x["foto"] is not None),
                                       (x["anio"] is not None)))
            mejor["registro"] = "Único"
            por_id[clave_id] = mejor
        else:
            r["registro"] = "Único"
            por_id[clave_id] = r
    return list(por_id.values()), espejos


def escribir_xlsx(registros: list[dict], calidad: dict, ruta: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    hoy = datetime.now().strftime("%Y-%m-%d")
    wb = Workbook()
    ws = wb.active
    ws.title = "Avisos"
    ws.append(COLUMNAS)

    for i, r in enumerate(registros, start=1):
        ws.append([
            i, r["marca"], r["modelo"], r["portal"], r["titulo"],
            r["precio"] if r["precio"] is not None else "ND",
            r["anio"] if r["anio"] is not None else "ND",
            r["version"] or "ND",
            r["cc"] if r["cc"] is not None else "ND",
            r["km"] if r["km"] is not None else "ND",
            r["ciudad"] or "ND",
            r["para_reparar"], r.get("registro", "Único"), r["link"] or "",
            r["nota"], r["departamento"] or "ND", r["estado"] or "",
            r["condicion"] or "", r["id_aviso"], r["foto"] or "",
            r.get("precio_moneda_original") if r.get("precio_moneda_original")
                is not None else "",
            r.get("moneda") or "COP",
            r.get("marca_buscada") or "", r.get("modelo_buscado") or "",
            r["consulta"], hoy,
        ])

    encabezado = Font(bold=True, color="FFFFFF")
    relleno = PatternFill("solid", fgColor="184F95")
    for celda in ws[1]:
        celda.font = encabezado
        celda.fill = relleno
        celda.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNAS))}{ws.max_row}"

    anchos = {"A": 5, "B": 15, "C": 20, "D": 17, "E": 46, "F": 17, "G": 11,
              "H": 34, "I": 13, "J": 15, "K": 16, "L": 17, "M": 10, "N": 52,
              "O": 46, "P": 18, "Q": 15, "R": 12, "S": 15, "T": 46}
    for col, ancho in anchos.items():
        ws.column_dimensions[col].width = ancho
    for fila in range(2, ws.max_row + 1):
        ws.cell(fila, 6).number_format = '"$"#,##0'
        ws.cell(fila, 9).number_format = "#,##0"
        ws.cell(fila, 10).number_format = "#,##0"

    # ------------------------------------------------------ hoja de calidad
    wq = wb.create_sheet("Calidad")
    wq.append(["Reporte de calidad de la recolección", ""])
    wq.append(["Fecha", hoy])
    wq.append([])
    for etiqueta, valor in calidad.items():
        wq.append([etiqueta, valor])
    wq["A1"].font = Font(bold=True, size=13)
    wq.column_dimensions["A"].width = 46
    wq.column_dimensions["B"].width = 20

    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)


def escribir_fotos(registros: list[dict], ruta: Path) -> int:
    con_foto = [r for r in registros if r.get("foto")]
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "url"])
        for r in con_foto:
            w.writerow([r["id_aviso"], r["foto"]])
    return len(con_foto)


def respaldar(ruta: Path) -> Path | None:
    if not ruta.exists():
        return None
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    destino = ruta.with_name(f"{ruta.stem}_respaldo_{sello}{ruta.suffix}")
    shutil.copy2(ruta, destino)
    return destino


def medir_calidad(registros: list[dict], espejos: int, descartados: int,
                  llamadas: int) -> dict:
    n = len(registros) or 1
    def pct(cuantos):
        return f"{cuantos} de {len(registros)}  ({100 * cuantos / n:.0f} %)"
    return {
        "Avisos únicos guardados": len(registros),
        "Avisos repetidos entre búsquedas": espejos,
        "Avisos descartados por estar cerrados o pausados": descartados,
        "Con precio publicado": pct(sum(r["precio"] is not None for r in registros)),
        "Con año del modelo": pct(sum(r["anio"] is not None for r in registros)),
        "Con año tomado del campo del aviso":
            pct(sum(r["anio"] is not None and "deducido" not in r["nota"]
                    for r in registros)),
        "Con ciudad": pct(sum(bool(r["ciudad"]) for r in registros)),
        "Con kilometraje": pct(sum(r["km"] is not None for r in registros)),
        "Con cilindraje": pct(sum(r["cc"] is not None for r in registros)),
        "Con foto": pct(sum(bool(r["foto"]) for r in registros)),
        "Con marca tomada del aviso":
            pct(sum(bool(r.get("marca_api")) for r in registros)),
        "Precios en moneda distinta al peso (excluidos)":
            sum(r.get("precio_moneda_original") is not None for r in registros),
        "Con enlace": pct(sum(bool(r["link"]) for r in registros)),
        "Llamadas a la API": llamadas,
    }


# ============================================================== simulacion
def cargar_simulacion() -> dict:
    """Carga los avisos de prueba para correr sin internet ni credenciales."""
    ruta = FIXTURES / "avisos_ejemplo.json"
    if not ruta.exists():
        raise SystemExit(f"No encuentro los datos de prueba en {ruta}")
    return json.loads(ruta.read_text(encoding="utf-8"))


class ApiSimulada:
    """Reemplazo de ApiML que responde desde los archivos de prueba."""

    def __init__(self):
        self.datos = cargar_simulacion()
        self.llamadas = 0

    def buscar_pagina(self, consulta, offset=0, **kw):
        self.llamadas += 1
        if offset > 0:
            return {"results": [], "paging": {"total": 0}}
        res = [dict(a) for a in self.datos["busqueda"]
               if clave(consulta).split()[0] in clave(a.get("title"))]
        return {"results": res, "paging": {"total": len(res)}}

    def items(self, ids):
        self.llamadas += 1
        return [dict(d) for d in self.datos["detalle"] if d["id"] in set(ids)]


# ==================================================================== main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Recolecta avisos de alta gama desde la API de MercadoLibre.")
    ap.add_argument("--simular", action="store_true",
                    help="corre con datos de prueba, sin internet ni credenciales")
    ap.add_argument("--sin-red", action="store_true",
                    help="rearma el Excel con el JSON ya descargado en datos_crudos")
    ap.add_argument("--solo", metavar="MARCA",
                    help="procesa solo las búsquedas de esa marca")
    ap.add_argument("--max", type=int, default=400, metavar="N",
                    help="tope de avisos por búsqueda (por defecto 400)")
    ap.add_argument("--condicion", default="used",
                    choices=["used", "new", "todas"],
                    help="condición del vehículo (por defecto usados)")
    ap.add_argument("--sin-respaldo", action="store_true",
                    help="no guardar copia del Excel anterior")
    ap.add_argument("--sin-filtro-marca", action="store_true",
                    help="conservar avisos cuya marca no coincide con la búsqueda")
    args = ap.parse_args(argv)

    CRUDOS.mkdir(parents=True, exist_ok=True)
    busquedas = leer_busquedas(ARCHIVO_BUSQUEDAS)
    if args.solo:
        busquedas = [b for b in busquedas
                     if clave(args.solo) in clave(b["marca"])]
        if not busquedas:
            raise SystemExit(f"Ninguna búsqueda activa para la marca {args.solo}")

    condicion = None if args.condicion == "todas" else args.condicion

    print(f"\n{'=' * 68}")
    print("  Recolección de autos deportivos y de alta gama · Colombia")
    print(f"  {len(busquedas)} búsquedas activas · "
          f"{'MODO SIMULACIÓN' if args.simular else 'API de MercadoLibre'}")
    print(f"{'=' * 68}\n")

    # ------------------------------------------------------------ obtener
    if args.simular:
        api = ApiSimulada()
    elif args.sin_red:
        api = None
    else:
        try:
            cid, sec = cargar_credenciales(ARCHIVO_CREDENCIALES)
        except ErrorCredenciales as e:
            print(f"\n[!] {e}\n")
            return 2
        api = ApiML(cid, sec)
        if api.anonimo:
            print("Sin credenciales configuradas: se intenta en modo anónimo.")
            print("Si MercadoLibre las exige, la rutina te lo dirá y se detiene")
            print("sin dañar nada. Para configurarlas, mira LEEME_SCRAPING.md.\n")
        else:
            print("Autenticando…")

    registros: list[dict] = []
    descartados = 0
    fuera_de_marca = 0

    for i, fila in enumerate(busquedas, start=1):
        etiqueta = f"{fila['marca']} {fila['modelo']}"
        archivo = CRUDOS / f"{_slug(fila['marca'])}__{_slug(fila['modelo'])}.json"
        print(f"[{i:>2}/{len(busquedas)}] {etiqueta:<34} ", end="", flush=True)

        if args.sin_red:
            if not archivo.exists():
                print("sin datos descargados, se salta")
                continue
            crudos = json.loads(archivo.read_text(encoding="utf-8"))
        else:
            try:
                encontrados = recolectar_busqueda(api, fila, args.max, condicion)
                crudos = (enriquecer(api, encontrados) if encontrados else [])
            except ErrorCredenciales as e:
                print(f"\n\n[!] {e}\n")
                return 2
            except ErrorAPI as e:
                print(f"error: {e}")
                continue
            archivo.write_text(
                json.dumps(crudos, ensure_ascii=False, indent=1),
                encoding="utf-8")

        vivos = [c for c in crudos if esta_vivo(c)]
        descartados += len(crudos) - len(vivos)
        nuevos = [normalizar(it, fila["marca"], fila["modelo"], fila["consulta"])
                  for it in vivos]
        if not args.sin_filtro_marca:
            antes = len(nuevos)
            nuevos = [r for r in nuevos if marca_coincide(r)]
            fuera_de_marca += antes - len(nuevos)
        registros.extend(nuevos)
        print(f"{len(nuevos):>4} avisos vigentes "
              f"({len(crudos) - len(vivos)} cerrados/pausados, "
              f"{len(vivos) - len(nuevos)} de otra marca)")

    if not registros:
        print("\n[!] No se recolectó ningún aviso. Nada que escribir.")
        return 1

    # ------------------------------------------------------------- escribir
    registros, espejos = deduplicar(registros)
    registros.sort(key=lambda r: (clave(r["marca"]), clave(r["modelo"]),
                                  -(r["precio"] or 0)))

    llamadas = getattr(api, "llamadas", 0) if api else 0
    calidad = medir_calidad(registros, espejos, descartados, llamadas)
    calidad["Avisos descartados por ser de otra marca"] = fuera_de_marca

    if not args.sin_respaldo:
        copia = respaldar(SALIDA_XLSX)
        if copia:
            print(f"\nRespaldo del Excel anterior: {copia.name}")

    escribir_xlsx(registros, calidad, SALIDA_XLSX)
    n_fotos = escribir_fotos(registros, SALIDA_FOTOS)

    lineas = ["Reporte de calidad de la recolección",
              datetime.now().strftime("%Y-%m-%d %H:%M"), "-" * 52]
    lineas += [f"{k:<48} {v}" for k, v in calidad.items()]
    SALIDA_REPORTE.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print(f"\n{'-' * 68}")
    for k, v in calidad.items():
        print(f"  {k:<48} {v}")
    print(f"{'-' * 68}")
    print(f"\n  Excel      {SALIDA_XLSX}")
    print(f"  Fotos      {SALIDA_FOTOS}  ({n_fotos} imágenes)")
    print(f"  Reporte    {SALIDA_REPORTE}")
    print("\n  Abre app.R y pulsa Run App para ver el tablero actualizado.\n")
    return 0


def _slug(texto: str) -> str:
    limpio = clave(texto).replace("/", "-")
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in limpio)


if __name__ == "__main__":
    sys.exit(main())
