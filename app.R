# ============================================================================
#  Tablero Shiny — Precios de autos deportivos y de alta gama usados, Colombia
#  Fuente: deportivos_alta_gama_colombia.xlsx (hoja "Avisos")
#
#  Para ejecutar:  abrir este archivo en RStudio y pulsar "Run App"
#                  o en consola:  shiny::runApp("app.R")
#
#  El archivo .xlsx debe estar en la misma carpeta que este app.R.
#  Las fotos del marketplace se leen de  www/fotos/  y de  fotos.csv
#  (ver LEEME_TABLERO.md).
# ============================================================================

# --- Dependencias -----------------------------------------------------------
.deps <- c("shiny", "readxl", "dplyr", "plotly", "scales", "DT")
.falta <- .deps[!vapply(.deps, requireNamespace, logical(1), quietly = TRUE)]
if (length(.falta)) {
  message("Instalando paquetes faltantes: ", paste(.falta, collapse = ", "))
  install.packages(.falta, repos = "https://cloud.r-project.org")
}
library(shiny)
library(readxl)
library(dplyr)
library(plotly)
library(scales)
library(DT)

# ============================================================================
#  1. PALETA Y TEMA
#     Paleta validada para daltonismo (deuteranopia/protanopia/tritanopia).
#     Azul = un solo tono para magnitud; los 3 tonos categóricos solo se usan
#     en el eje "portal", que además lleva etiquetas directas.
# ============================================================================
PAL <- list(
  surface   = "#fcfcfb",
  plane     = "#f9f9f7",
  ink       = "#0b0b0b",
  ink2      = "#52514e",
  muted     = "#898781",
  grid      = "#e1e0d9",
  axis      = "#c3c2b7",
  blue      = "#2a78d6",
  blue_dark = "#184f95",
  blue_soft = "#9ec5f4",
  rojo      = "#d03b3b",
  cat       = c("#2a78d6", "#eb6834", "#1baf7a")
)

FUENTE <- "system-ui, -apple-system, Segoe UI, sans-serif"

# Valor por defecto cuando un input aún no existe (definido aquí para no
# depender de que la versión de shiny instalada lo exporte).
`%||%` <- function(a, b) if (is.null(a)) b else a

# Layout base compartido por todos los gráficos de plotly.
tema_ply <- function(p, margen_der = 118, margen_izq = 130) {
  p %>% layout(
    paper_bgcolor = PAL$surface,
    plot_bgcolor  = PAL$surface,
    font   = list(family = FUENTE, color = PAL$ink2, size = 12),
    margin = list(l = margen_izq, r = margen_der, t = 14, b = 52),
    separators = ",.",
    showlegend = FALSE,
    hoverlabel = list(bgcolor = "#ffffff", bordercolor = PAL$axis,
                      font = list(family = FUENTE, color = PAL$ink, size = 12)),
    dragmode = FALSE
  ) %>%
    config(displaylogo = FALSE, locale = "es",
           modeBarButtonsToRemove = c("select2d", "lasso2d", "autoScale2d",
                                      "hoverClosestCartesian",
                                      "hoverCompareCartesian", "zoom2d",
                                      "pan2d", "zoomIn2d", "zoomOut2d"))
}

# Titulo, subtitulo y nota al pie van en HTML alrededor del grafico: los
# titulos nativos de plotly se recortaban contra el borde del contenedor.
panel_grafico <- function(salida, titulo, sub = NULL, alto = 400, pie = NULL,
                          dinamico = FALSE) {
  div(class = "graf",
      div(class = "graf-tit", titulo),
      if (!is.null(sub)) div(class = "graf-sub", sub),
      if (dinamico) uiOutput(paste0("box_", salida))
      else plotlyOutput(salida, height = paste0(alto, "px")),
      if (!is.null(pie)) div(class = "graf-pie", pie))
}

# Los valores se pasan a MILLONES antes de graficar (ver mill()), asi el eje
# muestra "250 M" y no la notacion SI de plotly ("0,2B M").
mill <- function(x) x / 1e6

eje_precio <- function(titulo = "Precio publicado (millones COP)", log = FALSE) {
  base <- list(title = list(text = titulo, font = list(size = 12),
                            standoff = 12),
               gridcolor = PAL$grid, zeroline = FALSE,
               linecolor = PAL$axis, tickcolor = PAL$axis,
               tickfont = list(color = PAL$muted, size = 11),
               tickformat = ",.0f", ticksuffix = " M")
  if (log) {
    base$type <- "log"
    base$title$text <- paste0(titulo, " · escala log")
  }
  base
}

# Paso de marca "bonito" para los ejes de conteo, para no dibujar 52 ticks.
paso_conteo <- function(maximo) {
  bruto <- max(1, maximo / 6)
  opciones <- c(1, 2, 5, 10, 20, 25, 50, 100, 200, 500)
  opciones[which(opciones >= bruto)[1]] %||% 1000
}

# tickmode "array" garantiza una etiqueta por grupo: con 43 modelos plotly
# saltaba etiquetas y las anotaciones de la derecha quedaban descuadradas.
eje_grupos <- function(niveles) {
  list(title = "", categoryorder = "array", categoryarray = niveles,
       tickmode = "array", tickvals = niveles, ticktext = niveles,
       gridcolor = "rgba(0,0,0,0)", zeroline = FALSE, linecolor = PAL$axis,
       tickfont = list(color = PAL$ink2, size = 11.5), automargin = TRUE)
}

# Altura del panel en funcion del numero de grupos, para que cada fila tenga
# aire suficiente y ninguna etiqueta se pise.
alto_grupos <- function(n, por = 25, minimo = 175) max(minimo, por * n + 100)

# Columna de etiquetas (mediana · n) fuera del área de datos, a la derecha.
anot_resumen <- function(res, var) {
  lapply(seq_len(nrow(res)), function(i) {
    list(x = 1.005, y = res[[var]][i], xref = "paper", yref = "y",
         text = paste0(mm(res$med[i]), " · n=", res$n[i]),
         showarrow = FALSE, xanchor = "left", yanchor = "middle",
         font = list(size = 11.5, color = PAL$ink2, family = FUENTE))
  })
}

