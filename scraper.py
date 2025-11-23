import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

ARCHIVO_JSON = 'datos_poceada.json'

def actualizar_diario():
    print("--- INICIANDO ROBOT DIARIO INTELIGENTE ---")
    
    # 1. LEER EL ÚLTIMO SORTEO GUARDADO
    try:
        if os.path.exists(ARCHIVO_JSON):
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        else:
            historial = []
    except Exception:
        historial = []
        
    # Buscamos el ID más alto
    ultimo_id = 451
    if historial:
        ultimo_id = historial[0].get('numeroSorteo', 451)
    
    siguiente_id = ultimo_id + 1
    print(f"Último guardado: {ultimo_id}. Buscando: {siguiente_id}...")

    # 2. BUSCAR EL SIGUIENTE
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{siguiente_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Sorteo {siguiente_id} no disponible (Código {response.status_code})")
            return 

        soup = BeautifulSoup(response.content, 'html.parser')
        texto_pagina = soup.get_text()

        # --- EXTRAER NÚMEROS ---
        numeros = []
        items_lista = soup.find_all("li", class_="results-list__item")
        for item in items_lista:
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        
        numeros = sorted(list(set(numeros[:10])))

        if len(numeros) < 5:
            print("⚠️ Web activa pero sin números cargados.")
            return

        # --- EXTRAER FECHA INTELIGENTE ---
        fecha_sorteo = datetime.now().strftime("%Y-%m-%d 21:00:00") # Fallback
        fecha_encontrada = False
        
        # Intento A: PDF Link
        link_pdf = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        if link_pdf:
            href = link_pdf.get('href', '')
            match_pdf = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', href)
            if match_pdf:
                d, m, y = match_pdf.groups()
                if len(y) == 2: y = "20" + y
                fecha_sorteo = f"{y}-{m}-{d} 21:00:00"
                fecha_encontrada = True

        # Intento B: Texto
        if not fecha_encontrada:
            match_texto = re.search(r'(\d{2})[\s/-](\d{2})[\s/-](\d{4})', texto_pagina)
            if match_texto:
                d, m, y = match_texto.groups()
                fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

        # --- EXTRAER POZO PRÓXIMO ---
        pozo_proximo = "0"
        match_pozo = re.search(r'POZO.*ESTIMADO.*\$?\s*([\d\.,]+)', texto_pagina, re.IGNORECASE)
        if match_pozo:
            pozo_proximo = match_pozo.group(1).strip()

        # --- EXTRAER PREMIOS ---
        datos_premios = { "pozo5": "0", "gan5": 0, "vacante5": False, "pozo4": "0", "gan4": 0, "pozo3": "0", "gan3": 0, "pozo2": "0", "gan2": 0 }
        
        header_premios = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header_premios:
            card_body = header_premios.find_parent("div", class_="card").find("article", class_="card-body")
            filas = card_body.find_all("li", class_="results-list__item")
            def limpio(t): return t.replace("\n", "").strip()

            if len(filas) > 1:
                cols = filas[1].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["pozo5"] = limpio(cols[1].text)
                    gan = limpio(cols[2].text)
                    datos_premios["vacante5"] = (gan.upper() == "VACANTE" or gan == "0")
                    datos_premios["gan5"] = 0 if datos_premios["vacante5"] else int(gan.replace(".",""))
            if len(filas) > 2:
                cols = filas[2].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan4"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo4"] = limpio(cols[3].text)
            if len(filas) > 3:
                cols = filas[3].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan3"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo3"] = limpio(cols[3].text)
            if len(filas) > 4:
                cols = filas[4].find_all("p", class_="results-number")
                if len(cols) >= 4:
                    datos_premios["gan2"] = int(limpio(cols[2].text).replace(".",""))
                    datos_premios["pozo2"] = limpio(cols[3].text)

        # --- GUARDAR ---
        nuevo_sorteo = {
            "numeroSorteo": siguiente_id,
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

        historial.insert(0, nuevo_sorteo)
        
        with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)
            
        print(f"✅ ¡ÉXITO! Sorteo {siguiente_id} guardado. Fecha: {fecha_sorteo}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    actualizar_diario()