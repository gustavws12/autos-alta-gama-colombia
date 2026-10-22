#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extraccion y normalizacion de un aviso de MercadoLibre.

Todo lo de este archivo son funciones puras: reciben el JSON del aviso y
devuelven un diccionario. No tocan la red ni el disco, por eso se pueden
probar completas sin credenciales (ver pruebas/test_extraer.py).

Por que existe este archivo
---------------------------
La version anterior del analisis leia el precio y el ano del TEXTO del
resultado de busqueda, y por eso fallaba: el texto trae "Audi A5 2.0 TFSI"
y el 2.0 se confundia con el ano, o el precio no aparecia. La API entrega
cada dato en su propio campo, asi que aqui NO se adivina nada salvo cuando
el aviso realmente no trae el dato, y en ese caso queda registrado en la
columna "Nota / supuesto".
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

ANIO_ACTUAL = datetime.now().year
ANIO_MIN = 1950
ANIO_MAX = ANIO_ACTUAL + 2

PALABRAS_CHOCADO = (
    "chocado", "chocada", "para repuestos", "por partes", "desguace",
    "siniestrado", "para reparar", "no enciende", "sin papeles",
    "para chatarra", "solo repuestos",
)


# --------------------------------------------------------------------- texto
def sin_tildes(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def clave(texto: str) -> str:
    return sin_tildes(str(texto or "")).strip().lower()


# ---------------------------------------------------------------- atributos
def _atributos(item: dict) -> list[dict]:
    ats = item.get("attributes")
    return ats if isinstance(ats, list) else []


def atributo(item: dict, *ids_o_nombres: str) -> dict | None:
    """
    Busca un atributo por su id (p. ej. VEHICLE_YEAR) o por su nombre visible
    (p. ej. "Ano"), sin distinguir tildes ni mayusculas.
    """
    buscados = {clave(x) for x in ids_o_nombres}
    for at in _atributos(item):
        if clave(at.get("id")) in buscados or clave(at.get("name")) in buscados:
            return at
    return None


def _numero_de(at: dict | None):
    """Saca el numero de un atributo, prefiriendo value_struct sobre el texto."""
    if not at:
        return None, None
    est = at.get("value_struct") or {}
    if est.get("number") is not None:
        return est.get("number"), (est.get("unit") or "").strip().lower()
    texto = at.get("value_name") or at.get("value_id") or ""
    m = re.search(r"([\d]+(?:[.,]\d+)?)", str(texto).replace(".", "")
                  if str(texto).count(".") > 1 else str(texto))
    if not m:
        return None, None
    crudo = m.group(1).replace(",", ".")
    try:
        num = float(crudo)
    except ValueError:
        return None, None
    unidad = str(texto)[m.end():].strip().lower()
    return num, unidad


# -------------------------------------------------------------------- campos
def extraer_anio(item: dict) -> tuple[int | None, str | None]:
    """
    Devuelve (anio, nota). La nota solo se llena cuando el dato NO vino del
    campo del aviso y hubo que deducirlo del titulo.
    """
    at = atributo(item, "VEHICLE_YEAR", "MODEL_YEAR", "ano", "año",
                  "ano del modelo", "año del modelo")
    if at:
        texto = str(at.get("value_name") or "").strip()
        m = re.search(r"\b(19|20)\d{2}\b", texto)
        if m:
            anio = int(m.group(0))
            if ANIO_MIN <= anio <= ANIO_MAX:
                return anio, None

    # Respaldo: un ano de 4 digitos en el titulo. Se marca como deducido.
    titulo = str(item.get("title") or "")
    candidatos = [int(a) for a in re.findall(r"\b(?:19|20)\d{2}\b", titulo)
                  if ANIO_MIN <= int(a) <= ANIO_MAX]
    if len(candidatos) == 1:
        return candidatos[0], "Ano deducido del titulo; el aviso no trae el campo"
    if len(candidatos) > 1:
        return None, ("El titulo tiene mas de un ano posible "
                      f"({', '.join(map(str, candidatos))}); se deja en ND")
    return None, "El aviso no publica el ano del modelo"


def extraer_precio(item: dict) -> tuple[float | None, str | None]:
    """
    Precio EN PESOS. Nunca se deduce del texto: o esta el campo, o es ND.

    Un aviso en dolares se deja en ND a proposito: si se copiara el numero
    tal cual, un Porsche de USD 150.000 entraria a las estadisticas como si
    costara 150 mil pesos y arrastraria la mediana. El valor original queda
    guardado aparte, en la columna de moneda original.
    """
    precio = item.get("price")
    moneda = item.get("currency_id") or "COP"
    if precio is None or (isinstance(precio, (int, float)) and precio <= 0):
        return None, "El aviso no publica precio"
    if moneda != "COP":
        return None, (f"Precio publicado en {moneda} ({precio:,.0f}), no en "
                      "pesos: se deja fuera de las estadisticas")
    return float(precio), None


def extraer_kilometraje(item: dict) -> int | None:
    num, unidad = _numero_de(atributo(item, "KILOMETERS", "kilometros",
                                      "kilometraje"))
    if num is None:
        return None
    if unidad.startswith("mi"):          # millas -> km
        num *= 1.60934
    return int(round(num))


def extraer_cilindraje(item: dict) -> tuple[int | None, str | None]:
    """
    Devuelve el cilindraje en cc. La API lo entrega en litros ("2.0 L") o en
    centimetros cubicos ("1998 cc") segun el aviso; aqui se normaliza a cc.
    """
    at = atributo(item, "ENGINE_DISPLACEMENT", "cilindrada", "cilindraje",
                  "motor")
    num, unidad = _numero_de(at)
    if num is None:
        return None, None
    if unidad.startswith("l") or (num < 20 and not unidad.startswith("c")):
        # 2.0 L -> 2000 cc
        return int(round(num * 1000)), None
    return int(round(num)), None


def extraer_ubicacion(item: dict) -> tuple[str | None, str | None]:
    """
    Ciudad y departamento. La API los trae en 'address' (resultado de busqueda)
    o en 'seller_address' / 'location' (detalle del aviso). Se prueban todos.
    """
    def limpio(x):
        x = (x or "").strip()
        return x or None

    dir_ = item.get("address") or {}
    ciudad = limpio(dir_.get("city_name"))
    depto = limpio(dir_.get("state_name"))
    if ciudad:
        return ciudad, depto

    for llave in ("seller_address", "location"):
        d = item.get(llave) or {}
        c = d.get("city") or {}
        e = d.get("state") or {}
        ciudad = limpio(c.get("name") if isinstance(c, dict) else c)
        depto = limpio(e.get("name") if isinstance(e, dict) else e)
        if ciudad:
            return ciudad, depto
    return None, depto


def extraer_foto(item: dict) -> str | None:
    fotos = item.get("pictures")
    if isinstance(fotos, list) and fotos:
        p = fotos[0]
        url = p.get("secure_url") or p.get("url")
        if url:
            return url
    miniatura = item.get("thumbnail") or ""
    if miniatura:
        # La miniatura de busqueda viene en 100x100; -O da la version grande.
        return miniatura.replace("http://", "https://").replace("-I.jpg", "-O.jpg")
    return None


def extraer_portal(item: dict) -> str:
    """
    TuCarro y MercadoLibre CO son la misma plataforma; lo que cambia es el
    dominio del permalink. De ahi sale el 'portal' donde se ve el aviso.
    """
    enlace = str(item.get("permalink") or "")
    if "tucarro" in enlace:
        return "TuCarro"
    if "mercadolibre" in enlace:
        return "MercadoLibre CO"
    return "MercadoLibre CO"


def para_reparar(item: dict) -> str:
    texto = clave(item.get("title"))
    sub = item.get("sub_status") or []
    if isinstance(sub, str):
        sub = [sub]
    if any(p in texto for p in PALABRAS_CHOCADO):
        return "Si (segun el titulo)"
    if any("deleted" in str(s) for s in sub):
        return "No indicado"
    return "No indicado"


def esta_vivo(item: dict) -> bool:
    """
    Un aviso solo cuenta si sigue publicado. Esto es lo que arregla los links
    que 'no entran': antes se guardaban avisos ya cerrados o pausados.
    """
    if str(item.get("status") or "").lower() != "active":
        return False
    sub = item.get("sub_status") or []
    if isinstance(sub, str):
        sub = [sub]
    return not any(str(s).lower() in ("deleted", "suspended", "expired")
                   for s in sub)


def extraer_version(item: dict) -> str | None:
    partes = []
    for campo in ("TRIM", "version", "VEHICLE_BODY_TYPE"):
        at = atributo(item, campo)
        if at and at.get("value_name"):
            partes.append(str(at["value_name"]).strip())
    at_trans = atributo(item, "TRANSMISSION", "transmision")
    if at_trans and at_trans.get("value_name"):
        partes.append(str(at_trans["value_name"]).strip())
    vistos, salida = set(), []
    for p in partes:
        if clave(p) not in vistos:
            vistos.add(clave(p))
            salida.append(p)
    return " · ".join(salida) if salida else None


# ------------------------------------------------------------------ registro
def normalizar(item: dict, marca_buscada: str, modelo_buscado: str,
               consulta: str) -> dict:
    """Convierte un aviso de la API en la fila que consume el tablero."""
    notas = []

    anio, nota_anio = extraer_anio(item)
    if nota_anio:
        notas.append(nota_anio)

    precio, nota_precio = extraer_precio(item)
    if nota_precio:
        notas.append(nota_precio)

    cc, nota_cc = extraer_cilindraje(item)
    if nota_cc:
        notas.append(nota_cc)
    if cc is None:
        notas.append("El aviso no publica el cilindraje")

    ciudad, depto = extraer_ubicacion(item)
    if not ciudad:
        notas.append("El aviso no publica la ciudad")

    km = extraer_kilometraje(item)
    if km is None:
        notas.append("El aviso no publica el kilometraje")

    # La marca y el modelo salen del propio aviso cuando la API los trae.
    # La etiqueta de la busqueda es solo el respaldo: si se usara siempre,
    # una consulta de "Porsche 911" que devuelve un Cayman lo guardaria como
    # 911, que es justo el tipo de error que hubo en la version anterior.
    at_marca = atributo(item, "BRAND", "marca")
    at_modelo = atributo(item, "MODEL", "modelo")
    marca_api = (at_marca or {}).get("value_name")
    modelo_api = (at_modelo or {}).get("value_name")

    marca = (marca_api or marca_buscada).strip()
    modelo = (modelo_api or modelo_buscado).strip()
    if not marca_api:
        notas.append("Marca tomada de la busqueda; el aviso no la publica")
    if not modelo_api:
        notas.append("Modelo tomado de la busqueda; el aviso no lo publica")

    return {
        "id_aviso": item.get("id"),
        "marca": marca,
        "modelo": modelo,
        "marca_buscada": marca_buscada,
        "modelo_buscado": modelo_buscado,
        "marca_api": marca_api,
        "modelo_api": modelo_api,
        "precio_moneda_original": item.get("price")
            if (item.get("currency_id") or "COP") != "COP" else None,
        "portal": extraer_portal(item),
        "titulo": (item.get("title") or "").strip(),
        "precio": precio,
        "moneda": item.get("currency_id") or "COP",
        "anio": anio,
        "version": extraer_version(item),
        "cc": cc,
        "km": km,
        "ciudad": ciudad,
        "departamento": depto,
        "para_reparar": para_reparar(item),
        "estado": item.get("status"),
        "link": item.get("permalink"),
        "foto": extraer_foto(item),
        "condicion": item.get("condition"),
        "consulta": consulta,
        "nota": "; ".join(notas) if notas else "",
    }
