import requests
from bs4 import BeautifulSoup
import json
import re
import os
import sys # Para frenar si hay peligro
from datetime import datetime
from io import BytesIO
from pypdf import PdfReader
import urllib3

# Desactivar alertas de seguridad SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ARCHIVO_JSON = 'datos_poceada.json'
CARPETA_BACKUP = 'backups'

# ID Base de seguridad
ID_SEGURIDAD = 860 

def obtener_ultimo_id_web_procesado():
    if os.path.exists("ultimo_id_web.txt"):
        with open("ultimo_id_web.txt", "r") as f:
            return int(f.read().strip())
    return ID_SEGURIDAD

def guardar_ultimo_id_web(id_web):
    with open("ultimo_id_web.txt", "w") as f:
        f.write(str(id_web))

def procesar_sorteo(id_url):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_url}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
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
        
        if numero_real_sorteo == 0:
            print("(Usando ID Web) ", end="")
            numero_real_sorteo = id_url

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

        # 3. PDF (FECHA Y POZO)
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
                    
                    texto_limpio = " ".join(texto_pdf.split()) # Limpieza fuerte

                    # Fecha
                    match_f = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_limpio)
                    if match_f:
                        d, m, y = match_f.groups()
                        if len(y) == 2: y = "20" + y
                        fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    # Pozo Francotirador
                    if "ESTIMADO" in texto_limpio.upper():
                        parte = texto_limpio.upper().split("ESTIMADO")[1]
                        match_pozo = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', parte)
                        if match_pozo: pozo_proximo = match_pozo.group(1)
                        else:
                             # Intento secundario
                             m2 = re.search(r'\$\s*([\d\.]+)', parte)
                             if m2: pozo_proximo = m2.group(1)

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

        print(f"✅ OK Sorteo {numero_real_sorteo} (Pozo: ${pozo_proximo})")
        
        return {
            "numeroSorteo": numero_real_sorteo, "id_web": id_url, "fecha": fecha_sorteo, "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": "" 
        }
    except Exception as e:
        print(f"❌ Error crítico: {e}")
        return None

def actualizar_diario():
    print("--- INICIANDO ROBOT DIARIO BLINDADO ---")
    
    # 1. LEER Y VALIDAR HISTORIAL
    historial = []
    if os.path.exists(ARCHIVO_JSON):
        try:
            with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
                historial = json.load(f)
        except Exception as e:
            print(f"🛑 ERROR DE LECTURA JSON: {e}")
            sys.exit(1) # ¡ABORTAR! No tocar nada.
    
    # BLINDAJE: Si el historial se encogió misteriosamente, no guardamos.
    if len(historial) < 50 and os.path.exists(ARCHIVO_JSON):
        print(f"🛑 ALERTA DE SEGURIDAD: El historial tiene solo {len(historial)} registros. Debería tener +400.")
        print("🛑 Se cancela la escritura para no perder datos históricos.")
        sys.exit(1) # ¡ABORTAR!

    # 2. PROCESO DE ACTUALIZACIÓN
    ultimo_id_web = obtener_ultimo_id_web_procesado()
    
    # A. Revisar último (para actualizar pozo si faltaba)
    print(f"> Revisando ID {ultimo_id_web}...")
    dato_actualizado = procesar_sorteo(ultimo_id_web)
    if dato_actualizado:
        for i, s in enumerate(historial):
            if s.get('id_web') == ultimo_id_web:
                historial[i] = dato_actualizado
                break
    
    # B. Buscar siguiente
    siguiente = ultimo_id_web + 1
    print(f"> Buscando ID {siguiente}...")
    dato_nuevo = procesar_sorteo(siguiente)
    
    if dato_nuevo:
        historial.insert(0, dato_nuevo)
        guardar_ultimo_id_web(siguiente)
        print("🎉 ¡NUEVO SORTEO AGREGADO!")

    # 3. GUARDAR (Solo si llegamos aquí seguros)
    with open(ARCHIVO_JSON, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)
        
    # Backup
    if not os.path.exists(CARPETA_BACKUP): os.makedirs(CARPETA_BACKUP)
    bkp = f"{CARPETA_BACKUP}/backup_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(bkp, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    actualizar_diario()