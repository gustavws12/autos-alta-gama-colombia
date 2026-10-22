# Rutina de recolección — autos deportivos y de alta gama, Colombia

Reemplaza el scraping anterior. Usa la **API oficial de MercadoLibre**, que es
la misma plataforma sobre la que corre TuCarro, así que cada dato llega en su
propio campo en vez de tener que adivinarlo del texto del aviso.

---

## Qué arregla y por qué

Los tres problemas que reportaste tenían **una sola causa**: los datos se
sacaban del texto del resultado de búsqueda, no de la ficha del aviso.

| Problema | Causa | Cómo queda |
|---|---|---|
| El link no entra o no existe | Se guardaban avisos ya cerrados o pausados, y enlaces reconstruidos a mano | Se usa el `permalink` canónico del aviso y **solo entran los avisos activos**. Los cerrados se cuentan aparte en el reporte. |
| El año sale mal | Se buscaba un número en el título: "Audi A5 **2.0** TFSI" se leía como año | Se lee el campo `VEHICLE_YEAR`. Si el aviso no lo trae, se intenta del título y **queda marcado como deducido**; si el título tiene dos años posibles se deja en ND en vez de elegir uno. |
| El precio sale mal | El precio no siempre aparecía en el texto indexado | Se lee el campo `price`. Sin precio publicado queda ND, nunca inventado. |

De paso se resuelven las dos limitaciones que arrastraba el análisis:

- **Ciudad**: ahora viene de la API (`address.city_name` o `seller_address`).
  Antes estaba en ND en 308 de 310 avisos.
- **Fotos**: se guarda la URL de la imagen de cada aviso y se escribe
  `fotos.csv`, que es exactamente lo que el marketplace del tablero necesita.

Y se agregaron tres controles de calidad que antes no existían:

- **La marca y el modelo salen del aviso, no de la búsqueda.** Buscar
  "Porsche 911" también devuelve Cayman y carros de otras marcas; antes todo
  eso quedaba guardado como 911.
- **Se descartan los avisos de otra marca.** Desactivable con
  `--sin-filtro-marca`.
- **Los precios en dólares no entran a las estadísticas.** Un Porsche de
  USD 150.000 copiado tal cual habría entrado como $150.000 COP y habría
  arrastrado la mediana. El valor original queda en su propia columna.

---

## Puesta en marcha (una sola vez)

### 1. Python

Si no lo tienes, instálalo desde <https://www.python.org/downloads/> y **marca
la casilla "Add Python to PATH"** durante la instalación.

### 2. Credenciales de MercadoLibre (gratis, 5 minutos)

**Prueba primero sin credenciales.** La rutina intenta en modo anónimo y, si
MercadoLibre las exige, se detiene con un mensaje claro sin dañar nada. Solo
sigue estos pasos si te lo pide.

1. Inicia sesión en MercadoLibre con tu cuenta normal.
2. Entra **directo** a <https://developers.mercadolibre.com.co/devcenter>.
   La página de inicio de Developers no siempre muestra el menú de
   aplicaciones; esa URL va derecho al administrador.
3. Botón **Crear aplicación**.
4. Nombre y descripción: cualquiera (por ejemplo "Análisis autos alta gama").
5. En **URI de redirect** pon `https://localhost`. Marca el scope **read**.
6. Copia el **App ID** y la **Secret Key**.
7. Abre `credenciales.json` en esta carpeta y pégalos:

```json
{
  "client_id": "1234567890123456",
  "client_secret": "aBcDeFgHiJkLmNoPqRsTuVwXyZ123456"
}
```

Si el archivo no existe, ejecuta la rutina una vez y ella lo crea con la
plantilla lista para llenar.

Si `/devcenter` tampoco te abre, prueba con
<https://developers.mercadolibre.com.co/devcenter/create-app>, o busca en el
menú del avatar arriba a la derecha. MercadoLibre le ha cambiado el nombre a
esa sección varias veces ("Mis aplicaciones", "DevCenter", "Tus aplicaciones").

