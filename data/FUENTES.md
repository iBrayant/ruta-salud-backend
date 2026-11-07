# Fuentes y construcción de los datos

Versión del conjunto: `veredas-v1` · Fecha: 2026-11-04

## 1. Fuentes oficiales utilizadas

| # | Fuente | Qué se tomó |
|---|---|---|
| F1 | Observatorio de Fusagasugá. *Información general del corregimiento* (5 PDF). https://observatorio.alcaldiafusagasuga.gov.co/corregimientos/ | Indicadores SISBÉN por corregimiento con corte al 11/04/2025: población, categoría A, acueducto, alcantarillado, afiliación a salud, adulto mayor, educación e incapacidad |
| F2 | Plano FR07, *División Político Administrativa Rural*, Acuerdo Municipal 10 de 2023 (IGAC / Secretaría de Planeación) | Código, nombre y área (ha) de las **56 veredas**, y posición de cada una en el plano |
| F3 | Planes de Desarrollo por corregimiento 2026-2029 (Observatorio) | Verificación de los indicadores de F1, estado de las vías rurales y puestos de salud |
| F4 | E.S.E. Hospital San Rafael de Fusagasugá. https://www.hospitaldefusa.gov.co/sedes/ | Sede principal (Diagonal 23 # 12-64) y puestos de salud rurales |
| F5 | OpenStreetMap / Nominatim | Coordenadas del hospital (4.33397, −74.37146) y validación de las coordenadas de las veredas |

## 2. Cómo se obtuvieron las coordenadas
1. Se extrajo el texto vectorial del plano F2 con su posición (`pdftotext -bbox`).
2. La cuadrícula del plano está en **MAGNA-SIRGAS Origen Nacional (EPSG:9377)**. Se calibró la conversión de posición en el PDF a metros usando las etiquetas de la cuadrícula (unos 15,17 m por punto de PDF).
3. La posición de la etiqueta de cada vereda se convirtió de EPSG:9377 a WGS84 con la fórmula inversa de Mercator Transversa.
4. **Validación:** se comparó con OSM para Chinauta, Novillero y La Aguadita. La diferencia fue de unos 600–700 m, lo esperable porque la etiqueta está dentro del polígono pero no en su centro.
5. **Control:** la suma de las áreas extraídas da 17.980,59 ha; el plano reporta 17.980,56 ha.

Scripts que reproducen el proceso: `tools/datos/veredas_extract.py` y `tools/datos/build_data.py`.

## 3. Cómo se calcula el índice de vulnerabilidad (necesidad de atención)

| Componente | Peso | Fuente | Varía por |
|---|---|---|---|
| Pobreza extrema (SISBÉN categoría A) | 0.25 | F1 | corregimiento |
| Sin acueducto | 0.20 | F1/F3 | corregimiento |
| Sin alcantarillado | 0.10 | F1/F3 | corregimiento |
| Sin afiliación a salud | 0.15 | F1/F3 | corregimiento |
| Proporción de adultos mayores (60+) | 0.15 | F1 | corregimiento |
| Aislamiento: **tiempo por vía real** (OSRM/OpenStreetMap) al servicio de salud más rápido de alcanzar | 0.15 | F2/F4/F6 | **vereda** |

> F6: OSRM (Open Source Routing Machine) sobre datos de OpenStreetMap. Por cada vereda se guardan el km y los minutos por vía hasta el hospital y hasta el servicio de salud más cercano.
> **Por qué no se usa la línea recta:** subestima el aislamiento en zona de montaña. Ejemplo: San Rafael está a 3,65 km en línea recta del PS La Aguadita, pero no hay vía directa. Por carretera, su opción más rápida es el hospital, a 18,4 km y 33 min.

Cada componente se normaliza entre 0 y 1 (mín–máx sobre las 56 veredas) y luego se hace un promedio ponderado.

## 4. Limitaciones (se declaran tal cual)
- Los indicadores socioeconómicos solo existen **por corregimiento**. Por eso, dentro de un mismo corregimiento, las veredas solo se diferencian por el componente de aislamiento.
- Las coordenadas son aproximadas (error menor a 1 km).
- Los tiempos de OSRM pueden ser optimistas en vías terciarias destapadas. La penalización por lluvia compensa una parte.
- El tipo de vía es "terciaria" por defecto, según F3. Solo están verificados Chinauta y El Triunfo (Ruta 40) y La Trinidad (vía mixta, unos 80 % pavimentada o en placa huella).
- La ubicación de cada puesto de salud se aproxima con la coordenada de la vereda donde está.
- El índice describe la **necesidad de atención de un territorio**. No es una característica de las personas ni de la comunidad.

## 5. Las 15 veredas del conjunto (3 por corregimiento)
- **Norte:** Los Robles, San Rafael, La Aguadita
- **Occidental:** Novillero, Usatama Baja, Casa de Lata
- **Oriental:** Mosqueral, La Palma, Bethel
- **Sur Occidental:** Chinauta, San Antonio, El Triunfo
- **Sur Oriental:** El Carmen, La Trinidad, Guavio Alto

Criterio de selección: que todos los corregimientos estén representados y que haya veredas cercanas, intermedias y lejanas (de 2,5 a 19,7 km por vía desde el hospital; de 8 a 44 min). El catálogo completo de 56 veredas está en `catalogo_veredas_fusagasuga.json`.
