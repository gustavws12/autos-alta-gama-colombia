#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente de la API oficial de MercadoLibre.

Aisla TODO el acceso a la red en una sola clase, para que el resto de la
rutina sea codigo puro y se pueda probar sin conexion (ver --simular).

Documentacion: https://developers.mercadolibre.com.co
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.mercadolibre.com"
TOKEN_URL = f"{BASE}/oauth/token"
SITIO = "MCO"                      # MercadoLibre Colombia
CATEGORIA_CARROS = "MCO1744"       # Carros, Camionetas y 4x4

# Tope de la busqueda publica: offset + limit no puede pasar de 1000.
TOPE_OFFSET = 1000
LIMITE_PAGINA = 50


class ErrorAPI(RuntimeError):
    """Error de la API que no tiene sentido reintentar."""


class ErrorCredenciales(ErrorAPI):
    pass


def _leer_json(resp) -> dict:
    return json.loads(resp.read().decode("utf-8"))


class ApiML:
    """
    Cliente minimo sobre urllib (sin dependencias externas).

    Maneja:
      - token de aplicacion (grant_type=client_credentials) y su renovacion
      - reintentos con espera creciente en 429 / 5xx
      - un retardo fijo entre llamadas para no golpear la API

    Si no se le pasan credenciales funciona en MODO ANONIMO: hace las
    llamadas sin cabecera de autorizacion. Algunos recursos publicos de
    MercadoLibre todavia responden asi; si el que se necesita no responde,
    la rutina lo dice claramente y pide las credenciales.
    """

    def __init__(self, client_id: str | None, client_secret: str | None,
                 pausa: float = 0.35, reintentos: int = 4,
                 verboso: bool = True):
        self.client_id = client_id
        self.client_secret = client_secret
        self.pausa = pausa
        self.reintentos = reintentos
        self.verboso = verboso
        self._token = None
        self._token_vence = 0.0
        self.llamadas = 0

    @property
    def anonimo(self) -> bool:
        return not (self.client_id and self.client_secret)

    # ------------------------------------------------------------------ token
    def token(self) -> str | None:
        if self.anonimo:
            return None
        if self._token and time.time() < self._token_vence - 60:
            return self._token
        datos = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }).encode("utf-8")
        pet = urllib.request.Request(
            TOKEN_URL, data=datos,
            headers={"Accept": "application/json",
                     "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(pet, timeout=30) as resp:
                cuerpo = _leer_json(resp)
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:400]
            raise ErrorCredenciales(
                f"MercadoLibre rechazo las credenciales (HTTP {e.code}).\n"
                f"Respuesta: {detalle}\n"
                "Revisa client_id y client_secret en credenciales.json."
            ) from None
        self._token = cuerpo["access_token"]
        self._token_vence = time.time() + int(cuerpo.get("expires_in", 21600))
        if self.verboso:
            print("  token obtenido, vigencia "
                  f"{int(cuerpo.get('expires_in', 0)) // 60} min")
        return self._token

    # -------------------------------------------------------------------- get
    def get(self, ruta: str, **params) -> dict:
        """GET a la API. `ruta` empieza con '/'. Devuelve el JSON ya parseado."""
        url = f"{BASE}{ruta}"
        if params:
            limpio = {k: v for k, v in params.items() if v not in (None, "")}
            url += "?" + urllib.parse.urlencode(limpio)

        espera = 1.5
        for intento in range(1, self.reintentos + 1):
            cabeceras = {
                "Accept": "application/json",
                "User-Agent": "analisis-autos-alta-gama/1.0",
            }
            tk = self.token()
            if tk:
                cabeceras["Authorization"] = f"Bearer {tk}"
            pet = urllib.request.Request(url, headers=cabeceras)
            try:
                time.sleep(self.pausa)
                with urllib.request.urlopen(pet, timeout=45) as resp:
                    self.llamadas += 1
                    return _leer_json(resp)
            except urllib.error.HTTPError as e:
                cuerpo = e.read().decode("utf-8", "replace")[:300]
                if e.code in (401, 403):
                    if self.anonimo:
                        raise ErrorCredenciales(
                            "MercadoLibre exige credenciales para esta consulta "
                            f"(HTTP {e.code}).\n"
                            "Crea tu aplicacion en "
                            "https://developers.mercadolibre.com.co/devcenter "
                            "y pega client_id y client_secret en "
                            "credenciales.json.") from None
                    # Token vencido o revocado: se pide uno nuevo y se reintenta.
                    self._token = None
                    if intento == self.reintentos:
                        raise ErrorCredenciales(
                            f"{e.code} de la API tras {intento} intentos: {cuerpo}")
                elif e.code in (429, 500, 502, 503, 504):
                    if intento == self.reintentos:
                        raise ErrorAPI(
                            f"HTTP {e.code} tras {intento} intentos en {ruta}: "
                            f"{cuerpo}")
                    if self.verboso:
                        print(f"  HTTP {e.code}, reintento {intento} "
                              f"en {espera:.0f}s…")
                    time.sleep(espera)
                    espera *= 2
                else:
                    raise ErrorAPI(f"HTTP {e.code} en {url}: {cuerpo}") from None
            except urllib.error.URLError as e:
                if intento == self.reintentos:
                    raise ErrorAPI(
                        f"No hay conexion con la API ({e.reason}). "
                        "Revisa tu internet, proxy o antivirus.") from None
                time.sleep(espera)
                espera *= 2
        raise ErrorAPI(f"No se pudo completar {ruta}")

    # --------------------------------------------------------------- busqueda
    def buscar_pagina(self, consulta: str, offset: int = 0,
                      precio_min=None, precio_max=None,
                      condicion: str | None = None,
                      categoria: str = CATEGORIA_CARROS) -> dict:
        params = {
            "q": consulta,
            "category": categoria,
            "limit": LIMITE_PAGINA,
            "offset": offset,
        }
        if condicion:
            params["condition"] = condicion
        if precio_min is not None or precio_max is not None:
            desde = int(precio_min) if precio_min is not None else ""
            hasta = int(precio_max) if precio_max is not None else "*"
            params["price"] = f"{desde or '*'}-{hasta}"
        return self.get(f"/sites/{SITIO}/search", **params)

    def items(self, ids: list[str]) -> list[dict]:
        """Detalle de hasta 20 avisos por llamada (multiget)."""
        salida = []
        for i in range(0, len(ids), 20):
            lote = ids[i:i + 20]
            crudo = self.get("/items", ids=",".join(lote))
            # El multiget devuelve [{code, body}, ...]
            for entrada in crudo if isinstance(crudo, list) else []:
                if entrada.get("code") == 200 and entrada.get("body"):
                    salida.append(entrada["body"])
        return salida


# ---------------------------------------------------------------- credenciales
PLANTILLA_CREDENCIALES = {
    "client_id": "PEGA_AQUI_TU_CLIENT_ID",
    "client_secret": "PEGA_AQUI_TU_CLIENT_SECRET",
    "_como_obtenerlas": (
        "1. Inicia sesion en MercadoLibre. "
        "2. Entra DIRECTO a https://developers.mercadolibre.com.co/devcenter "
        "(el menu de aplicaciones no siempre aparece en la pagina de inicio). "
        "3. Boton 'Crear aplicacion'. Nombre y descripcion cualquiera; en "
        "'URI de redirect' pon https://localhost ; marca el scope 'read'. "
        "4. Copia el App ID (client_id) y la Secret Key (client_secret) aqui. "
        "5. No compartas este archivo: la clave es personal."
    ),
}


def cargar_credenciales(ruta: Path) -> tuple[str | None, str | None]:
    """
    Busca las credenciales en, por este orden:
      1. variables de entorno ML_CLIENT_ID / ML_CLIENT_SECRET
      2. el archivo credenciales.json junto al script

    Devuelve (None, None) cuando no hay ninguna configurada, para que quien
    llame pueda intentar en modo anonimo en vez de detenerse. Si el archivo
    no existe, lo crea con la plantilla lista para llenar.
    """
    cid = os.environ.get("ML_CLIENT_ID", "").strip()
    sec = os.environ.get("ML_CLIENT_SECRET", "").strip()
    if cid and sec:
        return cid, sec

    if not ruta.exists():
        ruta.write_text(
            json.dumps(PLANTILLA_CREDENCIALES, indent=2, ensure_ascii=False),
            encoding="utf-8")
        return None, None

    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErrorCredenciales(
            f"{ruta.name} no es un JSON valido ({e}). Revisa que no falten "
            "comillas o comas.") from None
    cid = str(datos.get("client_id", "")).strip()
    sec = str(datos.get("client_secret", "")).strip()
    if not cid or not sec or cid.startswith("PEGA_AQUI"):
        return None, None
    return cid, sec
