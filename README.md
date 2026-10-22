# Autos usados de alta gama en Colombia

Recolección de avisos de vehículos deportivos y de alta gama usados en Colombia (12 marcas, ~310
avisos en agosto de 2026), consolidación en Excel con análisis de precios por marca, modelo y
cilindraje, y tablero Shiny para explorar la oferta.

```
scraping/recolectar.py · extraer.py · api_ml.py · verificar_enlaces.py   Recolección y verificación
scraping/pruebas/                                                          Pruebas con fixtures
scripts/build_consolidado.py · build_xlsx.py                               Consolidación y Excel
datos_crudos/*.json                                                        Avisos tal como se recolectaron
app.R                                                                      Tablero Shiny
PROMPT_web_scraping.md · LEEME.txt · LEEME_TABLERO.md · scraping/LEEME_SCRAPING.md
```

Credenciales de la API en `scraping/credenciales.json` (no se versiona). Los Excel generados tampoco.

Autor: Gustavo A Romero
