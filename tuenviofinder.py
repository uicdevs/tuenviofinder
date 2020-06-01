#!/usr/bin/python3
import datetime
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sqlite3, pickle
from collections import Counter

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
# Python wrapper imports
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, JobQueue

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

URL_BASE_TUENVIO = 'https://www.tuenvio.cu'

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/81.0.4044.122 Chrome/81.0.4044.122 Safari/537.36' }

RESULTADOS, PRODUCTOS, USER, TIENDAS_COMANDOS, SUBSCRIPCIONES, DEPARTAMENTOS, CACHE, CACHE2 = {}, {}, {}, {}, {}, {}, {}, {}

BOTONES = {
    'INICIO': '🚀 Inicio',
    'AYUDA': '❓ Ayuda',
    'PROVINCIAS': '🌆 Provincias',
    'CATEGORIAS': '🔰 Categorías',
    'INFO': '👤 Info',
    'SUBS': '⚓️ Subs'
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

TEXTO_AYUDA = f'<b>¡Bienvenido a la {BOTONES["AYUDA"]}!</b>\n\nEl bot cuenta con varias opciones para su manejo, siéntase libre de consultar esta \
Ayuda siempre que lo considere necesario. \n\n<b>{BOTONES["INICIO"]}</b>: Reinicia el bot a sus opciones por defecto.\n\n<b>{BOTONES["INFO"]}</b>: \
Muestra sus opciones de configuración actuales.\n\n{BOTONES["PROVINCIAS"]}</b>: Muestra un menú con las provincias para seleccionar \
aquella donde se realizarán las búsquedas.\n\n<b>{BOTONES["CATEGORIAS"]}</b>: Muestra las categorías disponibles en una tienda, que debe\
 haber seleccionado previamente.\n\n<b>{BOTONES["SUBS"]}</b>: Muestra las opciones de subscripción disponibles.\n\n 💥 <b>¡Comandos avanzados! 💥</b>\n\nSi siente pasión por los comandos \
 le tenemos buenas noticias. Acceda a todos ellos directamente enviando la orden correspondiente seguida del caracter "/" \
 <b>Por ejemplo:</b> /lh cambia la provincia de búsqueda a 🦁 <b>La Habana</b>. Otros comandos disponibles son /prov, /cat, /dep, /sub, /start y /ayuda.\n\n\
 Los comandos de selección manual de provincia son:\n/pr, /ar, /my, /lh, /mt, /cf, /ss, /ca, /cm, /lt, /hl, /gr, /sc, /gt, /ij.'


# Tiempo en segundos que una palabra de búsqueda permanece válida
TTL = 900

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

def obtener_nombre_tienda(tid):
    for prov in PROVINCIAS:
        if tid in PROVINCIAS[prov][1]:
            return PROVINCIAS[prov][1][tid]
    return tid


def obtener_departamentos():
    deps = []
    for tienda in DEPARTAMENTOS:
        for cat in DEPARTAMENTOS[tienda]:
            for dep in DEPARTAMENTOS[tienda][cat]:
                if not dep in deps:
                    deps.append(dep)
    return deps


def mensaje_seleccion_provincia(prov):
    provincia = PROVINCIAS[prov][0]
    logo = PROVINCIAS[prov][2]
    texto_respuesta = f'Ha seleccionado: {logo} <b>{provincia}</b>. Tiendas disponibles:\n\n'
    for tid, tienda in obtener_tiendas(prov):
        tid_no_dashs = tid.replace('-', '_')
        texto_respuesta += f'🏬 <b>{tienda}</b>. /ver_categorias_{tid_no_dashs}\n\n'
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
        [ BOTONES['PROVINCIAS'], BOTONES['CATEGORIAS'], BOTONES['SUBS'] ],
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
    query = update.callback_query
    idchat = update.effective_chat.id
    if query.data == 'cat_atras':
        generar_teclado_categorias(update, context)
        context.bot.answerCallbackQuery(query.id)
    elif query.data in PROVINCIAS:
        try:
            prov = query.data
            provincia = PROVINCIAS[prov][0]
            if idchat in USER:
                USER[idchat]['prov'] = prov
            else:
                USER[idchat] = { 'prov': prov }
            if 'tienda' in USER[idchat]:
                del USER[idchat]['tienda']
            if 'cat' in USER[idchat]:
                del USER[idchat]['cat']
            if 'dep' in USER[idchat]:
                del USER[idchat]['dep']
            texto_respuesta = mensaje_seleccion_provincia(prov)
            context.bot.edit_message_text(text=texto_respuesta,
                                          chat_id=query.message.chat_id,
                                          message_id=query.message.message_id,
                                          parse_mode='HTML')
        except Exception as ex:
            print('Ocurrió la excepción:', ex)
    # Cuando se selecciona una categoría o departamento
    elif 'tienda' in USER[idchat]:
        tienda = USER[idchat]['tienda']
        # Cuando se selecciona una categoría
        if query.data in DEPARTAMENTOS[tienda]:
            cat = query.data
            USER[idchat]['cat'] = cat         
            generar_teclado_departamentos(update, context)
        # Cuando se selecciona un departamento
        else:
            cat = USER[idchat]['cat']
            if query.data in DEPARTAMENTOS[tienda][cat]:
                USER[idchat]['dep'] = query.data
                buscar_productos(update, context, palabras=False, dep=True)
                context.bot.answerCallbackQuery(query.id)             
    else:
        context.bot.send_message(chat_id=idchat,
                     text='Debe seleccionar una tienda antes de acceder a esta función.')
    


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



def usuarios_registrados(update, context):
    try:
        result = {}
        for idchat in USER:
            if 'prov' in USER[idchat]:
                prov = USER[idchat]['prov']
                if prov in result:
                    result[prov] += 1
                else:
                    result[prov] = 1
        message = ''
        for prov in result:
            message += f'{prov}: {result[prov]}\n'
        if message:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=message)
    except Exception as ex:
        print('usuarios_registrados:', ex)

