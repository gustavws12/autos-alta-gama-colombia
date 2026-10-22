#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas del verificador de enlaces.

Levanta un servidor HTTP local que imita el comportamiento real de
MercadoLibre con un aviso caido (redirige al listado y agrega
#redirectedFromVip=...), y comprueba que la rutina lo detecta.

    python -m unittest pruebas.test_enlaces -v
"""

import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

from verificar_enlaces import (CAIDO, SIN_VERIFICAR, VIGENTE, clasificar,
                               clasificar_estado_api, codigo_mco, revisar,
                               revisar_con_api, sin_fragmento)

# El caso real que reporto el usuario.
URL_REAL = ("https://carro.mercadolibre.com.co/"
            "MCO-1542509431-ford-mustang-shelby-gt500-2021-_JM")
DESTINO_REAL = ("https://carros.mercadolibre.com.co/ford/modelo-mustang-shelby/"
                "2021/#redirectedFromVip=https%3A%2F%2Fcarro.mercadolibre.com.co"
                "%2FMCO-1542509431-ford-mustang-shelby-gt500-2021-_JM")


# ---------------------------------------------------------- servidor de prueba
class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):            # silencio
        pass

    def do_GET(self):
        if "MCO-1542509431" in self.path:
            self._responder(200, b"<html>aviso vigente</html>")
        elif "MCO-2873774080" in self.path:
            destino = ("/carros/ford/modelo-mustang/2021/"
                       "#redirectedFromVip=http://x/MCO-2873774080-muerto-_JM")
            self.send_response(302)
            self.send_header("Location", destino)
            self.end_headers()
        elif "MCO-3093635422" in self.path:
            self._responder(404, b"no existe")
        elif "MCO-1261722433" in self.path:       # redirige sin dejar huella
            self.send_response(301)
            self.send_header("Location", "/carros/ford/")
            self.end_headers()
        else:
            self._responder(200, b"listado")

    def do_HEAD(self):
        if "MCO-1583377795" in self.path:         # servidor que no acepta HEAD
            self._responder(405, b"")
            return
        self.do_GET()

    def _responder(self, codigo, cuerpo):
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)


class TestConServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Manejador)
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        cls.hilo = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_aviso_vigente(self):
        estado, _ = revisar(f"{self.base}/MCO-1542509431-vivo-_JM")
        self.assertEqual(estado, VIGENTE)

    def test_aviso_redirigido_al_listado_es_caido(self):
        # Este es exactamente el caso del Mustang Shelby.
        estado, motivo = revisar(f"{self.base}/MCO-2873774080-muerto-_JM")
        self.assertEqual(estado, CAIDO)
        self.assertIn("ya no existe", motivo)

    def test_aviso_404_es_caido(self):
        estado, motivo = revisar(f"{self.base}/MCO-3093635422-borrado-_JM")
        self.assertEqual(estado, CAIDO)
        self.assertIn("404", motivo)

    def test_redireccion_sin_huella_tambien_es_caido(self):
        estado, _ = revisar(f"{self.base}/MCO-1261722433-movido-_JM")
        self.assertEqual(estado, CAIDO)

    def test_cae_a_get_cuando_el_servidor_rechaza_head(self):
        estado, _ = revisar(f"{self.base}/MCO-1583377795-vivo-_JM")
        self.assertIn(estado, (VIGENTE, CAIDO))   # respondió, no quedó sin verificar

    def test_servidor_inalcanzable_queda_sin_verificar(self):
        estado, motivo = revisar("http://127.0.0.1:9/MCO-9060000000-x-_JM", tiempo_limite=2)
        self.assertEqual(estado, SIN_VERIFICAR,
                         "sin respuesta no se puede afirmar que esté caído")
        self.assertIn("Sin respuesta", motivo)


# -------------------------------------------------------------- funcion pura
class TestClasificar(unittest.TestCase):
    def test_el_caso_real_del_mustang(self):
        estado, motivo = clasificar(URL_REAL, DESTINO_REAL, 200, None)
        self.assertEqual(estado, CAIDO)
        self.assertIn("ya no existe", motivo)

    def test_misma_url_final_es_vigente(self):
        estado, _ = clasificar(URL_REAL, URL_REAL, 200, None)
        self.assertEqual(estado, VIGENTE)

    def test_no_se_deja_enganar_por_el_id_dentro_del_fragmento(self):
        # La URL de destino lleva la original incrustada despues del '#'.
        # Sin quitar el fragmento, el codigo aparece y todo parece vigente.
        self.assertIn("MCO-1542509431", DESTINO_REAL)
        self.assertNotIn("MCO", sin_fragmento(DESTINO_REAL))

    def test_tolera_el_codigo_con_y_sin_guion(self):
        self.assertEqual(codigo_mco("…/MCO-1542509431-ford…"), "MCO1542509431")
        self.assertEqual(codigo_mco("MCO1542509431"), "MCO1542509431")

    def test_no_confunde_dos_avisos_distintos(self):
        otro = "https://carro.mercadolibre.com.co/MCO-9999999990-otro-_JM"
        estado, _ = clasificar(URL_REAL, otro, 200, None)
        self.assertEqual(estado, CAIDO)

    def test_error_de_red_no_es_caido(self):
        estado, _ = clasificar(URL_REAL, None, None, "Sin respuesta (timeout)")
        self.assertEqual(estado, SIN_VERIFICAR)

    def test_500_no_es_caido(self):
        estado, _ = clasificar(URL_REAL, URL_REAL, 500, None)
        self.assertEqual(estado, SIN_VERIFICAR,
                         "un error del servidor no prueba que el aviso murió")

    def test_enlace_sin_codigo_queda_sin_verificar(self):
        estado, _ = clasificar("https://ejemplo.com/algo", "https://ejemplo.com/algo",
                               200, None)
        self.assertEqual(estado, SIN_VERIFICAR)


# ------------------------------------------------------------------ modo API
class ApiFalsa:
    """Imita ApiML.get('/items') para probar el modo API sin red."""

    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = 0

    def get(self, ruta, **params):
        self.llamadas += 1
        ids = params["ids"].split(",")
        salida = []
        for i in ids:
            if i in self.respuestas:
                salida.append({"code": 200, "body": self.respuestas[i]})
        return salida


class TestModoApi(unittest.TestCase):
    def test_traduce_los_estados(self):
        self.assertEqual(clasificar_estado_api("active")[0], VIGENTE)
        self.assertEqual(clasificar_estado_api("closed")[0], CAIDO)
        self.assertEqual(clasificar_estado_api("paused")[0], CAIDO)
        self.assertEqual(clasificar_estado_api("under_review")[0], CAIDO)
        self.assertEqual(clasificar_estado_api(None)[0], SIN_VERIFICAR)

    def test_activo_pero_borrado_es_caido(self):
        estado, _ = clasificar_estado_api("active", ["deleted"])
        self.assertEqual(estado, CAIDO)

    def test_consulta_por_lotes(self):
        api = ApiFalsa({
            "MCO1542509431": {"id": "MCO1542509431", "status": "active"},
            "MCO2873774080": {"id": "MCO2873774080", "status": "closed"},
        })
        urls = ["https://x/MCO-1542509431-a-_JM", "https://x/MCO-2873774080-b-_JM"]
        res = revisar_con_api(api, urls)
        self.assertEqual(res[urls[0]][0], VIGENTE)
        self.assertEqual(res[urls[1]][0], CAIDO)
        self.assertEqual(api.llamadas, 1, "los 20 primeros van en una sola llamada")

    def test_aviso_que_la_api_no_devuelve_es_caido(self):
        api = ApiFalsa({})
        urls = ["https://x/MCO-1542509431-ford-mustang-_JM"]
        res = revisar_con_api(api, urls)
        self.assertEqual(res[urls[0]][0], CAIDO)

    def test_falla_de_la_api_no_marca_caido(self):
        class ApiRota:
            def get(self, *a, **k):
                raise RuntimeError("sin red")
        res = revisar_con_api(ApiRota(), ["https://x/MCO-1542509431-a-_JM"])
        self.assertEqual(list(res.values())[0][0], SIN_VERIFICAR)


if __name__ == "__main__":
    unittest.main(verbosity=2)
