import requests
from bs4 import BeautifulSoup
import json
import re
import os
import sys
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader
import urllib3

# Desactivar alertas SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ARCHIVO_JSON = 'datos_poceada.json'
CARPETA_BACKUP = 'backups'

# --- 1. FUNCIÓN PARA ENCONTRAR EL LINK DEL ÚLTIMO SORTEO ---
def obtener_link_ultimo_sorteo():
    url_indice = "https://loteria.chaco.gov.ar/juego/quiniela_poceada"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        print(f"🔍 Paso 1: Buscando en la lista principal...", end=" ")
        response = requests.get(url_indice, headers=headers, timeout=15, verify=False)
        
        if response.status_code != 200:
            print("❌ Web caída.")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Buscamos todos los links que lleven a un detalle de sorteo
        # Generalmente son href="/detalle_poceada/XXXX"
        links = soup.find_all('a', href=re.compile(r'/detalle_poceada/\d+'))
        
        if not links:
            print("⚠️ No encontré el botón 'VER' en la lista.")
            return None
            
        # El primero de la lista suele ser el más reciente en esa tabla
        ultimo_link_relativo = links[0]['href']
        url_final = f"https://loteria.chaco.gov.ar{ultimo_link_relativo}"
        
        print(f"✅ ¡Encontrado! Link: {url_final}")
        return url_final

    except Exception as e:
        print(f"❌ Error buscando link: {e}")
        return None

# --- 2. FUNCIÓN PARA PROCESAR EL DETALLE (Al que entramos) ---
def procesar_detalle_sorteo(url_destino):
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        print(f"🔍 Paso 2: Escaneando detalle...", end=" ")
        response = requests.get(url_destino, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        texto_pagina = soup.get_text(" ", strip=True)

        # A. NÚMERO DE SORTEO
        numero_real_sorteo = 0
        # Buscamos "N° Sorteo: 2239" en los títulos
        for t in soup.find_all('h5'):
            if "Sorteo" in t.text:
                nums = re.findall(r'\d+', t.text)
                if nums: numero_real_sorteo = int(nums[0])
        
        # Si falló h5, buscamos en texto plano
        if numero_real_sorteo == 0:
             m = re.search(r'Sorteo.*?(\d{4})', texto_pagina)
             if m: numero_real_sorteo = int(m.group(1))

        if numero_real_sorteo == 0:
            print("⚠️ No encontré el N° Sorteo.")
            return None

        # B. NÚMEROS GANADORES
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) >= 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        
        numeros = sorted(list(set(numeros[:10])))
        
        if len(numeros) < 5: 
            print(f"⚠️ Sorteo {numero_real_sorteo} sin bolillas cargadas.")
            return None

        # C. FECHA Y POZO (PDF + TEXTO)
        fecha_sorteo = datetime.now().strftime("%Y-%m-%d 21:00:00")
        pozo_proximo = "Ver próximo sorteo"
        
        # Fecha del texto HTML (Ej: 29/11/2025)
        match_f_html = re.search(r'(\d{2}/\d{2}/\d{4})', texto_pagina)
        if match_f_html:
            d, m, y = match_f_html.group(1).split('/')
            fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

        # Buscar PDF para el Pozo
        link_pdf = soup.find('a', href=re.compile(r'POCEADA.*\.pdf', re.IGNORECASE))
        if link_pdf:
            try:
                raw_href = requests.utils.unquote(link_pdf.get('href'))
                pdf_url = "https://loteria.chaco.gov.ar" + raw_href if raw_href.startswith('/') else raw_href
                
                resp_pdf = requests.get(pdf_url, headers=headers, verify=False)
                if resp_pdf.status_code == 200:
                    reader = PdfReader(BytesIO(resp_pdf.content))
                    texto_pdf = ""
                    for page in reader.pages: texto_pdf += page.extract_text() + " "
                    texto_limpio = " ".join(texto_pdf.split())

                    # Refinar Fecha si el HTML falló
                    match_f = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_limpio)
                    if match_f:
                        d, m, y = match_f.groups()
                        if len(y) == 2: y = "20" + y
                        # Prioridad al PDF si parece válido
                        fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    # POZO ESTIMADO
                    if "ESTIMADO" in texto_limpio.upper():
                        parte = texto_limpio.upper().split("ESTIMADO")[1]
                        # Buscar monto
                        m_dinero = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', parte)
                        if m_dinero: pozo_proximo = m_dinero.group(1)
            except: pass

        # D. PREMIOS Y VACANTE
        dp = { "pozo5": "0", "gan5": 0, "vacante5": False, "pozo4": "0", "gan4": 0, "pozo3": "0", "gan3": 0, "pozo2": "0", "gan2": 0 }
        
        # Lógica textual para vacante
        seccion_5 = re.search(r'Pozo 5 Aciertos(.*?)(Pozo 4|$)', texto_pagina, re.IGNORECASE)
        if seccion_5:
            txt5 = seccion_5.group(1)
            dp["vacante5"] = "VACANTE" in txt5.upper()
            if not dp["vacante5"] and "1" in txt5: dp["gan5"] = 1
            m = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', txt5)
            if m: dp["pozo5"] = m.group(1)

        # Lógica tabla HTML (Más precisa)
        header = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header:
            filas = header.find_parent("div", class_="card").find_all("li", class_="results-list__item")
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

        print(f"✅ OK Sorteo {numero_real_sorteo} ({fecha_sorteo})")
        
        return {
            "numeroSorteo": numero_real_sorteo,
            "id_web": 0,
            "fecha": fecha_sorteo, "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": "" 
        }

    except Exception as e:
        print(f"❌ Error detalle: {e}")
        return None

def actualizar_diario():
    print("--- ROBOT DOBLE PASO (LISTA -> DETALLE) ---")
    
    # 1. Cargar Historial
    historial = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        except: pass
    
    # 2. OBTENER URL DEL ÚLTIMO SORTEO REAL
    url_detalle = obtener_link_ultimo_sorteo()
    
    if url_detalle:
        # 3. PROCESAR ESA URL ESPECÍFICA
        dato_nuevo = procesar_detalle_sorteo(url_detalle)

        if dato_nuevo:
            numero_nuevo = dato_nuevo['numeroSorteo']
            
            # Verificar si ya existe
            existe = False
            for i, s in enumerate(historial):
                if s['numeroSorteo'] == numero_nuevo:
                    existe = True
                    # Actualizamos por si cambió algo (ej: cargaron el PDF tarde)
                    historial[i] = dato_nuevo 
                    print("   (Registro actualizado)")
                    break
            
            if not existe:
                print("🎉 ¡NUEVO SORTEO AGREGADO AL HISTORIAL!")
                historial.insert(0, dato_nuevo)
            
            # Guardar
            with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
                json.dump(historial, f, indent=4, ensure_ascii=False)
            
            # Backup
            if not os.path.exists(CARPETA_BACKUP): os.makedirs(CARPETA_BACKUP)
            bkp = f"{CARPETA_BACKUP}/backup_{datetime.now().strftime('%Y-%m-%d')}.json"
            with open(bkp, 'w', encoding='utf-8') as f:
                json.dump(historial, f, indent=4, ensure_ascii=False)
    else:
        print("⚠️ No se pudo obtener el link del último sorteo.")

if __name__ == "__main__":
    actualizar_diario()