dispatcher.add_handler(CommandHandler('ur', usuarios_registrados))


# Generar el teclado con las categorías
def generar_teclado_categorias(update, context):
    botones = []
    idchat = update.effective_chat.id
    tienda = USER[idchat]['tienda']
    nombre_tienda = obtener_nombre_tienda(tienda)
    for cat in DEPARTAMENTOS[tienda]:
        botones.append(InlineKeyboardButton(cat, callback_data=cat))

    if botones:
        teclado = construir_menu( botones, n_cols=2 )
        reply_markup = InlineKeyboardMarkup(teclado)
        texto_respuesta = f'Categorías disponibles en 🏬 <b>{nombre_tienda}</b>'
        if 'cat_kb_message_id' in USER[idchat]:
            context.bot.edit_message_text(chat_id=update.effective_chat.id, 
                                 text=texto_respuesta,
                                 message_id=USER[idchat]['cat_kb_message_id'],                            
                                 reply_markup=reply_markup,
                                 parse_mode='HTML')
        else:
            message = context.bot.send_message(chat_id=idchat,
                                     text=texto_respuesta,
                                     reply_markup=reply_markup,
                                     parse_mode='HTML')
            # Se almacena el id del mensaje enviado para editarlo despues
            USER[idchat]['cat_kb_message_id'] =  message.message_id
    else:
        message = context.bot.send_message(chat_id=idchat,
                                 text=f'⛔️ No se encontraron categorías en <b>{nombre_tienda}</b>. <b>¿Quizás está offline?</b>',
                                 parse_mode='HTML')



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

    teclado = construir_menu( botones, n_cols=2)
    teclado.append( [InlineKeyboardButton('👈 Atrás', callback_data='cat_atras')] )

    reply_markup = InlineKeyboardMarkup(teclado)

    # Reemplazar el teclado
    context.bot.edit_message_text(chat_id=update.effective_chat.id, 
                             text='Seleccione un departamento para ver los productos disponibles.',
                             message_id=USER[update.effective_chat.id]['cat_kb_message_id'],                            
                             reply_markup=reply_markup)

def dep(update, context):
    generar_teclado_categorias(update, context)

dispatcher.add_handler(CommandHandler('dep', dep))


def tiene_subscripciones_activas(idchat):
    return idchat in USER and 'sub' in USER[idchat]