> **La Secret Key es personal.** No subas `credenciales.json` a ningún lado ni
> lo compartas. El `.gitignore` de esta carpeta ya lo excluye.
>
> Si prefieres no tener la clave en un archivo, define las variables de
> entorno `ML_CLIENT_ID` y `ML_CLIENT_SECRET` y la rutina las usa primero.

---

## Cómo se usa

**Lo más fácil:** doble clic en **`ejecutar.bat`**.

Desde la consola, parada en esta carpeta:

```bat
python recolectar.py                    :: corrida normal
python recolectar.py --solo Porsche     :: una sola marca
python recolectar.py --max 100          :: tope de avisos por búsqueda
python recolectar.py --condicion todas  :: incluir vehículos nuevos
python recolectar.py --simular          :: prueba sin internet ni credenciales
python recolectar.py --sin-red          :: rearmar el Excel con lo ya bajado
python recolectar.py --sin-filtro-marca :: no descartar avisos de otra marca
```

`--sin-red` es útil cuando quieres cambiar algo del procesamiento sin volver a
descargar: reusa el JSON guardado en `datos_crudos/`.

---

## Qué buscar: `busquedas.csv`

Ábrelo con Excel. Una fila por búsqueda:

| columna | qué es |
|---|---|
| `activo` | `si` o `no`. Sirve para apagar una búsqueda sin borrarla. |
| `marca` | Etiqueta de respaldo, por si el aviso no declara marca. |
| `modelo` | Igual, de respaldo. |
| `consulta` | **Lo que se escribe en el buscador de MercadoLibre.** Es lo único que de verdad determina qué se trae. |
| `precio_min` | Piso de precio en pesos. Viene en 30.000.000 para no traer repuestos ni miniaturas. |
| `precio_max` | Techo de precio. Vacío = sin techo. |
| `notas` | Para ti. La rutina lo ignora. |

Vienen 49 búsquedas activas (las mismas marcas y modelos de tu análisis, más
BMW Serie M, Porsche Macan y Toyota GR86) y 5 marcas exóticas desactivadas
—Ferrari, Lamborghini, Maserati, McLaren, Bentley— que puedes encender
cambiando su `activo` a `si`.

---

## Qué produce

| Archivo | Dónde queda |
|---|---|
| `deportivos_alta_gama_colombia.xlsx` | En la carpeta del proyecto, con hoja **Avisos** y hoja **Calidad**. Mismas columnas que antes, más 11 columnas nuevas de auditoría. |
| `fotos.csv` | En la carpeta del proyecto. Lo lee el marketplace del tablero. |
| `datos_crudos/*.json` | El JSON tal como lo devolvió la API, por si quieres reprocesarlo. |
| `reporte_calidad.txt` | Resumen de la corrida. |

**El Excel anterior se respalda automáticamente** como
`deportivos_alta_gama_colombia_respaldo_AAAAMMDD_HHMM.xlsx` antes de
sobrescribirlo. Con `--sin-respaldo` se omite.

El esquema de columnas es el que espera `app.R`, así que después de recolectar
solo tienes que abrir el tablero y pulsar *Run App*.

---

## Cómo saber si la corrida salió bien

Al terminar imprime, y guarda en la hoja **Calidad**, cuántos avisos tienen
precio, año, ciudad, kilometraje, cilindraje y foto, cuántos se descartaron por
estar cerrados y cuántos por ser de otra marca.

Compara contra la corrida anterior. Si "Con año tomado del campo del aviso"
baja mucho de un mes a otro, algo cambió en la API y vale la pena revisar.

---

## Verificar enlaces caídos (`verificar_enlaces.py`)

Un aviso de MercadoLibre que ya se vendió o venció **no devuelve error 404**:
la página redirige al listado de carros parecidos y agrega al final de la URL
la marca `#redirectedFromVip=<la url original>`. Por eso "el link no entra":
el navegador sí abre algo, pero no es el aviso.

```bat
python verificar_enlaces.py                 :: verifica y marca el Excel
python verificar_enlaces.py --solo-reporte  :: no toca el Excel
python verificar_enlaces.py --limite 20     :: probar con los primeros 20
python verificar_enlaces.py --modo http     :: forzar el modo sin credenciales
```

