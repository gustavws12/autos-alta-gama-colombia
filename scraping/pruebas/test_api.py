#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pruebas del cliente de la API. No tocan MercadoLibre: levantan un servidor
HTTP local que imita sus respuestas.

    python -m unittest pruebas.test_api -v
"""

import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import api_ml
from api_ml import ApiML, ErrorCredenciales, cargar_credenciales


class Manejador(BaseHTTPRequestHandler):
    ultimas_cabeceras = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        Manejador.ultimas_cabeceras = dict(self.headers)
        if self.path.startswith("/publico"):
            self._json(200, {"ok": True})
        elif self.path.startswith("/privado"):
            self._json(401, {"message": "invalid token"})
        else:
            self._json(404, {"message": "not found"})

    def _json(self, codigo, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)


class TestModoAnonimo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Manejador)
        cls.base_original = api_ml.BASE
        api_ml.BASE = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        api_ml.BASE = cls.base_original
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_sin_credenciales_es_anonimo(self):
        api = ApiML(None, None, pausa=0)
        self.assertTrue(api.anonimo)
        self.assertIsNone(api.token(), "en modo anónimo no se pide token")

    def test_con_credenciales_no_es_anonimo(self):
        self.assertFalse(ApiML("abc", "xyz", pausa=0).anonimo)

    def test_anonimo_no_manda_cabecera_de_autorizacion(self):
        api = ApiML(None, None, pausa=0)
        self.assertEqual(api.get("/publico"), {"ok": True})
        self.assertNotIn("Authorization", Manejador.ultimas_cabeceras)

    def test_anonimo_ante_401_explica_que_hacer(self):
        api = ApiML(None, None, pausa=0, reintentos=1)
        with self.assertRaises(ErrorCredenciales) as ctx:
            api.get("/privado")
        mensaje = str(ctx.exception)
        self.assertIn("devcenter", mensaje,
                      "el mensaje debe llevar al usuario a crear la aplicación")
        self.assertIn("credenciales.json", mensaje)

    def test_cuenta_las_llamadas(self):
        api = ApiML(None, None, pausa=0)
        api.get("/publico")
        api.get("/publico")
        self.assertEqual(api.llamadas, 2)


class TestCargarCredenciales(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "credenciales.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_crea_la_plantilla_si_no_existe(self):
        cid, sec = cargar_credenciales(self.ruta)
        self.assertTrue(self.ruta.exists(), "debe dejar el archivo listo")
        self.assertIsNone(cid)
        self.assertIsNone(sec)

    def test_plantilla_sin_llenar_no_es_credencial(self):
        cargar_credenciales(self.ruta)          # crea la plantilla
        self.assertEqual(cargar_credenciales(self.ruta), (None, None))

    def test_lee_credenciales_reales(self):
        self.ruta.write_text(json.dumps(
            {"client_id": "123456", "client_secret": "secreto"}),
            encoding="utf-8")
        self.assertEqual(cargar_credenciales(self.ruta), ("123456", "secreto"))

    def test_json_roto_avisa_con_claridad(self):
        self.ruta.write_text('{"client_id": "123",,}', encoding="utf-8")
        with self.assertRaises(ErrorCredenciales) as ctx:
            cargar_credenciales(self.ruta)
        self.assertIn("no es un JSON valido", str(ctx.exception))

    def test_las_variables_de_entorno_mandan(self):
        import os
        self.ruta.write_text(json.dumps(
            {"client_id": "delarchivo", "client_secret": "delarchivo"}),
            encoding="utf-8")
        os.environ["ML_CLIENT_ID"] = "delentorno"
        os.environ["ML_CLIENT_SECRET"] = "delentorno"
        try:
            self.assertEqual(cargar_credenciales(self.ruta),
                             ("delentorno", "delentorno"))
        finally:
            del os.environ["ML_CLIENT_ID"]
            del os.environ["ML_CLIENT_SECRET"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
