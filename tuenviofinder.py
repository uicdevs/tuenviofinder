#!/usr/bin/python3
import datetime
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sqlite3

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
# Python wrapper imports
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))

logger = logging.getLogger('tuenviofinder')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
fh = RotatingFileHandler(str(DIRECTORY / 'logs' / 'sync.log'), mode='a', maxBytes=5 * 1024 * 1024, backupCount=1)
fh.setFormatter(formatter)
logger.addHandler(fh)

env_path = DIRECTORY / '.env'
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv('TOKEN')
BD_FILE = os.getenv('BD_FILE')
URL = f'https://api.telegram.org/bot{TOKEN}/'

USER, RESULTADOS, PRODUCTOS = {}, {}, {}

BOTONES = {
    'INICIO': '🚀 Inicio',
    'AYUDA': '❓ Ayuda',
    'PROVINCIAS': '🌆 Provincias'
}

PROVINCIAS = {
    'pr': ['Pinar del Río', {'pinar': 'Pinar del Río'}, '🚬'],
    'ar': ['Artemisa', {'artemisa': 'Artemisa'}, '🏹'],
    'my': ['Mayabeque', {'mayabeque-tv': 'Mayabeque'}, '🌪'],
    'mt': ['Matanzas', {'matanzas': 'Matanzas'}, '🐊'],
    'cf': ['Cienfuegos', {'cienfuegos': 'Cienfuegos'}, '🐘'],
    'vc': ['Villa Clara', {'villaclara': 'Villa Clara'}, '🍊'],
    'ss': ['Sancti Spíritus', {'sancti': 'Sancti Spíritus'}, '🐔'],
    'ca': ['Ciego de Ávila', {'ciego': 'Ciego de Ávila'}, '🐯'],
    'cm': ['Camagüey', {'camaguey': 'Camagüey'}, '🐂'],
    'lt': ['Las Tunas', {'tunas': 'Las Tunas'}, '🌵'],
    'hg': ['Holguín', {'holguin': 'Holguín'}, '🐶'],
    'gr': ['Granma', {'granma': 'Granma'}, '🐴'],
    'sc': ['Santiago de Cuba', {'santiago': 'Santiago de Cuba'}, '🐝'],
    'gt': ['Guantánamo', {'guantanamo': 'Guantánamo'}, '🗿'],
    'ij': ['La Isla', {'isla': 'La Isla'}, '🏴‍☠️'],
    'lh': ['La Habana', {'carlos3': 'Carlos III', '4caminos': 'Cuatro Caminos', 'tvpedregal': 'Pedregal', 'caribehabana': 'Villa Diana'}, '🦁'],
}


# Tiempo en segundos que una palabra de búsqueda permanece válida
TTL = 600

session = requests.Session()


def inicializar_bd():
    conn = sqlite3.connect( 'BD_FILE' )
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM lineas")
    except sqlite3.OperationalError:
        debug_print("Error, base de datos inexistente")
        sys.exit(0)
    return (conn, c,)


def actualizar_soup(url, mensaje, ahora, tienda):
    respuesta = session.get(url)
    data = respuesta.content.decode('utf8')
    soup = BeautifulSoup(data, 'html.parser')
    if mensaje not in RESULTADOS:
        RESULTADOS[mensaje] = dict()
    RESULTADOS[mensaje][tienda] = {'tiempo': ahora, 'soup': soup}
    return soup


