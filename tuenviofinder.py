#!/usr/bin/python3

# Importar librerias
import json
import requests
import subprocess
import datetime
from bs4 import BeautifulSoup

# Variables para el Token y la URL del chatbot
# Real Token
#TOKEN = ""
# Test token
TOKEN = ""
URL = "https://api.telegram.org/bot" + TOKEN + "/"

USER = {
    
}

PROVINCIAS = {
    'pr': ['pinar', 'Pinar del Río'],
    'ar': ['artemisa', 'Artemisa', ],
    'c3': ['carlos3', 'Carlos Tercero'],
    '4c': ['4caminos', 'Cuatro Caminos'],
    'my': ['mayabeque-tv', 'Mayabeque'],
    'mt': ['matanzas', 'Matanzas'],
    'cf': ['cienfuegos', 'Cienfuegos'],
    'vc': ['villaclara', 'Villa Clara'],
    'ss': ['sancti', 'Sancti Spíritus'],
    'ca': ['ciego', 'Ciego de Ávila'],
    'cm': ['camaguey', 'Camagüey'],
    'lt': ['tunas', 'Las Tunas'],
    'hg': ['holguin', 'Holguín'],    
    'gr': ['granma', 'Granma'],
    'st': ['santiago', 'Santiago de Cuba'],
    'gt': ['guantanamo', 'Guantánamo'],
    'ij': ['isla', 'La Isla'],
}

RESULTADOS = {
    
}

PRODUCTOS = {
    
}


# Tiempo en segundos que una palabra de búsqueda permanece válida
TTL = 300


def update(offset):
    # Llamar al metodo getUpdates del bot, utilizando un offset
    respuesta = requests.get(URL + "getUpdates" +
                             "?offset=" + str(offset) + "&timeout=" + str(100))

    # Decodificar la respuesta recibida a formato UTF8
    mensajes_js = respuesta.content.decode("utf8")

    # Convertir el string de JSON a un diccionario de Python
    mensajes_diccionario = json.loads(mensajes_js)

    # Devolver este diccionario
    return mensajes_diccionario


def info_mensaje(mensaje):

    # Comprobar el tipo de mensaje
    if "text" in mensaje["message"]:
        tipo = "texto"
    elif "sticker" in mensaje["message"]:
        tipo = "sticker"
    elif "animation" in mensaje["message"]:
        tipo = "animacion"  # Nota: los GIF cuentan como animaciones
    elif "photo" in mensaje["message"]:
        tipo = "foto"
    else:
        # Para no hacer mas largo este ejemplo, el resto de tipos entran
        # en la categoria "otro"
        tipo = "otro"

    # Recoger la info del mensaje (remitente, id del chat e id del mensaje)
    persona = mensaje["message"]["from"]["first_name"]
    id_chat = mensaje["message"]["chat"]["id"]
    id_update = mensaje["update_id"]

    # Devolver toda la informacion
    return tipo, id_chat, persona, id_update


def leer_mensaje(mensaje):

    # Extraer el texto, nombre de la persona e id del último mensaje recibido
    texto = mensaje["message"]["text"]

    # Devolver las dos id, el nombre y el texto del mensaje
    return texto


def enviar_mensaje(idchat, texto):
    # Llamar el metodo sendMessage del bot, passando el texto y la id del chat
    requests.get(URL + "sendMessage?text=" + texto + "&chat_id=" + str(idchat) + "&parse_mode=html")


def update_soup(url, mensaje, ahora, prov):
    respuesta = requests.get(url)
    data = respuesta.content.decode("utf8")
    soup = BeautifulSoup(data, 'html.parser')
    if mensaje not in RESULTADOS:
        RESULTADOS[mensaje] = dict()
    RESULTADOS[mensaje][prov] = {"tiempo": ahora, "soup": soup }
    return soup

def obtener_soup(mensaje, nombre, idchat):
    prov, prov_name = 'granma', 'Granma'
    if idchat in USER:
        prov = PROVINCIAS[USER[idchat]['prov']][0]
        prov_name = PROVINCIAS[USER[idchat]['prov']][1]
    url_base = "https://www.tuenvio.cu/" + prov
    url = url_base + "/Search.aspx?keywords=%22" + mensaje + "%22&depPid=0"    
    respuesta, data, soup = "", "", ""
    ahora = datetime.datetime.now()
    if mensaje not in RESULTADOS or prov not in RESULTADOS[mensaje]:
        print("Buscando: \"" + mensaje + "\" para " + nombre)
        soup = update_soup(url, mensaje, ahora, prov)        
    elif prov in RESULTADOS[mensaje]:       
        delta = ahora - RESULTADOS[mensaje][prov]["tiempo"]
        if delta.total_seconds() <= TTL:
            print("\"" + mensaje + "\"" + " aún en cache, no se realiza la búsqueda.")
            soup = RESULTADOS[mensaje][prov]["soup"]
        else:
            print("Actualizando : \"" + mensaje + "\" para " + nombre)
            soup = update_soup(url, mensaje, ahora, prov)
    return soup, url_base, prov_name