# Definicion del comando sub
def sub(update, context):
    idchat = update.effective_chat.id
    args = context.args
    texto_no_subscripciones = 'Usted no tiene ninguna subscripción activa. Para subscribirse utilice /sub provincia palabras'
    # Si se envia el comando con 1 argumento, si se trata de una provincia se muestran las
    # subscripciones por esta via a esa provincia, si no se muestran las subscripciones a
    # la palabra seleccionada. Si se llama sin argumentos se muestran todas.
    if len(args) == 0:
        if tiene_subscripciones_activas(idchat):
            mostrar_subscripciones_clave(update, context)
        else:
            context.bot.send_message(chat_id=idchat,
                                     text=texto_no_subscripciones)
    elif len(args) == 1:
        prov = args[0]
        if prov == 'elim':
            # Lo que desea es eliminar
            if tiene_subscripciones_activas(idchat):
                del USER[idchat]['sub']
                context.bot.send_message(chat_id=idchat,
                                         text="Se han eliminado correctamente sus opciones de subscripción, \
                                         si las tenía. Recuerde que siempre puede volver a subscribirse utilizando /sub provincia palabras.")
            else:
                context.bot.send_message(chat_id=idchat,
                                         text=texto_no_subscripciones)
        else:
            mostrar_subscripciones_clave(update, context, clave=prov) 
    else:
        prov = args[0]
        palabras = ' '.join(args[1:])
        if prov in PROVINCIAS:            
            if tiene_subscripciones_activas(idchat):
                # Si ya tiene subscripciones actualizar las palabras en la provincia seleccionada
                if prov in USER[idchat]['sub']:
                    USER[idchat]['sub'][prov].append(palabras)
                else:
                    USER[idchat]['sub'][prov] = [ palabras ]
            else:
                # Si no tenia subscripciones simplemente inicializar el diccionario
                USER[idchat]['sub'] = { prov: [ palabras ] }
            context.bot.send_message(chat_id=idchat,
                                     text=f'Ha actualizado correctamente sus opciones de subscripción. Envíe <b>/sub provincia</b> o <b>/sub palabras</b> para chequear sus subscripciones.',
                                     parse_mode='HTML')
        else:
            # Si no comienza con el identificador de provincia se asume que está buscando la subscripción
            mostrar_subscripciones_clave(update, context, clave=palabras)


dispatcher.add_handler(CommandHandler('sub', sub))


def usuario_subscrito_a_producto(idchat, tid, pid):
    if tid in SUBSCRIPCIONES:
        if pid in SUBSCRIPCIONES[tid]:
            return idchat in SUBSCRIPCIONES[tid][pid]
    return False

# 1: El usuario se registró con éxito
# 0: El usuario ya esta subscrito
def registrar_subscripcion(idchat, pid, prov_id):
    tiendas = obtener_tiendas(prov_id)
    for tid, tienda in tiendas:
        if usuario_subscrito_a_producto(idchat, tid, pid):
            return 0
        else:
            if tid in SUBSCRIPCIONES:
                if pid in SUBSCRIPCIONES[tid]:
                    SUBSCRIPCIONES[tid][pid][idchat] = 1
                else:
                    SUBSCRIPCIONES[tid][pid] = { idchat: 1 }
            else:
                SUBSCRIPCIONES[tid] = { pid: { idchat: 1 } }
    return 1


def sub_a(update, context):
    try:
        idchat = update.effective_chat.id
        pid = update.message.text.split('_')[-1]
        producto = PRODUCTOS[pid]['nombre']
        prov_id = USER[idchat]['prov']
        provincia = PROVINCIAS[prov_id][0]
        if registrar_subscripcion(idchat, pid, prov_id):
            context.bot.send_message(chat_id=idchat,
                                     text=f'⚠️ <b>¡Subscripción registrada con éxito!</b> ⚠️\n\n<b>Producto:</b> {producto}\n<b>Provincia:</b> {provincia}',
                                     parse_mode='HTML')
        else:
            context.bot.send_message(chat_id=idchat,
                                 text=f'¡Ya existe una subscripción para {producto} en {provincia}!')
    except Exception as e:
        print(e)


