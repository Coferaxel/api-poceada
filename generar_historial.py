import requests
from bs4 import BeautifulSoup
import json
import re
import time
from io import BytesIO
from pypdf import PdfReader
import urllib3

# Desactivar alertas de seguridad
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- RANGO CONFIRMADO POR VOS ---
RANGO_INICIO = 452
RANGO_FIN = 869 # Ponemos uno más (869) para asegurar que incluya el 868

lista_sorteos = []
print(f"--- INICIANDO CARGA MASIVA DE HISTORIAL ({RANGO_INICIO} a {RANGO_FIN-1}) ---")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

for id_url in range(RANGO_INICIO, RANGO_FIN):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_url}"
    
    try:
        print(f"Procesando ID Web {id_url}...", end=" ")
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        
        if response.status_code != 200:
            print(f"❌ (Off)")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- A. BUSCAR EL NÚMERO REAL DEL SORTEO ---
        # Buscamos en los títulos <h5> donde dice "N° Sorteo:"
        numero_real_sorteo = 0
        titulos = soup.find_all('h5')
        for t in titulos:
            if "Sorteo" in t.text:
                # Extraemos solo los dígitos del texto (ej: "N° Sorteo: 2236" -> 2236)
                nums = re.findall(r'\d+', t.text)
                if nums:
                    numero_real_sorteo = int(nums[0])
                    break
        
        # Si no lo encuentra, usamos el ID web como respaldo (pero avisamos)
        if numero_real_sorteo == 0:
            print(f"[⚠️ Usando ID Web] ", end="")
            numero_real_sorteo = id_url

        # --- B. EXTRAER BOLILLAS ---
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5: 
            print("⚠️ (Sin bolillas)")
            continue

        # --- C. BUSCAR PDF (FECHA Y POZO) ---
        fecha_sorteo = "Fecha Pendiente"
        pozo_proximo = "0"
        
        # Buscamos link que diga 'POCEADA' y termine en .pdf
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

                    # Fecha
                    match_f = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_pdf)
                    if match_f:
                        d, m, y = match_f.groups()
                        if len(y) == 2: y = "20" + y
                        fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    # Pozo
                    if "POZO ESTIMADO" in texto_pdf:
                        parte = texto_pdf.split("POZO ESTIMADO")[1]
                        match_pozo = re.search(r'\$?\s*([\d]{1,3}(?:\.[\d]{3})*(?:,[\d]{2}))', parte)
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
        obj = {
            "numeroSorteo": numero_real_sorteo, # EL NÚMERO REAL (Ej: 2236)
            "id_web": id_url, # Guardamos el ID interno por referencia
            "fecha": fecha_sorteo,
            "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, "fechaProximo": ""
        }
        
        lista_sorteos.insert(0, obj)
        print(f"✅ Sorteo N° {numero_real_sorteo} OK (ID {id_url})")
        # time.sleep(0.1) # Pequeña pausa para ser amables con el servidor

    except Exception as e:
        print(f"❌ Error: {e}")

# Guardar archivo final
with open('datos_poceada.json', 'w', encoding='utf-8') as f:
    json.dump(lista_sorteos, f, indent=4, ensure_ascii=False)

print(f"\n✨ BASE DE DATOS RECONSTRUIDA: {len(lista_sorteos)} sorteos guardados.")