def obtener_soup(mensaje, nombre, idchat):
    # Arreglo con una tupla para cada tienda con sus valores
    result = []
    if idchat in USER:
        # Seleccionar provincia que tiene el usuario en sus ajustes
        prov = USER[idchat]['prov']

        # Se hace el procesamiento para cada tienda en cada provincia
        for tienda in PROVINCIAS[prov][1]:
            url_base = f'https://www.tuenvio.cu/{tienda}'
            url = f'{url_base}/Search.aspx?keywords=%22{mensaje}%22&depPid=0'
            respuesta, data, soup_str = '', '', ''
            ahora = datetime.datetime.now()

            # Si el resultado no se encuentra cacheado buscar y guardar
            if mensaje not in RESULTADOS or tienda not in RESULTADOS[mensaje]:
                debug_print(f'Buscando: "{mensaje}" para {nombre}')
                soup_str = actualizar_soup(url, mensaje, ahora, tienda)
            # Si el resultado está cacheado
            elif tienda in RESULTADOS[mensaje]:
                delta = ahora - RESULTADOS[mensaje][tienda]['tiempo']
                # Si aún es válido se retorna lo que hay en cache
                if delta.total_seconds() <= TTL:
                    debug_print(f'"{mensaje}" aún en cache, no se realiza la búsqueda.')
                    soup_str = RESULTADOS[mensaje][tienda]["soup"]
                # Si no es válido se actualiza la cache
                else:
                    debug_print(f'Actualizando : "{mensaje}" para {nombre}')
                    soup_str = actualizar_soup(url, mensaje, ahora, tienda)
            result.append((soup_str, url_base, tienda))
    return result


def debug_print(message):
    print(message)
    logger.debug(message)


# Retorna una lista con tuplas de id de tienda y su nombre
def obtener_tiendas(prov):
    tiendas = []
    for tid in PROVINCIAS[prov][1]:
        tiendas.append( (tid, PROVINCIAS[prov][1][tid]) )
    return tiendas

def mensaje_seleccion_provincia(prov):
    provincia = PROVINCIAS[prov][0]
    logo = PROVINCIAS[prov][2]
    texto_respuesta = f'Tiendas disponibles en: {logo} <b>{provincia}</b>:\n\n'
    for tid, tienda in obtener_tiendas(prov):
        # Descomentar cuando utilicemos busquedas en las tiendas
        #texto_respuesta += f'🏬 {tienda}. Buscar en /{tid}\n'
        texto_respuesta += f'🛒 {tienda}.\n\n'
    return texto_respuesta


# Inicializar todo

updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher


# Pequeña función para generar un menu para teclado
def construir_menu(buttons,
                   n_cols,
                   header_buttons=None,
                   footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu


# Definicion del comando /start
def start(update, context):
    iniciar_aplicacion(update, context)


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)


def iniciar_aplicacion(update, context):
    mensaje_bienvenida = 'Búsqueda de productos en tuenvio.cu. Envíe una o varias palabras y el bot se encargará de chequear el sitio por usted. Consulte la /ayuda para seleccionar su provincia. Suerte!'

    button_list = [
        [ BOTONES['INICIO'], BOTONES['AYUDA'] ],
        [ BOTONES['PROVINCIAS'] ],
    ]

    reply_markup = ReplyKeyboardMarkup(button_list, resize_keyboard=True)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=mensaje_bienvenida,
                             reply_markup=reply_markup)


# Definicion del comando /ayuda
def ayuda(update, context):
    texto_respuesta = 'Envíe los términos a buscar o seleccione una provincia:\n\n'
    for prov in PROVINCIAS:
        texto_respuesta += f'/{prov}: {PROVINCIAS[prov][0]}\n'

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=texto_respuesta)


dispatcher.add_handler(CommandHandler('ayuda', ayuda))


# Manejador del teclado inline de provincias
def teclado_provincias(update, context):
    query = update.callback_query
    prov = query.data
    provincia = PROVINCIAS[prov][0]
    USER[update.effective_chat.id] = {'prov': prov}
    texto_respuesta = mensaje_seleccion_provincia(prov)
    context.bot.edit_message_text(text=texto_respuesta,
                                  chat_id=query.message.chat_id,
                                  message_id=query.message.message_id,
                                  parse_mode='HTML')


dispatcher.add_handler(CallbackQueryHandler(teclado_provincias))


# Definicion del comando /prov
# Al pulsar /prov en el teclado se envía el nuevo teclado inline con las provincias
def prov(update, context):
    generar_teclado_provincias(update, context)


dispatcher.add_handler(CommandHandler('prov', prov))



