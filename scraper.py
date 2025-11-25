import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ARCHIVO_JSON = 'datos_poceada.json'
CARPETA_BACKUP = 'backups'

# RANGO para probar (Ajusta a lo que necesites, ej: el último ID 868)
RANGO_INICIO = 860 
RANGO_FIN = 875 

lista_sorteos = []
print(f"--- ROBOT FECHAS HTML ({RANGO_INICIO}-{RANGO_FIN}) ---")

headers = {'User-Agent': 'Mozilla/5.0'}

for id_url in range(RANGO_INICIO, RANGO_FIN):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_url}"
    try:
        print(f"ID {id_url}...", end=" ")
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        if response.status_code != 200:
            print("❌")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')
        texto_pagina = soup.get_text()

        # 1. NÚMERO REAL
        numero_real_sorteo = 0
        for t in soup.find_all('h5'):
            if "Sorteo" in t.text:
                nums = re.findall(r'\d+', t.text)
                if nums: numero_real_sorteo = int(nums[0])
        if numero_real_sorteo == 0: continue

        # 2. BOLILLAS
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            p = item.find_all("p", class_="results-number")
            if len(p) == 2:
                t = p[1].text.strip()
                if t.isdigit(): numeros.append(int(t))
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5: continue

        # --- 3. FECHA DESDE EL HTML (NUEVO) ---
        fecha_sorteo = "Fecha Pendiente"
        
        # Buscamos patrón DD/MM/YYYY en todo el texto de la página
        # Ej: "Sorteo del 22/11/2025" o simplemente la fecha suelta
        match_fecha_html = re.search(r'(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})', texto_pagina)
        
        if match_fecha_html:
            d, m, y = match_fecha_html.groups()
            # Aseguramos ceros (05 en vez de 5)
            d = d.zfill(2)
            m = m.zfill(2)
            fecha_sorteo = f"{y}-{m}-{d} 21:00:00"
        
        # --- 4. PDF (SOLO PARA POZO) ---
        pozo_proximo = "0"
        link_pdf = soup.find('a', href=re.compile(r'POCEADA.*\.pdf', re.IGNORECASE))
        if link_pdf:
            try:
                raw = requests.utils.unquote(link_pdf.get('href'))
                p_url = "https://loteria.chaco.gov.ar" + raw if raw.startswith('/') else raw
                resp = requests.get(p_url, headers=headers, verify=False)
                if resp.status_code == 200:
                    reader = PdfReader(BytesIO(resp.content))
                    txt_pdf = ""
                    for p in reader.pages: txt_pdf += p.extract_text() + " "
                    txt_pdf = " ".join(txt_pdf.split())
                    
                    if "ESTIMADO" in txt_pdf.upper():
                        parte = txt_pdf.upper().split("ESTIMADO")[1]
                        m_dinero = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', parte)
                        if m_dinero: pozo_proximo = m_dinero.group(1)
            except: pass

        # 5. PREMIOS (HTML)
        dp = { "pozo5": "0", "gan5": 0, "vacante5": False, "pozo4": "0", "gan4": 0, "pozo3": "0", "gan3": 0, "pozo2": "0", "gan2": 0 }
        h = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if h:
            filas = h.find_parent("div", class_="card").find_all("li", class_="results-list__item")
            def cln(t): return t.replace("\n", "").strip()
            if len(filas) > 1:
                dp["pozo5"] = cln(filas[1].find_all("p")[1].text)
                g = cln(filas[1].find_all("p")[2].text)
                dp["vacante5"] = (g.upper() == "VACANTE" or g == "0")
                dp["gan5"] = 0 if dp["vacante5"] else int(g.replace(".",""))
            if len(filas) > 2:
                dp["gan4"] = int(cln(filas[2].find_all("p")[2].text).replace(".",""))
                dp["pozo4"] = cln(filas[2].find_all("p")[3].text)
            if len(filas) > 3:
                dp["gan3"] = int(cln(filas[3].find_all("p")[2].text).replace(".",""))
                dp["pozo3"] = cln(filas[3].find_all("p")[3].text)
            if len(filas) > 4:
                dp["gan2"] = int(cln(filas[4].find_all("p")[2].text).replace(".",""))
                dp["pozo2"] = cln(filas[4].find_all("p")[3].text)

        # GUARDAR
        obj = {
            "numeroSorteo": numero_real_sorteo, "id_web": id_url, "fecha": fecha_sorteo,
            "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": "" 
        }
        lista_sorteos.insert(0, obj)
        print(f"✅ {numero_real_sorteo} | Fecha: {fecha_sorteo}")

    except Exception as e: print(f"❌ {e}")

# Solo si es script de historial masivo, guarda pisando todo. 
# Si es scraper diario, usa la lógica de insert.
with open('datos_poceada.json', 'w', encoding='utf-8') as f:
    json.dump(lista_sorteos, f, indent=4, ensure_ascii=False)

print(f"\n✨ LISTO.")