def eliminar_prod(update, context):
    try:
        idchat = update.effective_chat.id        
        pid = update.message.text.split('_')[-1]
        producto = PRODUCTOS[pid]['nombre']
        for tienda in SUBSCRIPCIONES:
            if pid in SUBSCRIPCIONES[tienda] and idchat in SUBSCRIPCIONES[tienda][pid]:
                del SUBSCRIPCIONES[tienda][pid][idchat]
                context.bot.send_message(chat_id=idchat,
                                         text=f'Ha eliminado su subscripción al producto <b>{producto}</b>.',
                                         parse_mode='HTML')
    except Exception as e:
        print('Ocurrió: ', e)        

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

def seleccionar_categorias_tienda(update, context):
    tienda = TIENDAS_COMANDOS[update.message.text.split('/')[1]]
    idchat = update.effective_chat.id
    USER[idchat]['tienda'] = tienda
    prov = USER[idchat]['prov']
    texto_respuesta = f'Espere mientras se obtienen las categorías para: 🏬 <b>{PROVINCIAS[prov][1][tienda]}</b>'    
    context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')
    parsear_menu_departamentos(idchat)
    generar_teclado_categorias(update, context)

for tienda in obtener_todas_las_tiendas():
    comando_tienda = f'ver_categorias_{tienda}'.replace('-', '_')
    TIENDAS_COMANDOS[comando_tienda] = tienda
    dispatcher.add_handler(CommandHandler(comando_tienda, seleccionar_categorias_tienda))


def mostrar_informacion_usuario(update, context):
    try:
        idchat = update.effective_chat.id
        prov = USER[idchat]['prov']
        nombre_provincia = PROVINCIAS[prov][0]
        tienda = USER[idchat]['tienda']
        nombre_tienda = PROVINCIAS[prov][1][tienda]
        cat = USER[idchat]['cat']
        dep = USER[idchat]['dep']
        texto_respuesta = f'📌📌 Información Seleccionada 📌📌\n\n🌆 <b>Provincia:</b> {nombre_provincia}\n🛒 <b>Tienda:</b> {nombre_tienda}\n🔰 <b>Categoría:</b> {cat}\n📦 <b>Departamento:</b> {dep}'
        context.bot.send_message(chat_id=idchat, 
                                 text=texto_respuesta, 
                                 parse_mode='HTML')
    except Exception as e:
        print(e)


def subscripciones_activas_producto(idchat):
    subs = []
    for tid in SUBSCRIPCIONES:
        tienda = obtener_nombre_tienda(tid)
        for pid in SUBSCRIPCIONES[tid]:
            if idchat in SUBSCRIPCIONES[tid][pid]:
                prod = PRODUCTOS[pid]['nombre']
                subs.append( f'📦 <b>{prod}</b> en <b>{tienda}</b> /eliminar_{pid}' )
    if subs:
        return '\n\n'.join(subs)
    return False


def subscripciones_activas_clave(idchat, clave=False):
    subs = []
    if tiene_subscripciones_activas(idchat):
        for prov, pal in USER[idchat]['sub'].items():
            nombre_provincia = PROVINCIAS[prov][0]
            palabras = ', '.join(pal)
            ad = f'{nombre_provincia} --> "{palabras}"'
            if clave:                
                if clave in PROVINCIAS and clave == prov:
                    subs.append(ad)
                elif clave in pal:
                    subs.append(ad)
            else:
                subs.append(ad)
    if subs:
        return '\n\n'.join(subs)
    return False


def mostrar_subscripciones(update, context):
    idchat = update.effective_chat.id
    subs_act = subscripciones_activas_producto(idchat)
    if subs_act:
        texto_respuesta = '⚠️ <b>Subscripciones a productos:</b> ⚠️\n\n' + subs_act
    else:
        texto_respuesta = 'Usted no tiene subscripciones a productos específicos.'

    context.bot.send_message(chat_id=idchat,
                             text=texto_respuesta, 
                             parse_mode='HTML')


def mostrar_subscripciones_clave(update, context, clave=False):
    idchat = update.effective_chat.id
    subs_act = subscripciones_activas_clave(idchat, clave)
    if subs_act:
        texto_respuesta = '⚠️ <b>Subscripciones a palabras clave:</b> ⚠️\n\n' + subs_act
    else:
        texto_respuesta = 'No se encontraron subscripciones con los criterios especificados.'

    context.bot.send_message(chat_id=idchat,
                             text=texto_respuesta, 
                             parse_mode='HTML')


