# Prompt para continuar el web scraping en un chat nuevo

Copia todo lo que está entre las líneas y pégalo como primer mensaje del chat nuevo.
Adjunta también el archivo `deportivos_alta_gama_colombia.xlsx` si quieres que parta de lo ya recolectado.

---

Quiero que hagas web scraping de avisos de **vehículos usados de alta gama y deportivos en Colombia** y me entregues un Excel con la caracterización de precios.

**Marcas y modelos objetivo:** BMW Z4, Chevrolet Corvette y Camaro, Ford Mustang, Mercedes-Benz deportivos (SLK/SLC, C63 AMG, A45/CLA45 AMG, AMG GT, coupés y cabrios de Clase C y E), Audi (TT, S3, RS3, RS5, A5, A7, R8), MINI (Cooper, Cooper S, JCW, Countryman, Clubman), Porsche (911, Cayman, Boxster, 718, Panamera), Dodge Challenger y Charger, Jaguar F-Type, Nissan 370Z y GT-R, Subaru WRX, Toyota Supra.

**Columnas que necesito por cada aviso:**
marca · modelo · fuente (portal) · título del aviso · precio de venta (COP) · año modelo · versión/generación · cilindraje (cc) · kilometraje (km) · ciudad · ¿está para reparar? · link de la fuente · nota con los supuestos usados.

## Cómo hacerlo (esto ya está probado, ahórrate los intentos fallidos)

1. **NO uses WebFetch en los portales colombianos.** MercadoLibre Colombia, TuCarro, Mitula, Trovit, usados.co y la API de MercadoLibre devuelven error 403 o están bloqueados por robots.txt. CarroYa y Autocosmos cargan todo por JavaScript y devuelven una página vacía. Intentarlo solo gasta tiempo.

2. **Usa WebSearch con consultas `site:`.** Los títulos de los resultados indexados normalmente ya traen el precio en COP, y muchas veces el año y la versión. Los dos dominios que sí devuelven avisos individuales son:
   - `site:articulo.tucarro.com.co <marca> <modelo>`
   - `site:carro.mercadolibre.com.co <marca> <modelo>`
   Haz 8–10 búsquedas distintas por marca, variando versión, año y carrocería, para maximizar cobertura.

3. **Paraleliza.** Lanza un subagente por marca o grupo de marcas, todos en el mismo mensaje, y pídeles que devuelvan un array JSON con las claves exactas de las columnas. Es mucho más rápido que buscar en serie.

4. **Extrae también del slug de la URL.** Cuando el título no trae el año, muchas veces la URL sí lo tiene (ej. `...-camaro-2023-_JM`). Anótalo en la nota indicando que vino del slug, no del título.

5. **Deriva el cilindraje de la versión** cuando no venga explícito, y **documenta el supuesto en la columna de notas**. Referencias: Mustang GT 5.0 Coyote = 4951 cc · Shelby GT350 5.2 Voodoo = 5163 cc · Camaro/Corvette 6.2 = 6162 cc · Corvette C8 Z06 5.5 = 5463 cc · Hellcat 6.2 = 6166 cc · Scat Pack 6.4 = 6417 cc · Mercedes A45/CLA45 = 1991 cc · C63 AMG W204 = 6208 cc y W205 = 3982 cc · SLK200 = 1796 cc · Audi 2.0 TFSI = 1984 cc, 1.8 TFSI = 1798 cc, RS3 2.5 = 2480 cc, RS5 2.9 = 2894 cc, R8 V10 = 5204 cc · MINI 1.5 = 1499 cc, 1.6 = 1598 cc, 2.0 = 1998 cc · BMW Z4 sDrive20i = 1998 cc y M40i = 2998 cc · Porsche 718 2.0 = 1988 cc y 2.5 = 2497 cc, 911 992 = 2981 cc · Nissan 370Z = 3696 cc y GT-R = 3799 cc.
   Si la versión admite más de un motor (ej. Camaro RS, Jaguar F-Type sin motorización, Porsche Carrera S sin generación), deja el campo en ND en vez de adivinar.

6. **Deduplica por el ID de publicación** (`MCO-<dígitos>` dentro de la URL). El mismo aviso aparece espejado entre TuCarro y MercadoLibre; márcalo y **exclúyelo de las estadísticas** para no contar dos veces el mismo carro.

7. **Busca explícitamente vehículos siniestrados**: `<marca> chocado OR "para reparar" venta Colombia`. En la corrida anterior no apareció ninguno de estas marcas, pero vale confirmar.

8. **No inventes datos.** Kilometraje y ciudad casi nunca están disponibles porque los portales bloquean la lectura de la ficha completa: márcalos como ND y deja constancia de la limitación en el archivo.

## Entregable

Un `.xlsx` con dos hojas:

- **"Avisos"**: una fila por aviso con todas las columnas, links como hipervínculo, filtros activados, primera fila congelada, duplicados resaltados y una nota metodológica al pie.
- **"Análisis por marca"**: conteos (avisos totales, únicos, con precio, siniestrados), mediana general, y tablas de precio mínimo / promedio / máximo por marca, por modelo y por rango de cilindraje. **Todo calculado con fórmulas de Excel** que referencien la hoja "Avisos", no con valores quemados. Cierra con una sección de hallazgos en prosa.

Nota técnica para las fórmulas: `MINIFS` y `MAXIFS` necesitan el prefijo `_xlfn.` al escribirlas con openpyxl. Evita `MEDIAN(IF(...))` porque es fórmula matricial y no se calcula bien; en su lugar crea una columna auxiliar "Precio estadístico" con `=IF(AND(<registro>="Único",ISNUMBER(<precio>)),<precio>,"")` y saca la mediana sobre esa columna.

---

## Si además quieres ampliar el trabajo

Ideas para el chat nuevo, sobre la misma base:

- Agregar marcas de lujo no deportivas: Range Rover, Lexus, Volvo, Maserati, Bentley, Land Rover.
- Cruzar los precios contra el valor de referencia del RUNT o de Fasecolda para detectar avisos por debajo del mercado.
- Segmentar por antigüedad (año modelo) para estimar la curva de depreciación de cada modelo.
- Repetir la recolección cada mes y comparar contra este archivo para medir cómo se mueve el mercado.