def procesar_comando(mensaje, idchat):
    texto_respuesta, salida = '', ''
    if mensaje.startswith("/start"):
        texto_respuesta = "Búsqueda de productos en tuenvio.cu. Envíe una o varias palabras y se le responderá la disponibilidad. También puede probar la /ayuda. Suerte!"          
        salida = "ha iniciado chat con el bot."
    elif mensaje.startswith("/ayuda"):
        texto_respuesta = "Envíe una palabra para buscar. O puede seleccionar una provincia:\n\n"
        for prov in PROVINCIAS:
            texto_respuesta += "/" + prov + ": " + PROVINCIAS[prov][1] + "\n"
        salida = "ha solicitado la ayuda."
    else:
        prov = mensaje.split('/')[1]
        if prov in PROVINCIAS:
            USER[idchat] = {'prov': prov}
            texto_respuesta = "Ha seleccionado la provincia: " + PROVINCIAS[prov][1] + "."     
            salida = "ha cambiado la provincia de búsqueda a " + PROVINCIAS[prov][1] + "."
        elif prov in PRODUCTOS:
            producto = PRODUCTOS[prov]['producto']
            texto_respuesta = "Consultando: " + producto + "\n\nClick para ver en: " + PRODUCTOS[prov]['link']    
            salida = "ha consultado el link del producto " + producto + "."
        else:
            texto_respuesta = "Ha seleccionado incorrectamente el comanndo de provincia. Por favor, utilice la /ayuda."   
            salida = "ha utilizado incorrectamente la ayuda."            
    return texto_respuesta, salida



# Variable para almacenar la ID del ultimo mensaje procesado
ultima_id = 0

while(True):
    mensajes_diccionario = update(ultima_id)
    for i in mensajes_diccionario["result"]:

        # Guardar la informacion del mensaje
        try:
            tipo, idchat, nombre, id_update = info_mensaje(i)
        except:
            tipo, idchat, nombre, id_update = "delete", "744256293", "Disnel 56", 1

        # Generar una respuesta dependiendo del tipo de mensaje
        if tipo == "texto":
            mensaje = leer_mensaje(i)
            texto_respuesta = ""   
            if mensaje.startswith("/"):
                texto_respuesta, salida = procesar_comando(mensaje, idchat)
                print(nombre + " " + salida)
            else:
                try:                    
                    soup, url, prov_name = obtener_soup(mensaje, nombre, idchat)
                    l = soup.select('div.thumbSetting')
                    #texto_respuesta += "[Buscando en: " + prov_name + "]\n\n"
                    for child in l:
                        producto = child.select('div.thumbTitle a')[0].contents[0]
                        phref = child.select('div.thumbTitle a')[0]['href']
                        pid = phref.split('&')[0].split('=')[1]
                        plink = url + "/" + phref
                        if pid not in PRODUCTOS:
                            PRODUCTOS[pid] = { 'producto': producto, 'link': plink }
                        precio = child.select('div.thumbPrice span')[0].contents[0]
                        texto_respuesta += producto + " --> " + precio + " /" + pid  + "\n"
                except Exception as inst:
                    texto_respuesta = "Ocurrió la siguiente excepción: " + str(inst)
        else:
            texto_respuesta = "Solo se admiten textos."
            
 
        # Si la ID del mensaje es mayor que el ultimo, se guarda la ID + 1
        if id_update > (ultima_id-1):
            ultima_id = id_update + 1
 
        # Enviar la respuesta
        if texto_respuesta:
            if texto_respuesta.startswith("Ocurrió"):
                enviar_mensaje("744256293", texto_respuesta)
            elif not texto_respuesta.startswith("Búsqueda") and not texto_respuesta.startswith("Ha seleccionado"):
                texto_respuesta = "🎉🎉🎉¡¡¡Encontrado!!! 🎉🎉🎉\n\n" + texto_respuesta + "\n\nNota: Algunos links de productos no funcionan debido a los ajustes del sitio tuenvio. Rogamos nos disculpen."
            enviar_mensaje(idchat, texto_respuesta)
        else:
            enviar_mensaje(idchat, "No hay productos que contengan la palabra buscada ... 😭")
 
    # Vaciar el diccionario
    mensajes_diccionario = []