Tiene dos modos y elige solo el mejor disponible:

- **Modo API** (si `credenciales.json` está lleno). Pregunta el campo `status`
  de cada aviso. Es la respuesta autoritativa y va rápido: 20 avisos por
  llamada.
- **Modo HTTP** (sin credenciales). Abre cada enlace y mira dónde termina.
  Funciona, pero es aproximado: si MercadoLibre decide mostrar el aviso cerrado
  en la misma URL con un cartel de "publicación finalizada" en vez de redirigir,
  este modo lo dará por vigente.

En ambos casos, **"Sin verificar" nunca se confunde con "Caído"**: si no hay
respuesta del servidor, se dice que no se pudo comprobar, no que el aviso murió.

Deja dos columnas nuevas en la hoja *Avisos* —`Estado del enlace` y
`Enlace verificado el`— más un `reporte_enlaces.csv` con el motivo aviso por
aviso. El Excel se respalda antes de tocarlo.

Cuando esas columnas existen, el tablero muestra una casilla **"Solo avisos con
enlace vigente"** y marca en rojo las tarjetas de los avisos retirados.

---

## Cómo está organizado

```
scraping/
├── recolectar.py       Rutina principal: orquesta todo
├── verificar_enlaces.py Revisa si los enlaces guardados siguen vivos
├── api_ml.py           Único archivo que toca la red (token, reintentos, paginación)
├── extraer.py          Funciones puras que leen cada campo del aviso
├── busquedas.csv       Qué buscar (editable en Excel)
├── credenciales.json   Tus llaves de la API (no compartir)
├── ejecutar.bat        Doble clic para correr
├── probar.bat          Doble clic para correr las pruebas
├── requirements.txt    Dependencias (solo openpyxl)
├── datos_crudos/       JSON descargado
└── pruebas/
    ├── test_extraer.py           33 pruebas de extracción
    ├── test_enlaces.py           19 pruebas del verificador
    ├── test_api.py               10 pruebas del cliente de la API
    └── fixtures/avisos_ejemplo.json
```

La red está aislada en `api_ml.py` a propósito: `extraer.py` son funciones
puras, y por eso se pueden probar completas sin conexión.

---

## Pruebas

Doble clic en **`probar.bat`**, o:

```bat
python -m unittest discover -s pruebas -v
python recolectar.py --simular
```

Son 62 pruebas y cada una corresponde a un problema concreto: que el cilindraje
"2.0" no se lea como año, que un título con dos años no elija uno al azar, que
un aviso pausado se descarte, que el precio en dólares no entre como pesos, que
la marca salga del aviso y no de la búsqueda, que un aviso sin ningún dato no
rompa el proceso.

Las del verificador levantan un servidor HTTP local que imita la redirección
real de MercadoLibre, así que la detección de avisos caídos está probada de
punta a punta. Una de ellas cazó un error de verdad: la URL de destino lleva el
ID del aviso original incrustado después del `#`, así que comparar códigos sin
quitar el fragmento daba "vigente" a un aviso muerto.

---

## Advertencias honestas

**No pude probar la rutina contra la API real.** El entorno donde la escribí no
tiene acceso a `api.mercadolibre.com`. Lo que sí está probado, y a fondo, es
todo el procesamiento: extracción, normalización, deduplicación, filtros,
generación del Excel y del `fotos.csv`, verificado además cargando el resultado
desde el tablero de R. La primera corrida real con tus credenciales es la
prueba que falta; si algo falla ahí, lo más probable es un nombre de atributo
distinto al esperado, y el reporte de calidad lo va a mostrar de inmediato como
una caída en el porcentaje del campo afectado.

**La búsqueda pública tiene tope de 1.000 avisos por consulta.** Cuando una
búsqueda supera ese número, la rutina la parte automáticamente en rangos de
precio para no perder avisos. Si aun así ves un total sospechosamente redondo,
acota con `precio_min` y `precio_max` en `busquedas.csv`.

**Los precios siguen siendo los publicados por el vendedor**, no precios de
transacción. Eso no lo arregla ninguna API.
