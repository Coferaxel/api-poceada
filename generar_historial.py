import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime

# --- CONFIGURACIÓN ---
RANGO_INICIO = 452  
RANGO_FIN = 900     # Ajusta esto hasta el último sorteo actual
ARCHIVO_SALIDA = 'datos_poceada.json'

print(f"--- INICIANDO ESCANEO INTELIGENTE ({RANGO_INICIO}-{RANGO_FIN}) ---")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

lista_sorteos = []

for id_sorteo in range(RANGO_INICIO, RANGO_FIN):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_sorteo}"
    
    try:
        print(f"Sorteo {id_sorteo}...", end=" ")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ (Web no disponible)")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        texto_pagina = soup.get_text() # Obtenemos todo el texto plano

        # --- 1. EXTRAER NÚMEROS ---
        numeros = []
        items_lista = soup.find_all("li", class_="results-list__item")
        for item in items_lista:
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit():
                    numeros.append(int(txt))
        
        # Filtramos y ordenamos (nos quedamos con los primeros 10 únicos)
        numeros = sorted(list(set(numeros[:10])))

        if len(numeros) < 5:
            print("⚠️ (Sin números cargados)")
            continue

        # --- 2. EXTRAER FECHA (LÓGICA MEJORADA) ---
        fecha_sorteo = "Fecha Desconocida"
        
        # Intento A: Buscar en el link del PDF (El más preciso)
        link_pdf = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        fecha_encontrada = False
        
        if link_pdf:
            href = link_pdf.get('href', '')
            # Buscamos patrón DD-MM-YYYY o DD-MM-YY
            match_pdf = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', href)
            if match_pdf:
                d, m, y = match_pdf.groups()
                if len(y) == 2: y = "20" + y # Corregir años cortos
                fecha_sorteo = f"{y}-{m}-{d} 21:00:00"
                fecha_encontrada = True

        # Intento B: Si falló A, buscar cualquier fecha en el texto de la página
        if not fecha_encontrada:
            # Buscamos patrones como "20/11/2025" o "20-11-2025" cerca de la palabra "Sorteo" o al inicio
            match_texto = re.search(r'(\d{2})[\s/-](\d{2})[\s/-](\d{4})', texto_pagina)
            if match_texto:
                d, m, y = match_texto.groups()
                fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

        # --- 3. EXTRAER POZO ESTIMADO PRÓXIMO ---
        pozo_proximo = "0"
        # Buscamos frases como "POZO ESTIMADO" seguido de números
        match_pozo = re.search(r'POZO.*ESTIMADO.*\$?\s*([\d\.,]+)', texto_pagina, re.IGNORECASE)
        if match_pozo:
            # Limpiamos el texto para que quede solo el número bonito (ej: 121.901.459,28)
            pozo_proximo = match_pozo.group(1).strip()

        # --- 4. EXTRAER PREMIOS ---
        # (Esta lógica se mantiene porque funcionaba bien con la estructura de lista)
        datos_premios = {
            "pozo5": "0", "gan5": 0, "vacante5": False,
            "pozo4": "0", "gan4": 0,
            "pozo3": "0", "gan3": 0,
            "pozo2": "0", "gan2": 0
        }
        
        header_premios = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header_premios:
            card_body = header_premios.find_parent("div", class_="card").find("article", class_="card-body")
            filas = card_body.find_all("li", class_="results-list__item")
            
            def limpio(t): return t.replace("\n", "").strip()

            if len(filas) > 1: # 5 Aciertos
                cols = filas[1].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["pozo5"] = limpio(cols[1].text)
                    gan = limpio(cols[2].text)
                    datos_premios["vacante5"] = (gan.upper() == "VACANTE" or gan == "0")
                    datos_premios["gan5"] = 0 if datos_premios["vacante5"] else int(gan.replace(".",""))

            if len(filas) > 2: # 4 Aciertos
                cols = filas[2].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan4"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo4"] = limpio(cols[3].text)
            
            if len(filas) > 3: # 3 Aciertos
                cols = filas[3].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan3"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo3"] = limpio(cols[3].text)
            
            if len(filas) > 4: # 2 Aciertos
                cols = filas[4].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan2"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo2"] = limpio(cols[3].text)

        # --- 5. GUARDAR ---
        obj = {
            "numeroSorteo": id_sorteo,
            "fecha": fecha_sorteo,
            "numerosGanadores": numeros,
            "pozo5aciertos": datos_premios["pozo5"],
            "vacante5aciertos": datos_premios["vacante5"],
            "ganadores4aciertos": datos_premios["gan4"],
            "premio4aciertos": datos_premios["pozo4"],
            "ganadores3aciertos": datos_premios["gan3"],
            "premio3aciertos": datos_premios["pozo3"],
            "ganadores2aciertos": datos_premios["gan2"],
            "premio2aciertos": datos_premios["pozo2"],
            "pozoEstimadoProximo": pozo_proximo,
            "fechaProximo": "" 
        }
        
        lista_sorteos.insert(0, obj)
        print(f"✅ OK ({fecha_sorteo}) - Prox: ${pozo_proximo}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

# Guardar archivo final
with open(ARCHIVO_SALIDA, 'w', encoding='utf-8') as f:
    json.dump(lista_sorteos, f, indent=4, ensure_ascii=False)

print(f"\n✨ PROCESO TERMINADO: {len(lista_sorteos)} sorteos guardados.")