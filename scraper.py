import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader # Nueva herramienta

# --- CONFIGURACIÓN ---
ARCHIVO_JSON = 'datos_poceada.json'
CARPETA_BACKUP = 'backups'

def actualizar_diario():
    print("--- INICIANDO ROBOT LECTOR DE PDF ---")
    
    # 1. LEER HISTORIAL
    try:
        if os.path.exists(ARCHIVO_JSON):
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        else:
            historial = []
    except Exception:
        historial = []
        
    ultimo_id = 451
    if historial:
        ultimo_id = historial[0].get('numeroSorteo', 451)
    
    siguiente_id = ultimo_id + 1
    print(f"Buscando Sorteo {siguiente_id}...")

    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{siguiente_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Sorteo {siguiente_id} no disponible.")
            return 

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- EXTRACCIÓN DE NÚMEROS (Del HTML) ---
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5: return

        # --- EXTRACCIÓN AVANZADA DESDE EL PDF ---
        fecha_sorteo = datetime.now().strftime("%Y-%m-%d 21:00:00")
        pozo_proximo = "0" # Valor por defecto
        
        link_pdf = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        
        if link_pdf:
            try:
                # 1. Descargar PDF a memoria
                pdf_url = "https://loteria.chaco.gov.ar" + link_pdf.get('href') if link_pdf.get('href').startswith('/') else link_pdf.get('href')
                print(f"📄 Leyendo PDF: {pdf_url}")
                
                resp_pdf = requests.get(pdf_url, headers=headers)
                if resp_pdf.status_code == 200:
                    # 2. Leer contenido del PDF
                    reader = PdfReader(BytesIO(resp_pdf.content))
                    texto_pdf = ""
                    for page in reader.pages:
                        texto_pdf += page.extract_text() + "\n"
                    
                    # 3. Buscar FECHA en el PDF
                    match_fecha = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_pdf) # Buscar DD/MM/YYYY
                    if match_fecha:
                        d, m, y = match_fecha.groups()
                        if len(y) == 2: y = "20" + y
                        fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    # 4. Buscar POZO PRÓXIMO en el PDF
                    # Busca "POZO ESTIMADO..." seguido de números
                    match_pozo = re.search(r'POZO.*ESTIMADO.*\$?\s*([\d\.,]+)', texto_pdf, re.IGNORECASE)
                    if match_pozo:
                        pozo_proximo = match_pozo.group(1).strip()
                        print(f"💰 ¡Pozo encontrado en PDF!: {pozo_proximo}")
            except Exception as e:
                print(f"⚠️ No se pudo leer el PDF: {e}")

        # --- EXTRACCIÓN DE PREMIOS (Del HTML, esto suele estar bien ahí) ---
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
        nuevo = {
            "numeroSorteo": siguiente_id, "fecha": fecha_sorteo, "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, # AQUÍ VA EL VALOR DEL PDF
            "fechaProximo": ""
        }

        historial.insert(0, nuevo)
        
        with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)
            
        if not os.path.exists(CARPETA_BACKUP): os.makedirs(CARPETA_BACKUP)
        nombre_backup = f"{CARPETA_BACKUP}/backup_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(nombre_backup, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=4, ensure_ascii=False)

        print(f"✅ Sorteo {siguiente_id} guardado. Pozo Próximo: ${pozo_proximo}")

    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    actualizar_diario()