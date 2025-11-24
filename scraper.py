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

# --- CONFIGURACIÓN DEL RASTREO ---
# Si el último que viste en la web (marzo) era el ID 866, 
# para llegar al de hoy (Sorteo 2236) probemos buscar desde el ID 1000 en adelante
# OJO: Tú tendrás que ajustar este "ID_INICIAL_RASTREO" probando cuál es el de hoy.
# Si entras a la web y el link del último sorteo termina en /1234, pon 1234 aquí.
ID_INICIAL_RASTREO = 2230 # Probamos con 2230 por si acaso coincidieron los números

def obtener_ultimo_id_url_procesado():
    """Devuelve el ID de la URL (no el sorteo) que procesamos por última vez"""
    if os.path.exists("ultimo_id_url.txt"):
        with open("ultimo_id_url.txt", "r") as f:
            return int(f.read().strip())
    return ID_INICIAL_RASTREO

def guardar_ultimo_id_url(id_url):
    with open("ultimo_id_url.txt", "w") as f:
        f.write(str(id_url))

def actualizar_diario():
    print("--- ROBOT V3: CORRIGIENDO NÚMEROS DE SORTEO ---")
    
    # 1. Cargar JSON existente
    historial = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        except: pass

    # Empezamos a buscar desde el último ID de URL conocido
    id_actual = obtener_ultimo_id_url_procesado()
    id_siguiente = id_actual + 1
    
    print(f"🔍 Buscando en URL ID: {id_siguiente}...")

    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_siguiente}"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        
        if response.status_code != 200:
            print(f"⚠️ URL ID {id_siguiente} no responde (Fin del rastreo).")
            return

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- A. EXTRAER EL NÚMERO REAL DEL SORTEO (CORRECCIÓN) ---
        # Buscamos el <h5> que tiene el número. Ej: <h5> N° Sorteo: 2235 </h5>
        numero_real_sorteo = 0
        titulos = soup.find_all('h5')
        for t in titulos:
            if "Sorteo" in t.text:
                # Limpiamos el texto para sacar solo el número "2235"
                nums = re.findall(r'\d+', t.text)
                if nums:
                    numero_real_sorteo = int(nums[0])
                    break
        
        if numero_real_sorteo == 0:
            # Si falló el h5, intentamos usar el ID de la URL como fallback, 
            # pero avisando que podría estar mal.
            print(f"⚠️ No encontré 'N° Sorteo' en el HTML. Usando ID URL.")
            numero_real_sorteo = id_siguiente
        
        print(f"🎯 ¡Encontrado! Es el Sorteo N° {numero_real_sorteo}")

        # --- B. EXTRAER NÚMEROS GANADORES ---
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        numeros = sorted(list(set(numeros[:10])))
        
        if len(numeros) < 5: 
            print("⚠️ Sin bolillas cargadas.")
            return

        # --- C. PDF (FECHA Y POZO) ---
        fecha_sorteo = datetime.now().strftime("%Y-%m-%d 21:00:00")
        pozo_proximo = "0"
        
        link_pdf = soup.find('a', href=re.compile(r'POCEADA.*\.pdf', re.IGNORECASE))
        if link_pdf:
            try:
                raw_href = link_pdf.get('href')
                pdf_url = "https://loteria.chaco.gov.ar" + raw_href if raw_href.startswith('/') else raw_href
                
                resp_pdf = requests.get(pdf_url, headers=headers, verify=False)
                if resp_pdf.status_code == 200:
                    reader = PdfReader(BytesIO(resp_pdf.content))
                    texto_pdf = ""
                    for page in reader.pages: texto_pdf += page.extract_text() + " "
                    texto_pdf = texto_pdf.replace("\n", " ").replace("  ", " ")

                    match_f = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_pdf)
                    if match_f:
                        d, m, y = match_f.groups()
                        if len(y) == 2: y = "20" + y
                        fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    if "POZO ESTIMADO" in texto_pdf:
                        parte_final = texto_pdf.split("POZO ESTIMADO")[1]
                        match_pozo = re.search(r'\$?\s*([\d]{1,3}(?:\.[\d]{3})*(?:,[\d]{2}))', parte_final)
                        if match_pozo: pozo_proximo = match_pozo.group(1).strip()
            except: pass

        # --- D. PREMIOS ---
        dp = { "pozo5": "0", "gan5": 0, "vacante5": False, "pozo4": "0", "gan4": 0, "pozo3": "0", "gan3": 0, "pozo2": "0", "gan2": 0 }
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

        # --- GUARDAR ---
        nuevo_sorteo = {
            "numeroSorteo": numero_real_sorteo, # <--- ¡AQUÍ USAMOS EL REAL!
            "id_url": id_siguiente, # Guardamos el ID interno por si acaso
            "fecha": fecha_sorteo,
            "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": ""
        }

        # Insertar al principio
        historial.insert(0, nuevo_sorteo)
        
        with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)
            
        # Actualizar el "puntero" para mañana saber desde dónde buscar
        guardar_ultimo_id_url(id_siguiente)
        
        # Backup
        if not os.path.exists(CARPETA_BACKUP): os.makedirs(CARPETA_BACKUP)
        bkp = f"{CARPETA_BACKUP}/backup_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(bkp, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)

        print(f"✅ Guardado: Sorteo {numero_real_sorteo} (ID URL: {id_siguiente}) - Pozo: ${pozo_proximo}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    actualizar_diario()