def actualizar_soup(url, mensaje, ahora, tienda):
    try:
        respuesta = session.get(url, headers=HEADERS)
        data = respuesta.content.decode('utf8')
        soup = BeautifulSoup(data, 'html.parser')
        if mensaje not in RESULTADOS:
            RESULTADOS[mensaje] = { tienda: {'tiempo': ahora, 'soup': soup } }
        else:
            RESULTADOS[mensaje][tienda] = {'tiempo': ahora, 'soup': soup }
        return soup
    except Exception as e:        
        print('actualizar_soup:', e)


def obtener_mas_buscados(update, context):
    mb = {}
    for palabra in CACHE:
        total = 0
        for prov_id in CACHE[palabra]:
            total += CACHE[palabra][prov_id]
        mb[palabra] = total
    mb_ord = dict(Counter(mb).most_common(10))

    deps = obtener_departamentos()
    if not context.args:
        result = f'<b>Más buscados</b>\n'
        for palabra in CACHE:
            if not palabra in deps and palabra in mb_ord:
                result += f'\n<b>Palabra: {palabra}</b>\n'
                for prov_id in CACHE[palabra]:
                    nombre_provincia = PROVINCIAS[prov_id][0]
                    result += f'{nombre_provincia} --> {CACHE[palabra][prov_id]}\n'
        return result
    elif len(context.args) == 1:
        prov = context.args[0]
        if prov in PROVINCIAS:
            nombre_provincia = PROVINCIAS[prov][0]
            result = f'Más buscados en {nombre_provincia}\n\n'
            for palabra in CACHE:
                if not palabra in deps and palabra in mb_ord:
                    for prov_id in CACHE[palabra]:
                        if prov == prov_id:
                            result += f'{palabra} --> {CACHE[palabra][prov]}\n'
            return result
        else:
            return False


def mas_buscados(update, context):
    try:
        result = obtener_mas_buscados(update, context)
        if result:
            context.bot.send_message(chat_id=update.effective_chat.id, text=result, parse_mode='HTML')
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, 
                                     text='Debe especificar un código de provincia válido.')
    except Exception as ex:
        print('Más buscados:', ex)

dispatcher.add_handler(CommandHandler('mb', mas_buscados))  


# Realiza la búsqueda de la palabra clave en tuenvio.cu
# mensaje: lo que se va a buscar
# nombre: nombre de usuario para los logs
# idchat: el id de chat desde el que se invocó la búsqueda
# buscar_en_dpto: si esta búsqueda es general en un departamento
def obtener_soup(mensaje, nombre, idchat, buscar_en_dpto=False, tienda=False):
    try:
        cadena_busqueda = ''
        # Seleccionar provincia que tiene el usuario en sus ajustes
        prov = USER[idchat]['prov']

        # Actualizar estadisticas de busqueda
        if mensaje in CACHE:
            if prov in CACHE[mensaje]:
                CACHE[mensaje][prov] += 1
            else:
                CACHE[mensaje][prov] = 1
        else:
            CACHE[mensaje] = { prov: 1 }
        tiendas = {}
        if buscar_en_dpto:
            dep = USER[idchat]['dep']
            cadena_busqueda = f'Products?depPid={dep}'
            tiendas = { USER[idchat]['tienda']: '' }        
        else:
            cadena_busqueda = f'Search.aspx?keywords=%22{mensaje}%22&depPid=0'
            if tienda:
                tiendas = { tienda: '' }
            else:
                tiendas = PROVINCIAS[prov][1]
        # Arreglo con una tupla para cada tienda con sus valores
        result = []    

        # Se hace el procesamiento para cada tienda en cada provincia
        for tienda in tiendas:
            url_base = f'{URL_BASE_TUENVIO}/{tienda}'
            url = f'{url_base}/{cadena_busqueda}'
            respuesta, data, soup_str = '', '', ''
            ahora = datetime.datetime.now()
            ahora_str = f'{ahora.hour}:{ahora.minute}:{ahora.second}'

            # Si el resultado no se encuentra cacheado buscar y guardar
            if mensaje not in RESULTADOS or tienda not in RESULTADOS[mensaje]:
                debug_print(f'{ahora_str} Buscando: "{mensaje}" para {nombre}')
                soup_str = actualizar_soup(url, mensaje, ahora, tienda)
            # Si el resultado está cacheado
            elif tienda in RESULTADOS[mensaje]:
                delta = ahora - RESULTADOS[mensaje][tienda]['tiempo']
                # Si aún es válido se retorna lo que hay en cache
                if delta.total_seconds() <= TTL:
                    debug_print(f'{ahora_str} "{mensaje}" aún en cache, no se realiza la búsqueda.')
                    soup_str = RESULTADOS[mensaje][tienda]["soup"]
                # Si no es válido se actualiza la cache
                else:
                    debug_print(f'{ahora_str} Actualizando : "{mensaje}" para {nombre}')
                    soup_str = actualizar_soup(url, mensaje, ahora, tienda)
            result.append((soup_str, url_base, tienda))
        return result
    except Exception as e:
        print('obtener_soup:', e)


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
        productos.append( (producto, precio, plink, pid) )
    return productos


