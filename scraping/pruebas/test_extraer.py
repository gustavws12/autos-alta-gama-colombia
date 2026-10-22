#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas de la extraccion. Se ejecutan sin internet ni credenciales:

    python -m unittest discover -s pruebas -v
    (o simplemente:  python pruebas/test_extraer.py)

Cada prueba corresponde a un problema real encontrado en la version anterior
del analisis.
"""

import json
import sys
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from extraer import (esta_vivo, extraer_anio, extraer_cilindraje, extraer_foto,
                     extraer_kilometraje, extraer_portal, extraer_precio,
                     extraer_ubicacion, normalizar, para_reparar)
from recolectar import deduplicar, marca_coincide

DATOS = json.loads((AQUI / "fixtures" / "avisos_ejemplo.json")
                   .read_text(encoding="utf-8"))
DET = {d["id"]: d for d in DATOS["detalle"]}
BUS = {b["id"]: b for b in DATOS["busqueda"]}


def mezclado(id_):
    """Simula lo que hace enriquecer(): detalle sobre resultado de busqueda."""
    base = dict(BUS[id_])
    direccion = base.get("address")
    base.update(DET[id_])
    if direccion and not DET[id_].get("address"):
        base["address"] = direccion
    return base


class TestAnio(unittest.TestCase):
    def test_anio_viene_del_campo_del_aviso(self):
        anio, nota = extraer_anio(mezclado("MCO111"))
        self.assertEqual(anio, 2021)
        self.assertIsNone(nota, "un año que viene del campo no lleva nota")

    def test_no_confunde_el_cilindraje_con_el_anio(self):
        # Este es el error de la version anterior: "Audi A5 2.0 TFSI" -> 2.0
        item = {"title": "Audi A5 2.0 TFSI Multitronic Convertible",
                "attributes": []}
        anio, nota = extraer_anio(item)
        self.assertIsNone(anio)
        self.assertIn("no publica el año", nota.replace("ano", "año"))

    def test_anio_deducido_del_titulo_queda_marcado(self):
        anio, nota = extraer_anio(mezclado("MCO222"))
        self.assertEqual(anio, 2014)
        self.assertIn("deducido", nota)

    def test_titulo_con_dos_anios_no_adivina(self):
        anio, nota = extraer_anio(mezclado("MCO555"))
        self.assertIsNone(anio, "con dos años posibles no se debe elegir uno")
        self.assertIn("mas de un ano", nota.replace("á", "a").replace("ñ", "n"))

    def test_rechaza_anios_imposibles(self):
        item = {"title": "Porsche 911 modelo 1899", "attributes": []}
        self.assertIsNone(extraer_anio(item)[0])


class TestPrecio(unittest.TestCase):
    def test_precio_exacto(self):
        precio, nota = extraer_precio(mezclado("MCO111"))
        self.assertEqual(precio, 739000000.0)
        self.assertIsNone(nota)

    def test_sin_precio_devuelve_nd_y_no_inventa(self):
        precio, nota = extraer_precio(mezclado("MCO222"))
        self.assertIsNone(precio)
        self.assertIn("no publica precio", nota)

    def test_precio_en_dolares_no_entra_como_pesos(self):
        # Un Porsche de USD 150.000 no puede quedar como $150.000 COP: eso
        # arrastraria la mediana hacia abajo.
        precio, nota = extraer_precio(mezclado("MCO666"))
        self.assertIsNone(precio)
        self.assertIn("USD", nota)

    def test_precio_cero_es_nd(self):
        self.assertIsNone(extraer_precio({"price": 0})[0])


class TestCilindraje(unittest.TestCase):
    def test_en_centimetros_cubicos(self):
        self.assertEqual(extraer_cilindraje(mezclado("MCO111"))[0], 2981)

    def test_en_litros_se_convierte_a_cc(self):
        self.assertEqual(extraer_cilindraje(mezclado("MCO333"))[0], 3000)

    def test_sin_dato(self):
        self.assertIsNone(extraer_cilindraje({"attributes": []})[0])


class TestUbicacion(unittest.TestCase):
    def test_ciudad_del_resultado_de_busqueda(self):
        self.assertEqual(extraer_ubicacion(mezclado("MCO111")),
                         ("Bogotá D.C.", "Bogotá D.C."))

    def test_ciudad_del_seller_address_cuando_no_hay_address(self):
        ciudad, depto = extraer_ubicacion(mezclado("MCO333"))
        self.assertEqual(ciudad, "Rionegro")
        self.assertEqual(depto, "Antioquia")


class TestEstadoYEnlace(unittest.TestCase):
    def test_aviso_pausado_se_descarta(self):
        self.assertFalse(esta_vivo(mezclado("MCO444")),
                         "un aviso pausado es un link que no entra")

    def test_aviso_activo_se_conserva(self):
        self.assertTrue(esta_vivo(mezclado("MCO111")))

    def test_permalink_define_el_portal(self):
        self.assertEqual(extraer_portal(mezclado("MCO111")), "TuCarro")
        self.assertEqual(extraer_portal(mezclado("MCO222")), "MercadoLibre CO")

    def test_el_enlace_es_el_permalink_canonico(self):
        r = normalizar(mezclado("MCO111"), "Porsche", "911", "Porsche 911")
        self.assertTrue(r["link"].startswith("https://"))
        self.assertIn("MCO-111", r["link"])


class TestOtros(unittest.TestCase):
    def test_kilometraje(self):
        self.assertEqual(extraer_kilometraje(mezclado("MCO111")), 18500)

    def test_foto_grande(self):
        self.assertTrue(extraer_foto(mezclado("MCO111")).startswith("https://"))

    def test_foto_desde_miniatura_cuando_no_hay_pictures(self):
        item = {"thumbnail": "http://http2.mlstatic.com/D_NQ_NP_9-I.jpg"}
        url = extraer_foto(item)
        self.assertTrue(url.startswith("https://"))
        self.assertIn("-O.jpg", url)

    def test_detecta_chocado(self):
        self.assertIn("Si", para_reparar(mezclado("MCO888")))

    def test_auto_sano_no_se_marca_como_chocado(self):
        self.assertEqual(para_reparar(mezclado("MCO111")), "No indicado")


class TestDeduplicacion(unittest.TestCase):
    def test_mismo_aviso_en_dos_busquedas_queda_una_vez(self):
        a = normalizar(mezclado("MCO111"), "Porsche", "911", "Porsche 911")
        b = normalizar(mezclado("MCO111"), "Porsche", "Carrera", "Porsche Carrera")
        unicos, espejos = deduplicar([a, b])
        self.assertEqual(len(unicos), 1)
        self.assertEqual(espejos, 1)

    def test_gana_el_registro_que_tiene_precio(self):
        con = normalizar(mezclado("MCO111"), "Porsche", "911", "q")
        sin = dict(con, precio=None)
        unicos, _ = deduplicar([sin, con])
        self.assertEqual(unicos[0]["precio"], 739000000.0)


class TestMarcaYModelo(unittest.TestCase):
    def test_marca_y_modelo_salen_del_aviso_no_de_la_busqueda(self):
        # Se busca "911" pero el aviso es un C63: debe guardarse como Mercedes.
        r = normalizar(mezclado("MCO777"), "Porsche", "911", "Porsche 911")
        self.assertEqual(r["marca"], "Mercedes-Benz")
        self.assertEqual(r["marca_buscada"], "Porsche")

    def test_cae_a_la_busqueda_cuando_el_aviso_no_declara_marca(self):
        r = normalizar(mezclado("MCO555"), "Porsche", "Boxster", "Porsche Boxster")
        self.assertEqual(r["marca"], "Porsche")
        self.assertIn("tomada de la busqueda", r["nota"])

    def test_filtro_descarta_avisos_de_otra_marca(self):
        r = normalizar(mezclado("MCO777"), "Porsche", "911", "Porsche 911")
        self.assertFalse(marca_coincide(r))

    def test_filtro_acepta_la_marca_correcta(self):
        r = normalizar(mezclado("MCO111"), "Porsche", "911", "Porsche 911")
        self.assertTrue(marca_coincide(r))

    def test_filtro_tolera_mercedes_benz_vs_mercedes(self):
        r = normalizar(mezclado("MCO777"), "Mercedes", "C63", "Mercedes C63")
        self.assertTrue(marca_coincide(r))

    def test_filtro_conserva_avisos_sin_marca_declarada(self):
        r = normalizar(mezclado("MCO555"), "Porsche", "Boxster", "q")
        self.assertTrue(marca_coincide(r),
                        "sin marca en el aviso no hay con que contradecir")


class TestFilaCompleta(unittest.TestCase):
    def test_todas_las_llaves_esperadas(self):
        r = normalizar(mezclado("MCO111"), "Porsche", "911", "Porsche 911")
        for llave in ("marca", "modelo", "portal", "precio", "anio", "cc",
                      "km", "ciudad", "link", "foto", "nota", "registro"
                      if "registro" in r else "estado"):
            self.assertIn(llave, r)

    def test_aviso_pobre_no_rompe_nada(self):
        r = normalizar({"id": "MCO000", "title": "Carro"}, "X", "Y", "q")
        self.assertIsNone(r["precio"])
        self.assertIsNone(r["anio"])
        self.assertIsNone(r["ciudad"])
        self.assertTrue(r["nota"], "un aviso sin datos debe explicar por qué")


if __name__ == "__main__":
    unittest.main(verbosity=2)
