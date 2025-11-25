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

# Ajusta esto para que busque el sorteo de hoy (ej: 868 o el que toque)
ID_BASE_WEB = 860 

def obtener_ultimo_id_web_procesado():
    if os.path.exists("ultimo_id_web.txt"):
        with open("ultimo_id_web.txt", "r") as f:
            return int(f.read().strip())
    return ID_BASE_WEB

def guardar_ultimo_id_web(id_web):
    with open("ultimo_id_web.txt", "w") as f:
        f.write(str(id_web))

def procesar_sorteo(id_url):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_url}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        print(f"🔍 Consultando ID Web {id_url}...", end=" ")
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        if response.status_code != 200:
            print("❌ No disponible.")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. NÚMERO REAL
        numero_real_sorteo = 0
        for t in soup.find_all('h5'):
            if "Sorteo" in t.text:
                nums = re.findall(r'\d+', t.text)
                if nums: numero_real_sorteo = int(nums[0])
        if numero_real_sorteo == 0: numero_real_sorteo = id_url

        # 2. NÚMEROS
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            p = item.find_all("p", class_="results-number")
            if len(p) == 2:
                txt = p[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5: 
            print("⚠️ Página vacía.")
            return None

        # 3. PDF (ESTRATEGIA FUERZA BRUTA)
        fecha_sorteo = datetime.now().strftime("%Y-%m-%d 21:00:00")
        pozo_proximo = "0"
        
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
                    
                    # 1. BUSCAR FECHA
                    match_f = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_pdf)
                    if match_f:
                        d, m, y = match_f.groups()
                        if len(y) == 2: y = "20" + y
                        fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    # 2. BUSCAR EL POZO (EL NÚMERO MÁS GRANDE)
                    # Buscamos todos los montos que parezcan dinero (ej: 123.456,78)
                    # Regex: Dígitos con puntos, terminados en coma y 2 decimales
                    candidatos = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto_pdf)
                    
                    mayor_monto = 0.0
                    string_mayor = "0"

                    for c in candidatos:
                        # Convertimos a float para comparar (quitamos puntos, cambiamos coma por punto)
                        try:
                            valor_limpio = float(c.replace('.', '').replace(',', '.'))
                            # Filtramos números locos (ej: fechas confundidas)
                            if valor_limpio > mayor_monto and valor_limpio > 1000000: # Asumimos que el pozo es > 1 millón
                                mayor_monto = valor_limpio
                                string_mayor = c
                        except: pass
                    
                    if mayor_monto > 0:
                        pozo_proximo = string_mayor
                        
            except: pass

        # 4. PREMIOS
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

        print(f"✅ Sorteo {numero_real_sorteo} - Pozo Detectado: ${pozo_proximo}")
        
        return {
            "numeroSorteo": numero_real_sorteo, "id_web": id_url, "fecha": fecha_sorteo, "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": "" 
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def actualizar_diario():
    historial = []
    if os.path.exists(ARCHIVO_JSON):
        with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
            historial = json.load(f)
    
    # Revisar último ID web procesado
    ultimo_id_web = obtener_ultimo_id_web_procesado()
    
    print(f"> Reprocesando último ID ({ultimo_id_web}) para buscar pozo...")
    dato_actualizado = procesar_sorteo(ultimo_id_web)
    
    if dato_actualizado:
        # Actualizar el existente
        for i, s in enumerate(historial):
            if s.get('id_web') == ultimo_id_web:
                historial[i] = dato_actualizado
                break
        # O si no estaba, agregarlo
        else:
             historial.insert(0, dato_actualizado)

    # Intentar el siguiente
    siguiente = ultimo_id_web + 1
    print(f"> Buscando nuevo ({siguiente})...")
    dato_nuevo = procesar_sorteo(siguiente)
    if dato_nuevo:
        historial.insert(0, dato_nuevo)
        guardar_ultimo_id_web(siguiente)

    with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    actualizar_diario()