# --- Etiquetas de dinero ----------------------------------------------------
mm <- function(x) {
  label_number(scale = 1e-6, accuracy = 1, suffix = " M",
               big.mark = ".", decimal.mark = ",")(x)
}
cop <- function(x) {
  ifelse(is.na(x), "ND",
         paste0("$", suppressWarnings(
           formatC(round(x), format = "d", big.mark = ".", decimal.mark = ","))))
}
ent <- function(x) suppressWarnings(
  formatC(x, format = "d", big.mark = ".", decimal.mark = ","))

# ============================================================================
#  2. CARGA Y LIMPIEZA DE DATOS
# ============================================================================
ARCHIVO <- "deportivos_alta_gama_colombia.xlsx"

# Ciudades/municipios colombianos que se intentan inferir desde el título,
# el link y la nota del aviso cuando la columna "Ciudad" viene en ND.
CIUDADES <- c(
  "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena", "Bucaramanga",
  "Pereira", "Manizales", "Armenia", "Cúcuta", "Ibagué", "Villavicencio",
  "Santa Marta", "Montería", "Neiva", "Pasto", "Popayán", "Valledupar",
  "Sincelejo", "Tunja", "Envigado", "Itagüí", "Sabaneta",
  "Rionegro", "Chía", "Cajicá", "Soacha", "Zipaquirá", "Yumbo", "Palmira",
  "Floridablanca", "Girón", "Tuluá", "Duitama",
  "Sogamoso", "Girardot", "Melgar", "Riohacha", "Quibdó", "Florencia",
  "Yopal", "Mocoa", "Arauca", "Tumaco", "Apartadó", "Fusagasugá"
)
# Nota: se excluyen a propósito nombres que colisionan con vocabulario
# automotor (Turbo, Bello, Buga, Soledad), porque generaban falsos positivos
# del tipo "Porsche 911 Turbo" -> Turbo, Antioquia.

sin_tildes <- function(x) {
  x <- enc2utf8(as.character(x))
  chartr("áéíóúÁÉÍÓÚüÜñÑ", "aeiouAEIOUuUnN", x)
}

inferir_ciudad <- function(texto) {
  t <- tolower(sin_tildes(texto))
  base <- tolower(sin_tildes(CIUDADES))
  patrones <- paste0("(^|[^a-z])", gsub(" ", "[ -]", base, fixed = TRUE),
                     "($|[^a-z])")
  hits <- vapply(patrones, function(p) grepl(p, t), logical(length(t)))
  if (length(t) == 1L) hits <- matrix(hits, nrow = 1)
  apply(hits, 1, function(fila) {
    k <- which(fila)
    if (length(k) == 1L) CIUDADES[k] else NA_character_
  })
}

num_seguro <- function(x) suppressWarnings(as.numeric(x))

# ID del aviso dentro del portal (MCO-xxxxxxx). Sirve para emparejar fotos.
id_aviso <- function(link) {
  m <- regmatches(link, regexpr("MCO-?[0-9]+", link))
  out <- rep(NA_character_, length(link))
  hay <- regexpr("MCO-?[0-9]+", link) > 0
  out[hay] <- gsub("-", "", m)
  out
}

cargar_datos <- function(ruta = ARCHIVO) {
  if (!file.exists(ruta)) {
    stop("No encuentro '", ruta, "'. Deja el .xlsx en la misma carpeta que app.R.")
  }
  crudo <- as.data.frame(
    readxl::read_excel(ruta, sheet = "Avisos", col_types = "text"),
    stringsAsFactors = FALSE)
  names(crudo) <- trimws(names(crudo))

  # Localiza columnas sin depender de tildes ni de mayúsculas, para que el app
  # funcione igual en Windows, macOS y Linux con cualquier locale.
  col <- function(clave, obligatoria = TRUE) {
    nn <- tolower(sin_tildes(names(crudo)))
    i <- which(startsWith(nn, tolower(sin_tildes(clave))))
    if (!length(i)) {
      if (obligatoria) {
        stop("No encuentro la columna que empieza por '", clave,
             "' en la hoja 'Avisos'. Columnas presentes: ",
             paste(names(crudo), collapse = " | "))
      }
      return(rep(NA_character_, nrow(crudo)))
    }
    as.character(crudo[[i[1]]])
  }

  d <- data.frame(
    id         = num_seguro(col("#")),
    marca      = trimws(col("marca")),
    modelo     = trimws(col("modelo")),
    portal     = trimws(col("fuente")),
    titulo     = trimws(col("titulo del aviso")),
    precio     = num_seguro(col("precio venta")),
    anio       = num_seguro(col("ano modelo")),
    version    = trimws(col("version")),
    cc         = num_seguro(col("cilindraje")),
    km         = num_seguro(col("kilometraje", FALSE)),
    ciudad_src = trimws(col("ciudad", FALSE)),
    registro   = trimws(col("registro", FALSE)),
    link       = trimws(col("link", FALSE)),
    nota       = trimws(col("nota", FALSE)),
    # La escribe scraping/verificar_enlaces.py. Si no existe, queda en NA y
    # el tablero simplemente no muestra el filtro.
    estado_link = trimws(col("estado del enlace", FALSE)),
    stringsAsFactors = FALSE
  ) %>%
    filter(!is.na(id), !is.na(marca), marca != "")

  # --- Ciudad: la publicada cuando existe; si no, la inferida del texto ------
  publicada <- ifelse(!is.na(d$ciudad_src) & d$ciudad_src != "ND" &
                        d$ciudad_src != "", d$ciudad_src, NA_character_)
  inferida <- inferir_ciudad(paste(d$titulo, d$link, d$nota))
  d$ciudad <- ifelse(!is.na(publicada), publicada, inferida)
  d$origen_ciudad <- ifelse(!is.na(publicada), "Publicada",
                            ifelse(!is.na(inferida), "Inferida del aviso",
                                   "Sin dato"))
  d$ciudad_lbl <- ifelse(is.na(d$ciudad), "Sin dato", d$ciudad)

  d %>%
    mutate(
      duplicado = !is.na(registro) & grepl("Duplicado", registro, fixed = TRUE),
      marca_mod = paste(marca, modelo, sep = " · "),
      portal    = ifelse(is.na(portal) | portal == "", "Sin dato", portal),
      mco       = id_aviso(link),
      enlace_ok = is.na(estado_link) | estado_link == "" |
        !grepl("^Ca", estado_link)
    ) %>%
    arrange(marca, modelo)
}

DATOS <- cargar_datos()

