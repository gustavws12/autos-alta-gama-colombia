# Tablero Shiny — precios de deportivos y alta gama usados en Colombia

`app.R` lee directamente `deportivos_alta_gama_colombia.xlsx` (hoja **Avisos**)
desde su misma carpeta. Si actualizas el Excel, el tablero se actualiza al
reiniciarlo: no hay que tocar código.

## Cómo ejecutarlo

**Con RStudio:** abre `app.R` y pulsa *Run App*.

**Sin RStudio, desde la consola de R:**

```r
setwd("C:/Users/Pc/para trabajo/ideas de negocio/Autos/autos_alta_gama_colombia")
shiny::runApp("app.R")
```

La primera vez el app instala solo lo que le falte de: `shiny`, `readxl`,
`dplyr`, `plotly`, `scales`, `DT`.

## Qué muestra

**Fila de indicadores** (siempre visible, responde a los filtros): avisos con
precio, mediana, promedio, rango, rango intercuartílico y qué porcentaje de los
avisos tiene ciudad conocida.

| Pestaña | Contenido |
|---|---|
| **Marketplace** | Los vehículos en tarjetas, con orden configurable y páginas de 12. Cada tarjeta lleva modelo, versión, precio, año, cilindraje, portal, ciudad y botón *Ver aviso*. |
| **Por marca** | Caja y puntos por marca, ordenada por mediana, más un ranking de cuánta oferta hay por marca. |
| **Por modelo** | Lo mismo a nivel `Marca · Modelo` (47 combinaciones). Filtra por marca para leerlo cómodo. |
| **Por lugar** | Distribución por portal, avisos por ciudad identificada y una tabla con mínimo, cuartiles, mediana y máximo por portal. |
| **Distribución general** | Histograma de precios con la mediana marcada y precio contra año modelo con tendencia suavizada. |
| **Tabla de avisos** | Tabla filtrable con link a cada aviso y descarga del CSV filtrado. |

Los gráficos son de **plotly**: pasa el cursor por cualquier punto para ver el
aviso completo (marca, versión, precio, año y portal) y usa la barra superior
derecha para descargar el gráfico como PNG.

**Filtros.** Marca, modelo, portal y ciudad son listas desplegables con
buscador: escribe dentro de cualquiera para filtrar las opciones. Puedes elegir
varias a la vez, y **si dejas una lista vacía significa "todas"**. La lista de
modelos se recorta sola a las marcas que hayas elegido. Además hay rango de
precio, rango de año, incluir o no avisos sin año, excluir los dos avisos
espejados entre portales, escala logarítmica de precio y un mínimo de avisos por
grupo para decidir cuándo tiene sentido dibujar una caja (con 1 o 2 avisos solo
se muestran los puntos).

## Fotos del marketplace

**La rutina de `scraping/` ya trae las fotos.** Al recolectar con la API oficial
de MercadoLibre se escribe `fotos.csv` automáticamente y las tarjetas se llenan
solas. Ver `scraping/LEEME_SCRAPING.md`.

Si prefieres poner fotos a mano, o completar las que falten, hay dos vías:

**1. Archivos locales.** Guarda las imágenes en `www/fotos/` con el ID del aviso
como nombre. El ID es el código MCO del link:

```
https://articulo.tucarro.com.co/MCO-644551264-audi-a5-...
                                ^^^^^^^^^^^^^
->  www/fotos/MCO644551264.jpg
```

Sirven `.jpg .jpeg .png .webp .gif`, y también el número de la columna `#` del
Excel (`1.jpg`, `2.jpg`, …).

**2. Enlaces en `fotos.csv`.** El archivo ya está creado con las columnas `id` y
`url`. Cada fila apunta un aviso a una imagen en la web:

```csv
id,url
MCO644551264,https://http2.mlstatic.com/D_NQ_NP_2X_123456-MCO.jpg
```

El archivo local manda sobre el CSV, así que una foto que pongas a mano
sobrevive a la siguiente recolección. La barra superior del marketplace te dice
cuántos vehículos del filtro actual ya tienen foto.

## Enlaces caídos

Un aviso de MercadoLibre que ya se vendió o venció **no da error 404**: redirige
al listado de carros parecidos. Por eso algunos links "no entran" aunque el
navegador abra algo.

Corre `scraping/verificar_enlaces.py` y el tablero se entera solo: aparece la
casilla **"Solo avisos con enlace vigente"** en el panel izquierdo (marcada por
defecto), y los avisos retirados quedan con la foto en gris, una etiqueta roja
*aviso retirado* y un botón que avisa antes de llevarte al listado de similares.

Si nunca has corrido el verificador, la casilla no aparece y el tablero se
comporta como siempre.

## Decisiones que conviene que conozcas

**El "lugar": portal y ciudad.** En los datos viejos la columna `Ciudad` venía
en `ND` en 308 de 310 avisos, y por eso el eje geográfico del tablero es el
portal. Con la rutina nueva de `scraping/` la ciudad **sí llega** desde la API,
y la pestaña *Por lugar* la muestra sin que tengas que cambiar nada.

El app además **deduce la ciudad** desde el título, el link y la nota de cada
aviso contra una lista de 46 ciudades colombianas, como respaldo para los avisos
que no la publiquen.

Deliberadamente **excluí de la lista de ciudades** los nombres que chocan con
vocabulario automotor: *Turbo*, *Bello*, *Buga* y *Soledad*. Sin esa exclusión,
"Porsche 911 Turbo" se contaba como un aviso en Turbo, Antioquia — 27 falsos
positivos en la primera pasada.

**Solo entran a las estadísticas de precio los 227 avisos con precio publicado.**
Los 83 sin precio siguen apareciendo en el marketplace (marcados como "Precio no
publicado") y cuentan para la oferta por ciudad, que es un conteo, no un
promedio. Los precios son los publicados por el vendedor, no de transacción.

**El gráfico de precio contra año ajusta la tendencia solo desde 2011.** Con el
Mercedes SL de 1982 dentro del ajuste, la banda de confianza se extendía treinta
años sobre una zona sin un solo aviso.

**Los precios se grafican en millones.** Si se pasan en pesos, plotly rotula el
eje con su notación SI y salen etiquetas como `0,2B M` en vez de `200 M`.

## Verificación

El app se ejecutó en R 4.3.3 con las seis dependencias instaladas. Se renderizan
las dieciocho salidas sin errores ni advertencias, con los filtros por defecto,
con una sola marca, con escala logarítmica, en la página 2 del marketplace y con
un filtro que no devuelve ningún aviso. Se revisaron capturas del navegador en
las seis pestañas. La mediana general que calcula ($195.000.000) coincide con la
de tu `LEEME.txt`.