def generar_teclado_provincias(update, context):
    botones_provincias = []
    for prov in PROVINCIAS:
        provincia = PROVINCIAS[prov][0]
        logo = PROVINCIAS[prov][2]
        botones_provincias.append(InlineKeyboardButton(f'{logo} {provincia}', callback_data=prov))

    teclado = construir_menu(botones_provincias, n_cols=3)

    reply_markup = InlineKeyboardMarkup(teclado)

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Seleccione una provincia',
                             reply_markup=reply_markup)



# Generar masivamente los comandos de selección de provincia
# TODO: Responder cuando se pasa como argumento el producto
def seleccionar_provincia(update, context):
    # Seleccionar el id de provincia sin "/"
    # Si no hay argumentos solo se cambia de provincia
    if not context.args:
        debug_print(f'no hubo argumentos')
        prov = update.message.text[1:]
        texto_respuesta = mensaje_seleccion_provincia(prov)
        USER[update.effective_chat.id] = {'prov': prov}
        context.bot.send_message(chat_id=update.effective_chat.id, text=texto_respuesta, parse_mode='HTML')
    else:
        debug_print(f'si hubo argumentos: {update.message.text}')
        prov = update.message.text.split()[0].split('/')[1]
        palabras = update.message.text.split()[1]
        USER[update.effective_chat.id] = {'prov': prov}
        buscar_productos(update, context, palabras)


for prov in PROVINCIAS:
    dispatcher.add_handler(CommandHandler(prov, seleccionar_provincia))


# Buscar los productos
def buscar_productos(update, context, palabras=False):
    if not palabras:
        palabras = update.message.text
    idchat = update.effective_chat.id
    nombre = update.effective_user.username

    texto_respuesta = ''
    if update.effective_chat.id in USER:
        answer = False
        try:
            for soup, url_base, tienda in obtener_soup(palabras, nombre, idchat):
                prov = USER[idchat]['prov']
                nombre_tienda = PROVINCIAS[prov][1][tienda]
                thumb_setting = soup.select('div.thumbSetting')
                texto_respuesta += f'<b>Resultados en: 🏬 {nombre_tienda}</b>\n\n'
                for child in thumb_setting:
                    answer = True
                    producto = child.select('div.thumbTitle a')[0].contents[0]
                    phref = child.select('div.thumbTitle a')[0]['href']
                    pid = phref.split('&')[0].split('=')[1]
                    plink = f'{url_base}/{phref}'
                    precio = child.select('div.thumbPrice span')[0].contents[0]
                    texto_respuesta += f'📦{producto} --> {precio} <a href="{plink}">[ver producto]</a>\n'
                texto_respuesta += "\n"
            
            if answer:
                texto_respuesta = f'🎉🎉🎉¡¡¡Encontrado!!! 🎉🎉🎉\n\n{texto_respuesta}'
            else:
                texto_respuesta = 'No hay productos que contengan la palabra buscada ... 😭'
        except Exception as inst:
            texto_respuesta = f'Ocurrió la siguiente excepción: {str(inst)}'
    else:
        texto_respuesta = f'Debe seleccionar antes su provincia: hágalo mediante el menú de /ayuda.'

    context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')



# Procesar mensajes de texto que no son comandos
def procesar_palabra(update, context):
    palabra = update.message.text    

    if palabra == BOTONES['PROVINCIAS']:
        generar_teclado_provincias(update, context)
    elif palabra == BOTONES['AYUDA']:
        ayuda(update, context)
    elif palabra == BOTONES['INICIO']:
        iniciar_aplicacion(update, context)
    else:
        buscar_productos(update, context)


dispatcher.add_handler(MessageHandler(Filters.text, procesar_palabra))


# No procesar comandos incorrectos
def desconocido(update, context):
    texto_respuesta = 'Lo sentimos, \"' + update.message.text + '\" no es un comando.'
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=texto_respuesta)


dispatcher.add_handler(MessageHandler(Filters.command, desconocido))

updater.start_polling(allowed_updates=[])