# ============================================================================
#  2b. FOTOS DEL MARKETPLACE
#      Dos fuentes, en este orden:
#        1. www/fotos/<ID>.jpg|jpeg|png|webp   (ID = MCO del aviso, o el # )
#        2. fotos.csv con columnas  id,url     (id = MCO o #; url = enlace)
#      Si no hay ninguna, la tarjeta usa un marcador de posición dibujado.
# ============================================================================
DIR_FOTOS <- file.path("www", "fotos")

mapa_fotos <- function(d) {
  mapa <- setNames(rep(NA_character_, nrow(d)), as.character(d$id))

  # 1. archivos locales
  if (dir.exists(DIR_FOTOS)) {
    arch <- list.files(DIR_FOTOS,
                       pattern = "\\.(jpg|jpeg|png|webp|gif)$",
                       ignore.case = TRUE)
    if (length(arch)) {
      claves <- toupper(tools::file_path_sans_ext(arch))
      for (i in seq_len(nrow(d))) {
        k <- match(toupper(c(d$mco[i], as.character(d$id[i]))), claves)
        k <- k[!is.na(k)]
        if (length(k)) mapa[i] <- paste0("fotos/", arch[k[1]])
      }
    }
  }

  # 2. fotos.csv
  if (file.exists("fotos.csv")) {
    csv <- tryCatch(
      utils::read.csv("fotos.csv", stringsAsFactors = FALSE,
                      fileEncoding = "UTF-8"),
      error = function(e) NULL)
    if (!is.null(csv) && all(c("id", "url") %in% tolower(names(csv)))) {
      names(csv) <- tolower(names(csv))
      csv <- csv[!is.na(csv$url) & nzchar(trimws(csv$url)), , drop = FALSE]
      if (nrow(csv)) {
        claves <- toupper(gsub("-", "", trimws(as.character(csv$id))))
        for (i in seq_len(nrow(d))) {
          if (!is.na(mapa[i])) next            # el archivo local manda
          k <- match(toupper(c(d$mco[i], as.character(d$id[i]))), claves)
          k <- k[!is.na(k)]
          if (length(k)) mapa[i] <- trimws(csv$url[k[1]])
        }
      }
    }
  }
  unname(mapa)
}

DATOS$foto <- mapa_fotos(DATOS)
N_FOTOS <- sum(!is.na(DATOS$foto))

# ¿Se verificaron los enlaces alguna vez? De eso depende que aparezca el filtro.
HAY_ESTADO_LINK <- any(!is.na(DATOS$estado_link) & DATOS$estado_link != "")
N_CAIDOS <- sum(!DATOS$enlace_ok)

RANGO_ANIO <- range(DATOS$anio, na.rm = TRUE)
RANGO_PRECIO_M <- c(floor(min(DATOS$precio, na.rm = TRUE) / 1e6),
                    ceiling(max(DATOS$precio, na.rm = TRUE) / 1e6))
MARCAS   <- sort(unique(DATOS$marca))
MODELOS  <- sort(unique(DATOS$marca_mod))
PORTALES <- sort(unique(DATOS$portal))
CIUDADES_D <- sort(unique(DATOS$ciudad_lbl))
POR_PAGINA <- 12