# Obtiene las categorias y departamentos de la tienda actual
def parsear_menu_departamentos(idchat):
    tienda = USER[idchat]['tienda']
    respuesta = session.get(f'{URL_BASE_TUENVIO}/{tienda}', headers=HEADERS)
    data = respuesta.content.decode('utf8')
    soup = BeautifulSoup(data, 'html.parser')
    ahora = datetime.datetime.now()

    # Si no se le ha generado menu a la tienda o el que existe aun es valido
    if not tienda in DEPARTAMENTOS or (ahora - CACHE2[tienda]['menu_cat']).total_seconds() > TTL:  
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
        # TODO: Inicializar esta cache al inicio
        if not tienda in CACHE2:
            CACHE2[tienda] = {}
        CACHE2[tienda]['menu_cat'] = datetime.datetime.now()



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
        p_list = []
        for soup, url_base, tienda in results:
            prov = USER[idchat]['prov']
            nombre_provincia = PROVINCIAS[prov][0]
            nombre_tienda = PROVINCIAS[prov][1][tienda]
            if dep:
                texto_respuesta += f'<b>Resultados en: 🏬 {nombre_tienda}</b>\n\n<b>Departamento:</b> {DEPARTAMENTOS[tienda][cat][dep]}\n\n'
            else:
                texto_respuesta += f'<b>Resultados en: 🏬 {nombre_tienda}</b>\n\n'
            productos = parsear_productos(soup, url_base)
            if productos:
                p_list.append(productos)             
                for producto, precio, plink, pid in productos:
                    if pid not in PRODUCTOS:
                        PRODUCTOS[pid] = { 'nombre': producto, 'precio': precio, 'link': plink }
                    dispatcher.add_handler( CommandHandler(f'subscribirse_a_{pid}', sub_a), 1)             
                    dispatcher.add_handler( CommandHandler(f'eliminar_{pid}', eliminar_prod), 1)             
                    texto_respuesta += f'📦{producto} --> {precio} <a href="{plink}">ver producto</a> o /subscribirse_a_{pid}\n'
            texto_respuesta += "\n"
        if p_list:
            texto_respuesta = f'🎉🎉🎉¡¡¡Encontrado!!! 🎉🎉🎉\n\n{texto_respuesta}'
        else:
            if dep:
                texto_respuesta = 'No hay productos en el departamento seleccionado ... 😭'
            else:
                texto_respuesta = 'No hay productos que contengan la palabra buscada ... 😭'
    except Exception as inst:
        texto_respuesta = f'Ocurrió la siguiente excepción: {str(inst)}'

    context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')


# No procesar comandos incorrectos
def desconocido(update, context):
    text = update.message.text
    if not text.startswith('/subscribirse_a_') and not text.startswith('/eliminar'):
        texto_respuesta = 'Lo sentimos, \"' + text + '\" no es un comando.'
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
    elif palabra == BOTONES['SUBS']:
        mostrar_subscripciones(update, context)
    elif palabra == BOTONES['CATEGORIAS']:
        if not 'tienda' in USER[idchat]:
            context.bot.send_message(chat_id=idchat, 
                                     text='Debe seleccionar una tienda antes de consultar las categorías.')
        else:
            parsear_menu_departamentos(idchat)
            generar_teclado_categorias(update, context)
    else:
        if idchat in USER:
            buscar_productos(update, context)
        else:
            context.bot.send_message(chat_id=idchat, 
                                     text=f'Debe seleccionar una provincia antes de intentar realizar una búsqueda. Utilice el botón {BOTONES["INICIO"]} del teclado o el comando /prov')


