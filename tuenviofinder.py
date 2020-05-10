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

RESULTADOS, PRODUCTOS, USER, TIENDAS_COMANDOS = {}, {}, {}, {}

BOTONES = {
    'INICIO': '🚀 Inicio',
    'AYUDA': '❓ Ayuda',
    'PROVINCIAS': '🌆 Provincias',
    'CATEGORIAS': '🔰 Categorías',
    'INFO': '👤 Info'
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

DEPARTAMENTOS = {
    'Alimentos y Bebidas': {
        '52': 'Bebidas y Jugos',
        '54': 'Aderezos, Aliños y Salsas',
        '46087': 'Leche',
        '46081': 'Alimentos Refrigerados',
        '62006': 'Productos en Conserva',
    },
    'Belleza': {
        '62001': 'Artículos Personales',
        '46077': 'Aseo Personal',
        '46080': 'Cuidado del Cabello',
        '100002': 'Detergentes y Jabones',        
    },
    'Electrónica': {
        '59': 'Electrodomésticos'
    },
    'Para el Hogar': {
        '46078': 'Limpieza del Hogar',
        '60001': 'Útiles'
    }
}

TEXTO_AYUDA = f'<b>¡Bienvenido a la {BOTONES["AYUDA"]}!</b>\n\nEl bot cuenta con varias opciones para su manejo, siéntase libre de consultar esta \
Ayuda siempre que lo considere necesario. \n\n<b>{BOTONES["INICIO"]}</b>: Reinicia el bot a sus opciones por defecto. \
Sí, las búsquedas se realizarán en 🐴 <b>Granma</b> 😉.\n\n<b>{BOTONES["PROVINCIAS"]}</b>: Muestra un menú con las provincias para seleccionar \
aquella donde se realizarán las búsquedas.\n\n<b>{BOTONES["CATEGORIAS"]}</b>: Muestra las categorías disponibles en una tienda, que debe\
 haber seleccionado previamente.\n\n 💥 <b>¡Comandos avanzados! 💥</b>\n\nSi siente pasión por los comandos \
 le tenemos buenas noticias. Acceda a todos ellos directamente enviando la orden correspondiente seguida del caracter "/" \
 <b>Por ejemplo:</b> /lh cambia la provincia de búsqueda a 🦁 <b>La Habana</b>. Otros comandos disponibles son /prov, /cat, /dep, /sub, /start y /ayuda.\n\n\
 Los comandos de selección manual de provincia son:\n/pr, /ar, /my, /lh, /mt, /cf, /ss, /ca, /cm, /lt, /hl, /gr, /sc, /gt, /ij.'


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
        tid_no_dashs = tid.replace('-', '_')
        texto_respuesta += f'🏬 {tienda}. /seleccionar_{tid_no_dashs}\n'
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

dispatcher.add_handler( CommandHandler('start', start) )


def iniciar_aplicacion(update, context):
    mensaje_bienvenida = 'Búsqueda de productos en tuenvio.cu. Envíe una o varias palabras\
 y el bot se encargará de chequear el sitio por usted. Consulte la /ayuda para obtener más información. Suerte!'

    idchat = update.effective_chat.id

    button_list = [
        [ BOTONES['INICIO'], BOTONES['AYUDA'], BOTONES['INFO'] ],
        [ BOTONES['PROVINCIAS'], BOTONES['CATEGORIAS'] ],
    ]

    # Valores por defecto
    USER[idchat] = {
        'prov': 'gr',
        'tienda': 'granma',
        'cat': 'Alimentos y Bebidas',
        'dep': '46081'
    }

    reply_markup = ReplyKeyboardMarkup(button_list, resize_keyboard=True)
    context.bot.send_message(chat_id=idchat,
                             text=mensaje_bienvenida,
                             reply_markup=reply_markup)


# Definicion del comando /ayuda
def ayuda(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=TEXTO_AYUDA,
                             parse_mode='HTML')


dispatcher.add_handler(CommandHandler('ayuda', ayuda))


# Manejador de los teclados inlines disponibles
def manejador_teclados_inline(update, context):
    try:
        query = update.callback_query
        idchat = update.effective_chat.id        
        cat = USER[idchat]['cat']
        if query.data in PROVINCIAS:
            prov = query.data
            provincia = PROVINCIAS[prov][0]
            USER[idchat]['prov'] = prov
            if 'tienda' in USER[idchat]:
                del USER[idchat]['tienda']
            texto_respuesta = mensaje_seleccion_provincia(prov)
            context.bot.edit_message_text(text=texto_respuesta,
                                          chat_id=query.message.chat_id,
                                          message_id=query.message.message_id,
                                          parse_mode='HTML')
        # Cuando se selecciona una categoría o departamento
        elif 'tienda' in USER[idchat]:
            tienda = USER[idchat]['tienda']
            # Cuando se selecciona una categoría
            if query.data in DEPARTAMENTOS[tienda]:
                cat = query.data
                USER[idchat]['cat'] = cat         
                generar_teclado_departamentos(update, context)
            # Cuando se selecciona un departamento
            elif query.data in DEPARTAMENTOS[tienda][cat]:
                USER[idchat]['dep'] = query.data
                buscar_productos(update, context, palabras=False, dep=True)
                context.bot.answerCallbackQuery(query.id)             
        else:
            context.bot.send_message(chat_id=idchat,
                         text='Debe seleccionar una tienda antes de acceder a esta función.')
    except Exception as ex:
        print(str(ex))


dispatcher.add_handler(CallbackQueryHandler(manejador_teclados_inline))


# Definicion del comando /prov
# Al enviar /prov se recibe el teclado inline con las provincias
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


# Definicion del comando /dptos
# Al enviar /dptos en el teclado se recibe el teclado inline con los departamentos
def dptos(update, context):
    generar_teclado_departamentos(update, context)


dispatcher.add_handler(CommandHandler('dptos', dptos))



# Generar el teclado con las categorías
def generar_teclado_categorias(update, context):
    botones = []
    idchat = update.effective_chat.id
    tienda = USER[idchat]['tienda']
    for cat in DEPARTAMENTOS[tienda]:
        botones.append(InlineKeyboardButton(cat, callback_data=cat))

    teclado = construir_menu( botones, n_cols=2 )

    reply_markup = InlineKeyboardMarkup(teclado)

    message = context.bot.send_message(chat_id=idchat,
                             text='Seleccione una categoría para ver los departamentos disponibles.',
                             reply_markup=reply_markup)
    # Se almacena el id del mensaje enviado para editarlo despues
    USER[idchat]['cat_kb_message_id'] =  message.message_id


def cat(update, context):
    parsear_menu_departamentos(update.effective_chat.id)
    generar_teclado_categorias(update, context)

dispatcher.add_handler(CommandHandler('cat', cat))


# Generar el teclado con los departamentos
def generar_teclado_departamentos(update, context):
    botones = []
    idchat = update.effective_chat.id
    categoria = USER[idchat]['cat']
    tienda = USER[idchat]['tienda']
    for d_id, d_nombre in DEPARTAMENTOS[tienda][categoria].items():
        botones.append(InlineKeyboardButton(d_nombre, callback_data=d_id))


    teclado = construir_menu( botones, n_cols=2 )

    reply_markup = InlineKeyboardMarkup(teclado)

    # Reemplazar el teclado
    context.bot.edit_message_text(chat_id=update.effective_chat.id, 
                             text='Seleccione un departamento para ver los productos disponibles.',
                             message_id=USER[update.effective_chat.id]['cat_kb_message_id'],                            
                             reply_markup=reply_markup)

def dep(update, context):
    generar_teclado_categorias(update, context)

dispatcher.add_handler(CommandHandler('dep', dep))


# Definicion del comando sub
def sub(update, context):
    idchat = update.effective_chat.id
    args = context.args
    if len(args) < 2:
        if 'sub' in USER[idchat]:
            del USER[idchat]['sub']
            context.bot.send_message(chat_id=idchat,
                                 text="Se ha eliminado correctamente su subscripción. Recuerde que siempre puede volver a subscribirse utilizando /sub provincia palabras")
        else:
            context.bot.send_message(chat_id=idchat,
                                 text="Usted no tiene una subscripción activa. Para subscribirse utilice /sub provincia palabras")
    else:
        prov = args[0]
        palabras = args[1:]
        USER[idchat]['sub'] = { prov: palabras }
        context.bot.send_message(chat_id=idchat,
                             text=f'Ha actualizado correctamente sus opciones de subscripción.')

dispatcher.add_handler(CommandHandler('sub', sub))


# Generar masivamente los comandos de selección de provincia
# TODO: Responder cuando se pasa como argumento el producto
def seleccionar_provincia(update, context):
    # Seleccionar el id de provincia sin "/"
    # Si no hay argumentos solo se cambia de provincia
    idchat = update.effective_chat.id
    if not context.args:
        prov = update.message.text.split('/')[1]
        texto_respuesta = mensaje_seleccion_provincia(prov)
        USER[idchat]['prov'] = prov
        context.bot.send_message(chat_id=update.effective_chat.id, text=texto_respuesta, parse_mode='HTML')
    else:
        prov = update.message.text.split()[0].split('/')[1]
        palabras = ''
        for pal in update.message.text.split()[1:]:
            palabras += f'{pal} '
        USER[idchat]['prov'] = prov
        buscar_productos(update, context, palabras)
    if 'tienda' in USER[idchat]:
        del USER[idchat]['tienda']


for prov in PROVINCIAS:
    dispatcher.add_handler(CommandHandler(prov, seleccionar_provincia))


def obtener_todas_las_tiendas():
    tiendas = []
    for prov in PROVINCIAS:
        for tienda in PROVINCIAS[prov][1]:
            tiendas.append(tienda)
    return tiendas

def seleccionar_tienda(update, context):
    tienda = TIENDAS_COMANDOS[update.message.text.split('/')[1]]
    idchat = update.effective_chat.id
    USER[idchat]['tienda'] = tienda
    prov = USER[idchat]['prov']
    texto_respuesta = f'Ha seleccionado la tienda: {PROVINCIAS[prov][1][tienda]}'
    context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')

for tienda in obtener_todas_las_tiendas():
    comando_tienda = f'seleccionar_{tienda}'.replace('-', '_')
    TIENDAS_COMANDOS[comando_tienda] = tienda
    dispatcher.add_handler(CommandHandler(comando_tienda, seleccionar_tienda))


def mostrar_informacion_usuario(update, context):
    try:
        idchat = update.effective_chat.id
        prov = USER[idchat]['prov']
        nombre_provincia = PROVINCIAS[prov][0]
        tienda = USER[idchat]['tienda']
        nombre_tienda = PROVINCIAS[prov][1][tienda]
        cat = USER[idchat]['cat']
        dep = USER[idchat]['dep']
        #nombre_departamento = DEPARTAMENTOS[tienda][cat][dep]
        print(DEPARTAMENTOS)
        texto_respuesta = f'📌📌 Información Seleccionada 📌📌\n\n🌆 <b>Provincia:</b> {nombre_provincia}\n🛒 <b>Tienda:</b> {nombre_tienda}\n🔰 <b>Categoría:</b> {cat}\n📦 <b>Departamento:</b> {dep}'
        context.bot.send_message(chat_id=idchat, 
                                 text=texto_respuesta, 
                                 parse_mode='HTML')
    except Exception as e:
        print(e)


def actualizar_soup(url, mensaje, ahora, tienda):
    respuesta = session.get(url)
    data = respuesta.content.decode('utf8')
    soup = BeautifulSoup(data, 'html.parser')
    if mensaje not in RESULTADOS:
        RESULTADOS[mensaje] = dict()
    RESULTADOS[mensaje][tienda] = {'tiempo': ahora, 'soup': soup}
    return soup


def obtener_soup(mensaje, nombre, idchat, buscar_en_dpto=False):    
    cadena_busqueda = ''
    # Seleccionar provincia que tiene el usuario en sus ajustes
    prov = USER[idchat]['prov']
    tiendas = {}
    if buscar_en_dpto:
        dep = USER[idchat]['dep']
        cadena_busqueda = f'Products?depPid={dep}'
        tiendas = { USER[idchat]['tienda']: 'xxx' }
    else:
        cadena_busqueda = f'Search.aspx?keywords=%22{mensaje}%22&depPid=0'
        tiendas = PROVINCIAS[prov][1]
    # Arreglo con una tupla para cada tienda con sus valores
    result = []    

    # Se hace el procesamiento para cada tienda en cada provincia
    for tienda in tiendas:
        url_base = f'https://www.tuenvio.cu/{tienda}'
        url = f'{url_base}/{cadena_busqueda}'
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


# Definir una funcion para cada tipo de elemento a parsear
def parsear_productos(soup, url_base):
    productos = []
    thumb_setting = soup.select('div.thumbSetting')             
    for child in thumb_setting:
        producto = child.select('div.thumbTitle a')[0].contents[0]
        phref = child.select('div.thumbTitle a')[0]['href']
        pid = phref.split('&')[0].split('=')[1]
        plink = f'{url_base}/{phref}'
        precio = child.select('div.thumbPrice span')[0].contents[0]
        productos.append( (producto, precio, plink) )
    return productos


# Obtiene las categorias y departamentos de la tienda actual
def parsear_menu_departamentos(idchat):
    tienda = USER[idchat]['tienda']
    respuesta = session.get(f'https://www.tuenvio.cu/{tienda}')    
    data = respuesta.content.decode('utf8')
    soup = BeautifulSoup(data, 'html.parser')

    if not tienda in DEPARTAMENTOS:            
        deps = {}
        navbar = soup.select('.mainNav .navbar .nav > li:not(:first-child)')
        for child in navbar:
            cat = child.select('a')[0].contents[0]
            deps[cat] = {}
            for d in child.select('div > ul > li'):
                d_id = d.select('a')[0]['href'].split('=')[1]
                d_nombre = d.select('a')[0].contents[0]
                deps[cat][d_id] = d_nombre
        DEPARTAMENTOS[tienda] = deps


def notificar_subscritos(update, context, prov, palabras, nombre_provincia):
    for uid in USER:
        if 'sub' in USER[uid]:
            if prov in USER[uid]['sub']:
                if palabras in USER[uid]['sub'][prov]:
                    context.bot.send_message(chat_id=uid,
                             text=f'Atención: Se encontró <b>{palabras}</b> en <b>{nombre_provincia}</b>.', 
                             parse_mode='HTML')

# Buscar los productos en la provincia seleccionada
def buscar_productos(update, context, palabras=False, dep=False):
    idchat = update.effective_chat.id
    nombre = update.effective_user.username
    if dep:
        dep = USER[idchat]['dep']
        cat = USER[idchat]['cat']

    texto_respuesta = ''
    try:
        if dep:
            results = obtener_soup(dep, nombre, idchat, True)
        else:
            if not palabras:
                palabras = update.message.text
            results = obtener_soup(palabras, nombre, idchat)
        for soup, url_base, tienda in results:
            prov = USER[idchat]['prov']
            nombre_provincia = PROVINCIAS[prov][0]
            nombre_tienda = PROVINCIAS[prov][1][tienda]
            if dep:
                texto_respuesta += f'<b>Resultados en: 🏬 {nombre_tienda}</b>\n\n<b>Departamento:</b> {DEPARTAMENTOS[tienda][cat][dep]}\n\n'
            else:
                texto_respuesta += f'<b>Resultados en: 🏬 {nombre_tienda}</b>\n\n'
            productos = parsear_productos(soup, url_base)               
            for producto, precio, plink in productos:                    
                texto_respuesta += f'📦{producto} --> {precio} <a href="{plink}">[ver producto]</a>\n'
            texto_respuesta += "\n"            
        if productos:
            texto_respuesta = f'🎉🎉🎉¡¡¡Encontrado!!! 🎉🎉🎉\n\n{texto_respuesta}'
            # Enviar notificaciones a los subscritos
            notificar_subscritos(update, context, prov, palabras, nombre_provincia)
        else:
            texto_respuesta = 'No hay productos que contengan la palabra buscada ... 😭'
    except Exception as inst:
        texto_respuesta = f'Ocurrió la siguiente excepción: {str(inst)}'

    context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')


# No procesar comandos incorrectos
def desconocido(update, context):
    texto_respuesta = 'Lo sentimos, \"' + update.message.text + '\" no es un comando.'
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=texto_respuesta)


dispatcher.add_handler(MessageHandler(Filters.command, desconocido))

# Procesar mensajes de texto que no son comandos
def procesar_palabra(update, context):
    palabra = update.message.text
    idchat = update.effective_chat.id

    if palabra == BOTONES['PROVINCIAS']:        
        generar_teclado_provincias(update, context)
    elif palabra == BOTONES['AYUDA']:
        ayuda(update, context)
    elif palabra == BOTONES['INICIO']:
        iniciar_aplicacion(update, context)
    elif palabra == BOTONES['INFO']:
        mostrar_informacion_usuario(update, context)
    elif palabra == BOTONES['CATEGORIAS']:
        if not 'tienda' in USER[idchat]:
            context.bot.send_message(chat_id=idchat, 
                                     text='Debe seleccionar una tienda antes de consultar las categorías.', 
                                     parse_mode='HTML')
        else:
            parsear_menu_departamentos(idchat)
            generar_teclado_categorias(update, context)
    else:
        buscar_productos(update, context)


dispatcher.add_handler(MessageHandler(Filters.text, procesar_palabra))


updater.start_polling(allowed_updates=[])