# ============================================================================
#  3. INTERFAZ
# ============================================================================
css <- sprintf("
  body { background: %s; color: %s; font-family: %s; }
  .titulo-app { font-size: 22px; font-weight: 700; letter-spacing: -0.2px;
                margin: 4px 0 2px 0; }
  .sub-app { color: %s; font-size: 13px; margin-bottom: 14px; }
  .well { background: %s; border: 1px solid rgba(11,11,11,0.10);
          box-shadow: none; border-radius: 10px; }
  .control-label { font-size: 12px; font-weight: 600; color: %s; }

  .kpi-fila { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
  .kpi { flex: 1 1 150px; background: %s; border: 1px solid rgba(11,11,11,0.10);
         border-radius: 10px; padding: 12px 14px; }
  .kpi-lbl { color: %s; font-size: 11px; text-transform: uppercase;
             letter-spacing: 0.4px; margin-bottom: 4px; }
  .kpi-val { color: %s; font-size: 21px; font-weight: 700; line-height: 1.15; }
  .kpi-sub { color: %s; font-size: 11px; margin-top: 3px; }

  .aviso { background: #fff8e6; border: 1px solid rgba(11,11,11,0.10);
           border-left: 3px solid #fab219; border-radius: 8px;
           padding: 10px 12px; font-size: 12.5px; color: %s;
           margin-bottom: 14px; }
  .panel-nota { color: %s; font-size: 12px; margin-top: 8px; }
  .graf { margin-bottom: 26px; }
  .graf-tit { font-size: 15px; font-weight: 700; color: %s; margin-bottom: 1px; }
  .graf-sub { font-size: 12px; color: %s; margin-bottom: 6px; }
  .graf-pie { font-size: 11.5px; color: %s; margin-top: 2px; }
  table.dataTable td { font-size: 12.5px; }

  /* ---------------------------- marketplace ---------------------------- */
  .mk-barra { display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap;
              margin-bottom: 14px; }
  .mk-barra .form-group { margin-bottom: 0; }
  .mk-conteo { color: %s; font-size: 12.5px; padding-bottom: 8px; }
  .mk-grid { display: grid; gap: 14px;
             grid-template-columns: repeat(auto-fill, minmax(248px, 1fr)); }
  .mk-card { background: %s; border: 1px solid rgba(11,11,11,0.10);
             border-radius: 12px; overflow: hidden; display: flex;
             flex-direction: column; transition: box-shadow .15s ease,
             transform .15s ease; }
  .mk-card:hover { box-shadow: 0 6px 18px rgba(11,11,11,0.10);
                   transform: translateY(-2px); }
  .mk-foto { position: relative; width: 100%%; aspect-ratio: 16/10;
             background: linear-gradient(140deg, #eef3fa 0%%, #e3eaf3 100%%);
             display: flex; align-items: center; justify-content: center;
             overflow: hidden; }
  .mk-foto img { width: 100%%; height: 100%%; object-fit: cover; display: block; }
  .mk-foto .mk-ph { color: %s; opacity: .5; }
  .mk-marca { position: absolute; left: 10px; top: 10px;
              background: rgba(252,252,251,0.92); color: %s;
              font-size: 10.5px; font-weight: 700; letter-spacing: .5px;
              text-transform: uppercase; padding: 3px 8px; border-radius: 999px; }
  .mk-cuerpo { padding: 12px 13px 13px 13px; display: flex;
               flex-direction: column; gap: 7px; flex: 1; }
  .mk-titulo { font-size: 14.5px; font-weight: 700; color: %s; line-height: 1.25; }
  .mk-version { font-size: 11.5px; color: %s; line-height: 1.35;
                min-height: 2.4em; }
  .mk-precio { font-size: 18px; font-weight: 700; color: %s; }
  .mk-precio.nd { font-size: 13px; font-weight: 600; color: %s; }
  .mk-chips { display: flex; flex-wrap: wrap; gap: 5px; }
  .mk-chip { font-size: 10.5px; color: %s; background: %s;
             border: 1px solid rgba(11,11,11,0.08); border-radius: 6px;
             padding: 2px 7px; white-space: nowrap; }
  .mk-pie { margin-top: auto; padding-top: 4px; }
  .mk-btn { display: block; text-align: center; font-size: 12.5px;
            font-weight: 600; text-decoration: none; padding: 7px 10px;
            border-radius: 8px; background: %s; color: #fff !important; }
  .mk-btn:hover { background: %s; text-decoration: none; }
  .mk-btn.off { background: %s; color: %s !important; cursor: default; }
  .mk-btn.caido { background: %s; color: %s !important; }
  .mk-btn.caido:hover { background: %s; }
  .mk-chip.caido { background: #fdeeee; border-color: rgba(208,59,59,0.35);
                   color: %s; font-weight: 600; }
  .mk-card.caido .mk-foto { filter: grayscale(0.7); opacity: .75; }
  .mk-nav { display: flex; align-items: center; justify-content: center;
            gap: 12px; margin: 20px 0 6px 0; color: %s; font-size: 13px; }
", PAL$plane, PAL$ink, FUENTE, PAL$ink2, PAL$surface, PAL$ink2,
   PAL$surface, PAL$muted, PAL$ink, PAL$muted, PAL$ink2, PAL$ink2,
   PAL$ink, PAL$ink2, PAL$muted,
   PAL$ink2, PAL$surface, PAL$blue_dark, PAL$ink2, PAL$ink, PAL$ink2, PAL$ink, PAL$muted,
   PAL$ink2, PAL$plane, PAL$blue, PAL$blue_dark, PAL$grid, PAL$muted,
   PAL$plane, PAL$ink2, PAL$grid, PAL$rojo, PAL$ink2)

# Selector desplegable con buscador. Vacío = "todas las opciones".
desplegable <- function(id, etiqueta, opciones, marcador) {
  selectizeInput(id, etiqueta, choices = opciones, selected = NULL,
                 multiple = TRUE,
                 options = list(placeholder = marcador,
                                plugins = list("remove_button"),
                                closeAfterSelect = FALSE))
}

ui <- fluidPage(
  tags$head(tags$style(HTML(css)), tags$title("Precios alta gama Colombia")),

  div(class = "titulo-app", "Precios de deportivos y alta gama usados · Colombia"),
  div(class = "sub-app",
      sprintf("%s avisos recolectados el 24-ago-2026 en portales colombianos. Precios publicados por el vendedor, no de transacción.",
              ent(nrow(DATOS)))),

  sidebarLayout(
    sidebarPanel(
      width = 3,
      desplegable("marca",  "Marca",  MARCAS,     "Todas las marcas"),
      desplegable("modelo", "Modelo", MODELOS,    "Todos los modelos"),
      desplegable("portal", "Portal", PORTALES,   "Todos los portales"),
      desplegable("ciudad", "Ciudad", CIUDADES_D, "Todas las ciudades"),
      div(class = "panel-nota",
          "Escribe dentro de cualquier lista para buscar. Sin selección = todo."),
      hr(),
      sliderInput("precio", "Precio publicado (millones COP)",
                  min = RANGO_PRECIO_M[1], max = RANGO_PRECIO_M[2],
                  value = RANGO_PRECIO_M, step = 5, sep = "."),
      sliderInput("anio", "Año modelo",
                  min = RANGO_ANIO[1], max = RANGO_ANIO[2],
                  value = RANGO_ANIO, step = 1, sep = ""),
      checkboxInput("incluir_sin_anio", "Incluir avisos sin año", TRUE),
      hr(),
      if (HAY_ESTADO_LINK)
        checkboxInput("solo_vigentes",
                      sprintf("Solo avisos con enlace vigente (%s caídos)",
                              ent(N_CAIDOS)), TRUE),
      checkboxInput("sin_dup", "Excluir avisos espejados entre portales", TRUE),
      checkboxInput("log", "Escala logarítmica de precio", FALSE),
      sliderInput("min_n", "Mínimo de avisos por grupo", min = 1, max = 15,
                  value = 3, step = 1),
      hr(),
      actionButton("reset", "Restablecer filtros", class = "btn-sm btn-default"),
      div(class = "panel-nota",
          "Solo entran a las estadísticas de precio los avisos con precio publicado.")
    ),

    mainPanel(
      width = 9,
      uiOutput("kpis"),
      tabsetPanel(
        id = "tabs", type = "tabs",
        tabPanel("Marketplace",
                 br(),
                 uiOutput("mk_barra"),
                 uiOutput("mk_grid"),
                 uiOutput("mk_nav")),
        tabPanel("Por marca",
                 br(),
                 panel_grafico("p_marca", "Distribución de precios por marca",
                   "Cada punto es un aviso; la caja marca el 50 % central. A la derecha, mediana y número de avisos.",
                   440, dinamico = TRUE,
                   "Pasa el cursor por cualquier punto para ver el aviso. La caja aparece solo desde el mínimo de avisos fijado a la izquierda."),
                 panel_grafico("p_marca_n", "Oferta disponible por marca",
                   "Número de avisos con precio publicado", 300, dinamico = TRUE)),
        tabPanel("Por modelo",
                 br(),
                 panel_grafico("p_modelo", "Distribución de precios por modelo",
                   "Ordenado de menor a mayor mediana. A la derecha, mediana y número de avisos.",
                   620, dinamico = TRUE,
                   "Filtra por marca en el panel izquierdo para leer el detalle con comodidad.")),
        tabPanel("Por lugar",
                 br(),
                 uiOutput("aviso_ciudad"),
                 panel_grafico("p_portal", "Distribución de precios por portal",
                   "Dónde se está ofertando cada aviso", 300, dinamico = TRUE),
                 panel_grafico("p_ciudad", "Avisos por ciudad identificada",
                   "Ciudad publicada por el vendedor o deducida del texto del aviso",
                   280, dinamico = TRUE,
                   "Cuenta la oferta, no los precios: aquí sí entran los avisos sin precio publicado."),
                 h5("Resumen por portal"),
                 DTOutput("t_portal"),
                 br()),
        tabPanel("Distribución general",
                 br(),
                 panel_grafico("p_hist", "Distribución general de precios",
                   "Todos los avisos que pasan los filtros", 340),
                 panel_grafico("p_anio", "Precio frente a año modelo",
                   "Cada punto es un aviso; la línea es una tendencia suavizada, no una predicción",
                   360),
                 div(class = "graf-pie", uiOutput("pie_anio"))),
        tabPanel("Tabla de avisos",
                 br(),
                 downloadButton("bajar", "Descargar CSV filtrado",
                                class = "btn-sm"),
                 br(), br(),
                 DTOutput("tabla"))
      )
    )
  )
)

# ============================================================================
#  4. SERVIDOR
# ============================================================================
server <- function(input, output, session) {

  # Los modelos disponibles se recortan a las marcas elegidas.
  observeEvent(input$marca, ignoreNULL = FALSE, {
    mods <- if (!length(input$marca)) MODELOS else
      sort(unique(DATOS$marca_mod[DATOS$marca %in% input$marca]))
    updateSelectizeInput(session, "modelo", choices = mods,
                         selected = intersect(input$modelo, mods),
                         server = FALSE)
  })

  observeEvent(input$reset, {
    for (f in c("marca", "modelo", "portal", "ciudad")) {
      updateSelectizeInput(session, f, selected = character(0))
    }
    updateSliderInput(session, "precio", value = RANGO_PRECIO_M)
    updateSliderInput(session, "anio", value = RANGO_ANIO)
    updateCheckboxInput(session, "sin_dup", value = TRUE)
    if (HAY_ESTADO_LINK) updateCheckboxInput(session, "solo_vigentes", value = TRUE)
    updateCheckboxInput(session, "log", value = FALSE)
    updateCheckboxInput(session, "incluir_sin_anio", value = TRUE)
    updateSliderInput(session, "min_n", value = 3)
  })

  # --- Datos filtrados ------------------------------------------------------
  # base(): todos los avisos que pasan los filtros, tengan o no precio.
  #         Se usa para conteos de oferta y para el marketplace.
  # filtrados(): además exige precio publicado dentro del rango.
  #         Se usa para todo lo que sea estadística de precio.
  base <- reactive({
    # Un desplegable vacio (NULL o character(0)) significa "todas las opciones".
    d <- DATOS
    if (length(input$marca))  d <- d %>% filter(marca %in% input$marca)
    if (length(input$modelo)) d <- d %>% filter(marca_mod %in% input$modelo)
    if (length(input$portal)) d <- d %>% filter(portal %in% input$portal)
    if (length(input$ciudad)) d <- d %>% filter(ciudad_lbl %in% input$ciudad)
    if (isTRUE(input$sin_dup))  d <- d %>% filter(!duplicado)
    if (isTRUE(input$solo_vigentes)) d <- d %>% filter(enlace_ok)
    d <- d %>% filter(is.na(precio) |
                        (precio >= input$precio[1] * 1e6 &
                           precio <= input$precio[2] * 1e6))
    if (isTRUE(input$incluir_sin_anio)) {
      d %>% filter(is.na(anio) |
                     (anio >= input$anio[1] & anio <= input$anio[2]))
    } else {
      d %>% filter(!is.na(anio), anio >= input$anio[1], anio <= input$anio[2])
    }
  })

  filtrados <- reactive(base() %>% filter(!is.na(precio)))

  vacio <- function(d, msg = "No hay avisos con los filtros actuales.") {
    validate(need(nrow(d) > 0, msg))
  }

  # Resumen por grupo, ordenado de menor a mayor mediana.
  resumen <- function(d, var) {
    d %>% group_by(g = .data[[var]]) %>%
      summarise(n = n(), med = median(precio), .groups = "drop") %>%
      arrange(med)
  }

  hover_aviso <- function(d) {
    paste0("<b>", d$marca, " ", d$modelo, "</b><br>",
           ifelse(is.na(d$version) | d$version == "", "", paste0(d$version, "<br>")),
           cop(d$precio), "<br>",
           "Año ", ifelse(is.na(d$anio), "ND", as.character(d$anio)),
           " · ", d$portal, "<extra></extra>")
  }

  # Gráfico de caja horizontal reutilizado por marca, modelo y portal.
  caja_por <- function(d, var, colores = NULL) {
    res <- resumen(d, var)
    niveles <- as.character(res$g)
    d <- d %>% mutate(g = as.character(.data[[var]]))
    grandes <- res$g[res$n >= input$min_n]

    p <- plot_ly()

    # Cajas solo para los grupos que superan el mínimo de avisos.
    for (g in niveles[niveles %in% grandes]) {
      sub_d <- d[d$g == g, ]
      cl <- if (is.null(colores)) PAL$blue else unname(colores[g])
      p <- p %>% add_trace(
        x = mill(sub_d$precio), y = sub_d$g, type = "box", orientation = "h",
        name = g, boxpoints = "all", jitter = 0.55, pointpos = 0,
        width = 0.6,
        marker = list(color = cl, size = 6, opacity = 0.72),
        line = list(color = cl, width = 1.4),
        fillcolor = paste0(cl, "22"),
        hoveron = "points", text = hover_aviso(sub_d),
        hovertemplate = "%{text}", showlegend = FALSE)
    }
    # Grupos pequeños: solo los puntos, una caja de 1 o 2 avisos no dice nada.
    chicos <- d[!(d$g %in% grandes), ]
    if (nrow(chicos)) {
      cl <- if (is.null(colores)) PAL$blue else unname(colores[chicos$g])
      p <- p %>% add_trace(
        x = mill(chicos$precio), y = chicos$g, type = "scatter", mode = "markers",
        marker = list(color = cl, size = 6, opacity = 0.72),
        text = hover_aviso(chicos), hovertemplate = "%{text}",
        showlegend = FALSE)
    }

    p %>%
      layout(xaxis = eje_precio(log = isTRUE(input$log)),
             yaxis = eje_grupos(niveles),
             annotations = anot_resumen(
               res %>% rename(gg = g) %>% as.data.frame(), "gg")) %>%
      tema_ply()
  }

  # Barras horizontales de conteo.
  barras_conteo <- function(d, var) {
    res <- d %>% count(g = .data[[var]]) %>% arrange(n)
    plot_ly() %>%
      add_trace(x = res$n, y = as.character(res$g), type = "bar",
                orientation = "h", width = 0.62,
                marker = list(color = PAL$blue,
                              line = list(color = PAL$surface, width = 2)),
                text = ent(res$n), textposition = "outside",
                textfont = list(color = PAL$ink2, size = 11.5),
                hovertemplate = paste0("<b>%{y}</b><br>%{x} avisos<extra></extra>"),
                showlegend = FALSE) %>%
      layout(xaxis = list(title = list(text = "Avisos", standoff = 10),
                          gridcolor = PAL$grid,
                          zeroline = FALSE, linecolor = PAL$axis,
                          tickfont = list(color = PAL$muted, size = 11),
                          dtick = paso_conteo(max(res$n)),
                          range = c(0, max(res$n) * 1.16)),
             yaxis = eje_grupos(as.character(res$g)),
             bargap = 0.45) %>%
      tema_ply(margen_der = 40)
  }

  # --- KPIs -----------------------------------------------------------------
  output$kpis <- renderUI({
    d <- filtrados(); b <- base()
    if (nrow(b) == 0) {
      return(div(class = "aviso", "Ningún aviso cumple los filtros actuales."))
    }
    tile <- function(lbl, val, sub = NULL) {
      div(class = "kpi", div(class = "kpi-lbl", lbl),
          div(class = "kpi-val", val),
          if (!is.null(sub)) div(class = "kpi-sub", sub))
    }
    if (nrow(d) == 0) {
      return(div(class = "kpi-fila",
                 tile("Avisos en el filtro", ent(nrow(b)),
                      "ninguno con precio publicado")))
    }
    div(class = "kpi-fila",
        tile("Avisos con precio", ent(nrow(d)),
             sprintf("de %s en el filtro · %s marcas · %s modelos",
                     ent(nrow(b)), n_distinct(d$marca), n_distinct(d$marca_mod))),
        tile("Mediana", cop(median(d$precio)),
             sprintf("promedio %s", cop(mean(d$precio)))),
        tile("Rango", paste0(mm(min(d$precio)), " – ", mm(max(d$precio))),
             "mínimo y máximo publicados"),
        tile("Rango intercuartílico",
             paste0(mm(quantile(d$precio, .25)), " – ",
                    mm(quantile(d$precio, .75))),
             "50 % central del mercado"),
        tile("Con ciudad conocida",
             sprintf("%.0f %%", 100 * mean(b$origen_ciudad != "Sin dato")),
             sprintf("%s de %s avisos", ent(sum(b$origen_ciudad != "Sin dato")),
                     ent(nrow(b))))
    )
  })

  # ======================================================== MARKETPLACE ======
  pagina <- reactiveVal(1)
  observeEvent(list(input$marca, input$modelo, input$portal, input$ciudad,
                    input$precio, input$anio, input$sin_dup,
                    input$incluir_sin_anio, input$mk_orden, input$mk_solo_precio),
               pagina(1), ignoreNULL = FALSE)

  mk_datos <- reactive({
    d <- base()
    if (isTRUE(input$mk_solo_precio)) d <- d %>% filter(!is.na(precio))
    orden <- input$mk_orden %||% "precio_desc"
    switch(orden,
      precio_desc = d %>% arrange(is.na(precio), desc(precio)),
      precio_asc  = d %>% arrange(is.na(precio), precio),
      anio_desc   = d %>% arrange(is.na(anio), desc(anio), desc(precio)),
      anio_asc    = d %>% arrange(is.na(anio), anio, precio),
      marca       = d %>% arrange(marca, modelo, desc(precio)),
      d)
  })

  output$mk_barra <- renderUI({
    n <- nrow(mk_datos())
    div(class = "mk-barra",
        div(style = "min-width:230px",
            selectInput("mk_orden", "Ordenar por",
                        choices = c("Precio: mayor a menor" = "precio_desc",
                                    "Precio: menor a mayor" = "precio_asc",
                                    "Año: más nuevo primero" = "anio_desc",
                                    "Año: más viejo primero" = "anio_asc",
                                    "Marca y modelo (A-Z)"   = "marca"),
                        selected = input$mk_orden %||% "precio_desc",
                        width = "100%")),
        div(style = "padding-bottom:8px",
            checkboxInput("mk_solo_precio", "Solo con precio publicado",
                          value = isTRUE(input$mk_solo_precio))),
        div(class = "mk-conteo",
            if (n == 0) "Sin vehículos para estos filtros."
            else sprintf("%s vehículo%s · %s con foto",
                         ent(n), if (n == 1) "" else "s",
                         ent(sum(!is.na(mk_datos()$foto))))))
  })

  tarjeta <- function(r) {
    chips <- Filter(Negate(is.null), list(
      if (!is.na(r$anio)) span(class = "mk-chip", r$anio),
      if (!is.na(r$cc)) span(class = "mk-chip", paste0(ent(r$cc), " cc")),
      span(class = "mk-chip", r$portal),
      if (r$ciudad_lbl != "Sin dato") span(class = "mk-chip", r$ciudad_lbl),
      if (!r$enlace_ok) span(class = "mk-chip caido", "aviso retirado")
    ))

    foto <- if (!is.na(r$foto)) {
      tags$img(src = r$foto, alt = paste(r$marca, r$modelo), loading = "lazy")
    } else {
      # Marcador de posición: silueta, sin inventar una foto que no existe.
      HTML(sprintf('<svg class="mk-ph" width="72" height="72" viewBox="0 0 24 24"
             fill="none" stroke="%s" stroke-width="1.3"
             stroke-linecap="round" stroke-linejoin="round">
             <path d="M5 17h14M3 13l1.8-5.1A2 2 0 0 1 6.7 6.5h10.6a2 2 0 0 1
             1.9 1.4L21 13v4a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1v-1H6v1a1 1 0 0 1-1
             1H4a1 1 0 0 1-1-1v-4Z"/><circle cx="7.5" cy="14.5" r="1"/>
             <circle cx="16.5" cy="14.5" r="1"/><path d="M4.5 13h15"/></svg>',
             PAL$blue_dark))
    }

    div(class = if (r$enlace_ok) "mk-card" else "mk-card caido",
        div(class = "mk-foto", foto, div(class = "mk-marca", r$marca)),
        div(class = "mk-cuerpo",
            div(class = "mk-titulo", r$modelo),
            div(class = "mk-version",
                if (is.na(r$version) || r$version %in% c("", "ND"))
                  "Versión no indicada" else r$version),
            if (is.na(r$precio))
              div(class = "mk-precio nd", "Precio no publicado")
            else div(class = "mk-precio", cop(r$precio)),
            div(class = "mk-chips", chips),
            div(class = "mk-pie",
                if (is.na(r$link) || !nzchar(r$link))
                  div(class = "mk-btn off", "Sin enlace")
                else if (!r$enlace_ok)
                  # El enlace se deja abrible, pero avisando: MercadoLibre
                  # redirige al listado de carros parecidos, no da error.
                  tags$a(class = "mk-btn caido", href = r$link,
                         target = "_blank", rel = "noopener",
                         title = "Este aviso ya no está publicado; el portal te llevará a vehículos parecidos",
                         "Aviso retirado · ver similares")
                else
                  tags$a(class = "mk-btn", href = r$link, target = "_blank",
                         rel = "noopener", "Ver aviso"))))
  }

  output$mk_grid <- renderUI({
    d <- mk_datos()
    if (nrow(d) == 0) return(NULL)
    ini <- (pagina() - 1) * POR_PAGINA + 1
    fin <- min(nrow(d), pagina() * POR_PAGINA)
    if (ini > nrow(d)) { pagina(1); ini <- 1; fin <- min(nrow(d), POR_PAGINA) }
    div(class = "mk-grid",
        lapply(seq(ini, fin), function(i) tarjeta(d[i, ])))
  })

  output$mk_nav <- renderUI({
    n <- nrow(mk_datos())
    if (n == 0) return(NULL)
    paginas <- max(1, ceiling(n / POR_PAGINA))
    ini <- (pagina() - 1) * POR_PAGINA + 1
    div(class = "mk-nav",
        actionButton("mk_prev", "‹ Anteriores", class = "btn-sm",
                     disabled = if (pagina() <= 1) "disabled" else NULL),
        span(sprintf("Página %s de %s · vehículos %s–%s de %s",
                     ent(pagina()), ent(paginas), ent(ini),
                     ent(min(n, pagina() * POR_PAGINA)), ent(n))),
        actionButton("mk_next", "Siguientes ›", class = "btn-sm",
                     disabled = if (pagina() >= paginas) "disabled" else NULL))
  })

  observeEvent(input$mk_prev, pagina(max(1, pagina() - 1)))
  observeEvent(input$mk_next, {
    paginas <- max(1, ceiling(nrow(mk_datos()) / POR_PAGINA))
    pagina(min(paginas, pagina() + 1))
  })

  # Contenedores de altura variable segun cuantos grupos entren en el filtro.
  caja_dinamica <- function(salida, cuenta_fn, por = 25, minimo = 210) {
    renderUI({
      n <- tryCatch(cuenta_fn(), error = function(e) 6)
      plotlyOutput(salida, height = paste0(alto_grupos(n, por, minimo), "px"))
    })
  }
  output$box_p_marca   <- caja_dinamica("p_marca",
    function() n_distinct(filtrados()$marca), 30)
  output$box_p_marca_n <- caja_dinamica("p_marca_n",
    function() n_distinct(filtrados()$marca), 26)
  output$box_p_modelo  <- caja_dinamica("p_modelo",
    function() n_distinct(filtrados()$marca_mod), 25)
  output$box_p_portal  <- caja_dinamica("p_portal",
    function() n_distinct(filtrados()$portal), 60, 190)
  output$box_p_ciudad  <- caja_dinamica("p_ciudad",
    function() n_distinct(base()$ciudad_lbl[base()$origen_ciudad != "Sin dato"]),
    46, 175)

  # ---------------------------------------------------------------- POR MARCA
  output$p_marca <- renderPlotly({
    d <- filtrados(); vacio(d)
    caja_por(d, "marca")
  })

  output$p_marca_n <- renderPlotly({
    d <- filtrados(); vacio(d)
    barras_conteo(d, "marca")
  })

  # --------------------------------------------------------------- POR MODELO
  output$p_modelo <- renderPlotly({
    d <- filtrados(); vacio(d)
    caja_por(d, "marca_mod")
  })

  # ---------------------------------------------------------------- POR LUGAR
  output$aviso_ciudad <- renderUI({
    d <- base()
    con <- sum(d$origen_ciudad != "Sin dato")
    div(class = "aviso",
        tags$b("Sobre el campo “lugar”. "),
        sprintf("Los portales colombianos no exponen la ciudad en los resultados indexados, así que la columna Ciudad viene en ND en casi todos los registros: con los filtros actuales solo %s de %s avisos tienen ciudad conocida. ",
                ent(con), ent(nrow(d))),
        "Por eso el eje de lugar que sí sostiene el análisis es el ",
        tags$b("portal donde se publica"),
        ". El gráfico de ciudades queda listo para cuando amplíes el scraping con la ficha completa del aviso.")
  })

  output$p_portal <- renderPlotly({
    d <- filtrados(); vacio(d)
    niveles <- unique(as.character(resumen(d, "portal")$g))
    colores <- setNames(PAL$cat[seq_along(niveles)], niveles)
    caja_por(d, "portal", colores = colores)
  })

  output$p_ciudad <- renderPlotly({
    d <- base() %>% filter(origen_ciudad != "Sin dato")
    validate(need(nrow(d) > 0,
                  "Ningún aviso del filtro actual trae ciudad identificable. Es la limitación conocida del scraping: los portales no publican la ciudad en los resultados indexados."))
    barras_conteo(d, "ciudad_lbl")
  })

  output$t_portal <- renderDT({
    d <- filtrados(); vacio(d)
    res <- d %>% group_by(Portal = portal) %>%
      summarise(Avisos = n(), Marcas = n_distinct(marca),
                `Mínimo` = cop(min(precio)), `Q1` = cop(quantile(precio, .25)),
                `Mediana` = cop(median(precio)), `Q3` = cop(quantile(precio, .75)),
                `Máximo` = cop(max(precio)), .groups = "drop") %>%
      arrange(desc(Avisos))
    datatable(res, rownames = FALSE,
              options = list(dom = "t", ordering = TRUE, pageLength = 20))
  })

  # ---------------------------------------------------- DISTRIBUCIÓN GENERAL
  output$p_hist <- renderPlotly({
    d <- filtrados(); vacio(d)
    med <- median(d$precio)
    v <- mill(d$precio)
    ancho <- (max(v) - min(v)) / 32
    plot_ly(height = 340) %>%
      add_trace(x = v, type = "histogram",
                xbins = if (isTRUE(input$log)) NULL else
                  list(start = min(v), end = max(v), size = ancho),
                nbinsx = if (isTRUE(input$log)) 32 else NULL,
                marker = list(color = PAL$blue,
                              line = list(color = PAL$surface, width = 1)),
                hovertemplate = "%{y} avisos · %{x} M<extra></extra>",
                showlegend = FALSE) %>%
      layout(xaxis = eje_precio(log = isTRUE(input$log)),
             yaxis = list(title = list(text = "Avisos", standoff = 10),
                          gridcolor = PAL$grid,
                          zeroline = FALSE, linecolor = PAL$axis,
                          tickfont = list(color = PAL$muted, size = 11)),
             bargap = 0.04,
             shapes = list(list(type = "line", x0 = mill(med), x1 = mill(med),
                                y0 = 0, y1 = 1, yref = "paper",
                                line = list(color = PAL$rojo, width = 1.6,
                                            dash = "dash"))),
             annotations = list(list(
               x = mill(med), y = 1, yref = "paper", yanchor = "top",
               xanchor = "left", text = paste0(" Mediana ", cop(med)),
               showarrow = FALSE,
               font = list(color = PAL$rojo, size = 12, family = FUENTE)))) %>%
      tema_ply(margen_der = 40, margen_izq = 60)
  })

  # La tendencia se ajusta solo en el tramo con datos densos: extenderla hasta
  # los clásicos de los 80 producía una banda enorme sin ningún aviso detrás.
  corte_anio <- reactive({
    d <- filtrados() %>% filter(!is.na(anio))
    if (nrow(d) == 0) return(NA_real_)
    as.numeric(quantile(d$anio, 0.05, na.rm = TRUE))
  })

  output$pie_anio <- renderUI({
    d <- filtrados() %>% filter(!is.na(anio))
    corte <- corte_anio()
    if (is.na(corte) || sum(d$anio >= corte) <= 12) return(NULL)
    HTML(paste0("La tendencia se ajusta desde <b>", round(corte),
                "</b> en adelante, que es donde hay avisos suficientes; los",
                " clásicos anteriores se muestran como puntos pero no entran",
                " en el suavizado."))
  })

  output$p_anio <- renderPlotly({
    d <- filtrados() %>% filter(!is.na(anio))
    validate(need(nrow(d) > 0, "Ningún aviso del filtro actual reporta año."))
    corte <- corte_anio()
    d_t <- d %>% filter(anio >= corte)

    p <- plot_ly(height = 360) %>%
      add_trace(x = d$anio, y = mill(d$precio), type = "scatter", mode = "markers",
                marker = list(color = PAL$blue, size = 7, opacity = 0.7),
                text = hover_aviso(d), hovertemplate = "%{text}",
                showlegend = FALSE)

    if (nrow(d_t) > 12 && n_distinct(d_t$anio) > 4) {
      aj <- try(stats::loess(precio ~ anio, data = d_t, span = 0.9), silent = TRUE)
      if (!inherits(aj, "try-error")) {
        rej <- seq(min(d_t$anio), max(d_t$anio), length.out = 120)
        pr <- stats::predict(aj, newdata = data.frame(anio = rej), se = TRUE)
        ok <- !is.na(pr$fit)
        p <- p %>%
          add_ribbons(x = rej[ok],
                      ymin = mill(pmax(0, pr$fit[ok] - 1.96 * pr$se.fit[ok])),
                      ymax = mill(pr$fit[ok] + 1.96 * pr$se.fit[ok]),
                      line = list(width = 0), fillcolor = "rgba(158,197,244,0.45)",
                      hoverinfo = "skip", showlegend = FALSE) %>%
          add_lines(x = rej[ok], y = mill(pr$fit[ok]),
                    line = list(color = PAL$blue_dark, width = 2.4),
                    hoverinfo = "skip", showlegend = FALSE)
      }
    }

    p %>% layout(
      xaxis = list(title = list(text = "Año modelo", standoff = 10),
                   gridcolor = PAL$grid, zeroline = FALSE,
                   linecolor = PAL$axis, dtick = 5,
                   tickfont = list(color = PAL$muted, size = 11)),
      yaxis = eje_precio(log = isTRUE(input$log))
    ) %>% tema_ply(margen_der = 40, margen_izq = 80)
  })

  # ------------------------------------------------------------------- TABLA
  output$tabla <- renderDT({
    d <- filtrados(); vacio(d)
    tb <- d %>% transmute(
      Marca = marca, Modelo = modelo, `Versión` = version,
      `Año` = ifelse(is.na(anio), "ND", as.character(anio)),
      `Cilindraje` = ifelse(is.na(cc), "ND", ent(cc)),
      Portal = portal, Ciudad = ciudad_lbl,
      Enlace = ifelse(is.na(estado_link) | estado_link == "",
                      "Sin verificar", estado_link),
      `Precio (COP)` = precio,
      Aviso = ifelse(is.na(link) | link == "", "",
                     paste0("<a href='", link, "' target='_blank'>abrir</a>"))
    ) %>% arrange(desc(`Precio (COP)`))
    datatable(tb, rownames = FALSE, escape = FALSE, filter = "top",
              options = list(pageLength = 25, scrollX = TRUE,
                             lengthMenu = c(10, 25, 50, 100, 500))) %>%
      formatCurrency("Precio (COP)", currency = "$", interval = 3,
                     mark = ".", digits = 0)
  })

  output$bajar <- downloadHandler(
    filename = function() paste0("avisos_filtrados_",
                                 format(Sys.Date(), "%Y%m%d"), ".csv"),
    content = function(file) {
      d <- base() %>%
        select(marca, modelo, version, anio, cc, portal, ciudad = ciudad_lbl,
               origen_ciudad, precio, titulo, link, nota)
      utils::write.csv(d, file, row.names = FALSE, fileEncoding = "UTF-8")
    }
  )
}

shinyApp(ui, server)
