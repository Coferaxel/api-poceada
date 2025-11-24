import requests
from bs4 import BeautifulSoup
import json
import re
import time
from io import BytesIO
from pypdf import PdfReader

# AJUSTA ESTO AL RANGO ACTUAL (Para que escanee el último y lo arregle)
RANGO_INICIO = 3490 
RANGO_FIN = 3505 # Pon un número un poco mayor al último sorteo real

lista_sorteos = []
print(f"--- REPARANDO HISTORIAL CON LECTURA PDF ({RANGO_INICIO}-{RANGO_FIN}) ---")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

for id_sorteo in range(RANGO_INICIO, RANGO_FIN):
    url = f"https://loteria.chaco.gov.ar/detalle_poceada/{id_sorteo}"
    
    try:
        print(f"Sorteo {id_sorteo}...", end=" ")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ (No existe)")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        # 1. NÚMEROS
        numeros = []
        for item in soup.find_all("li", class_="results-list__item"):
            parrafos = item.find_all("p", class_="results-number")
            if len(parrafos) == 2:
                txt = parrafos[1].text.strip()
                if txt.isdigit(): numeros.append(int(txt))
        
        numeros = sorted(list(set(numeros[:10])))
        if len(numeros) < 5: 
            print("⚠️ (Sin datos)")
            continue

        # 2. LEER PDF (FECHA Y POZO PRÓXIMO)
        fecha_sorteo = "Fecha Pendiente"
        pozo_proximo = "0" # Valor por defecto si falla el PDF
        
        link_pdf = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        
        if link_pdf:
            try:
                pdf_url = "https://loteria.chaco.gov.ar" + link_pdf.get('href') if link_pdf.get('href').startswith('/') else link_pdf.get('href')
                
                resp_pdf = requests.get(pdf_url, headers=headers)
                if resp_pdf.status_code == 200:
                    # Leemos el PDF en memoria
                    reader = PdfReader(BytesIO(resp_pdf.content))
                    texto_pdf = ""
                    for page in reader.pages:
                        texto_pdf += page.extract_text() + "\n"
                    
                    # Buscar FECHA
                    match_f = re.search(r'(\d{2})[-/](\d{2})[-/](\d{2,4})', texto_pdf)
                    if match_f:
                        d, m, y = match_f.groups()
                        if len(y) == 2: y = "20" + y
                        fecha_sorteo = f"{y}-{m}-{d} 21:00:00"

                    # Buscar POZO (Aquí está la clave)
                    # Busca: "POZO ESTIMADO..." seguido de números
                    match_pozo = re.search(r'POZO.*ESTIMADO.*\$?\s*([\d\.,]+)', texto_pdf, re.IGNORECASE)
                    if match_pozo:
                        pozo_proximo = match_pozo.group(1).strip()
                        
            except Exception as e:
                print(f"(Error PDF: {e})", end=" ")

        # 3. PREMIOS (Del HTML)
        dp = { "pozo5": "0", "gan5": 0, "vacante5": False, "pozo4": "0", "gan4": 0, "pozo3": "0", "gan3": 0, "pozo2": "0", "gan2": 0 }
        header = soup.find("h4", string=re.compile("Pozos Quiniela Poceada"))
        if header:
            filas = header.find_parent("div", class_="card").find_all("li", class_="results-list__item")
            def cln(t): return t.replace("\n", "").strip()
            # (Lógica resumida de premios igual que antes)
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

        # 4. GUARDAR
        obj = {
            "numeroSorteo": id_sorteo,
            "fecha": fecha_sorteo,
            "numerosGanadores": numeros,
            "pozo5aciertos": dp["pozo5"], "vacante5aciertos": dp["vacante5"],
            "ganadores4aciertos": dp["gan4"], "premio4aciertos": dp["pozo4"],
            "ganadores3aciertos": dp["gan3"], "premio3aciertos": dp["pozo3"],
            "ganadores2aciertos": dp["gan2"], "premio2aciertos": dp["pozo2"],
            "pozoEstimadoProximo": pozo_proximo, # <--- ESTE ES EL DATO QUE FALTABA
            "fechaProximo": "" 
        }
        
        # Insertamos al principio (para que el JSON quede ordenado del más nuevo al más viejo)
        lista_sorteos.insert(0, obj)
        print(f"✅ OK - Pozo Prox: ${pozo_proximo}")
        time.sleep(0.1)

    except Exception as e:
        print(f"❌ Error: {e}")

# Guardar archivo final
with open('datos_poceada.json', 'w', encoding='utf-8') as f:
    json.dump(lista_sorteos, f, indent=4, ensure_ascii=False)

print(f"\n✨ PROCESO TERMINADO: {len(lista_sorteos)} sorteos actualizados.")