dispatcher.add_handler(MessageHandler(Filters.text, procesar_palabra))


updater.start_polling(allowed_updates=[])



# Sección de trabajos cronometrados

# Busca en la pagina de detalles del producto y retorna su informacion
# Si es vacio entonces ya no esta disponible
def parsear_detalles_producto(tid, pid):
    check_url = f'{URL_BASE_TUENVIO}/{tid}/Item?ProdPid={pid}'
    respuesta = session.get(check_url, headers=HEADERS)    
    data = respuesta.content.decode('utf8')
    soup = BeautifulSoup(data, 'html.parser')
    return soup.select('.product-details')


def notificar_usuario(context, idchat, tid, pid, encontrado):
    nombre_tienda = obtener_nombre_tienda(tid)
    nombre_producto = PRODUCTOS[pid]['nombre']
    if encontrado:
        context.bot.send_message(chat_id=idchat, 
                                 text=f'¡Alerta: hay <b>{nombre_producto}</b> en <b>{nombre_tienda}</b>!',
                                 parse_mode='HTML')
    else:
        context.bot.send_message(chat_id=idchat, 
                                 text=f'El producto <b>{nombre_producto}</b> ya no está disponible en <b>{nombre_tienda}</b>.',
                                 parse_mode='HTML')
    SUBSCRIPCIONES[tid][pid][idchat] = int(encontrado)


def notificar_subscritos_producto(context):
    # Para cada una de las tiendas que tienen subscripciones
    for tid in SUBSCRIPCIONES:
        nombre_tienda = obtener_nombre_tienda(tid)
        # Para cada producto que tenga subscripciones
        for pid in SUBSCRIPCIONES[tid]:
            # Si existe al menos una subscripcion
            if SUBSCRIPCIONES[tid][pid]:
                nombre_producto = PRODUCTOS[pid]['nombre']
                disponible = parsear_detalles_producto(tid, pid)
                # Para cada usuario que este subscrito a ese producto
                for idchat, notificado in SUBSCRIPCIONES[tid][pid].items():
                    # Si el producto está disponible
                    if disponible:                           
                        # Y el usuario no ha sido notificado
                        if not notificado:
                            # Notificarle y actualizar el valor
                            notificar_usuario(context, idchat, tid, pid, True)
                    # Si el producto no esta disponible...
                    else:
                        # Y el usuario fue notificado anteriormente actualizar el valor
                        if notificado:
                            notificar_usuario(context, idchat, tid, pid, False)    


# TODO: chequear que si notificó, no lo haga de nuevo
def notificar_subscritos_palabras_clave(context):
    for idchat in USER:
        if tiene_subscripciones_activas(idchat):
            for prov, pal in USER[idchat]['sub'].items():
                for tid, tienda in obtener_tiendas(prov):
                    encontradas = [] # lista de palabras encontradas a eliminar
                    for palabra in pal:
                        # Se utiliza como nombre de usuario para logs el propio idchat (2do arg)
                        soup = obtener_soup(palabra, idchat, idchat, tienda=tid)[0][0]
                        if len(soup.select('.hProductItems > li')):
                            context.bot.send_message(chat_id=idchat,
                                                     text=f'¡Alerta: hay productos con <b>{palabra}</b> en <b>{tienda}</b>!',
                                                     parse_mode='HTML')
                            encontradas.append(palabra)
                    # Eliminar las palabras que ya fueron encontradas
                    for p in encontradas:
                        USER[idchat]['sub'][prov].remove(p)
                        if not USER[idchat]['sub'][prov]:
                            del USER[idchat]['sub'][prov]


def chequear_subscripciones(context):    
    try:
        notificar_subscritos_producto(context)
        notificar_subscritos_palabras_clave(context)
    except RuntimeError:
        pass


job_queue = updater.job_queue
job_queue.run_repeating(chequear_subscripciones, TTL)