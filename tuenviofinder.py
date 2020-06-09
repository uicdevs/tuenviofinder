#!/usr/bin/python3
import datetime, os, mysql.connector, sys, timeago
from pathlib import Path
from collections import Counter

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
# Python wrapper imports
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, JobQueue

DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))

env_path = DIRECTORY / '.env'
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv('TOKEN')
URL = f'https://api.telegram.org/bot{TOKEN}/'

# En caso de usar un proxy
REQUEST_KWARGS={
    'proxy_url': 'http://172.26.1.10:3128/',
}

SUPER_ADMINS = [
    744256293,
    728711697
]

URL_BASE_TUENVIO = 'https://www.tuenvio.cu'

HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/81.0.4044.122 Chrome/81.0.4044.122 Safari/537.36' }

RESPUESTA_PENDIENTE = {}

BOTONES = {
    'INICIO': '🚀 Inicio',
    'AYUDA': '❓ Ayuda',
    'PROVINCIAS': '🌆 Provincias',
    'CATEGORIAS': '🔰 Categorías',
    'INFO': '👤 Info',
    'SUBS': '⚓️ Subs',
    'MAS_BUSCADOS': '🔍 Más buscados',
    'PRODUCTOS': '📦 Productos',
    'ACERCA_DE': '🏷 Acerca de'
}

LOGOS = {
    'pr': '🚬',
    'ar': '🏹',
    'my': '🌪',
    'mt': '🐊',
    'cf': '🐘',
    'vc': '🍊',
    'ss': '🐔',
    'ca': '🐯',
    'cm': '🐂',
    'lt': '🌵',
    'hg': '🐶',
    'gr': '🐴',
    'sc': '🐝',
    'gt': '🗿',
    'ij': '🏴‍☠️',
    'lh': '🦁',
}

session = requests.Session()  

TEXTO_AYUDA = f'<b>¡Bienvenido a la {BOTONES["AYUDA"]}!</b>\n\nEl bot cuenta con varias opciones para su manejo, siéntase libre de consultar esta \
Ayuda siempre que lo considere necesario. \n\n<b>{BOTONES["INICIO"]}</b>: Reinicia el bot a sus opciones por defecto.\n\n<b>{BOTONES["INFO"]}</b>: \
Muestra sus opciones de configuración actuales.\n\n<b>{BOTONES["PROVINCIAS"]}</b>: Muestra un menú con las provincias para seleccionar \
aquella donde se realizarán las búsquedas.\n\n<b>{BOTONES["CATEGORIAS"]}</b>: Muestra las categorías disponibles en una tienda, que debe\
 haber seleccionado previamente.\n\n<b>{BOTONES["SUBS"]}</b>: Muestra las opciones de subscripción disponibles.\n\n 💥 <b>¡Comandos avanzados!\
  💥</b>\n\nSi siente pasión por los comandos le tenemos buenas noticias. Acceda a todos ellos directamente enviando la orden correspondiente seguida del caracter "/" \
 <b>Por ejemplo:</b> /lh cambia la provincia de búsqueda a 🦁 <b>La Habana</b>. Otros comandos disponibles son /prov, /cat, /sub, /start y /ayuda.\n\n\
 Los comandos de selección manual de provincia son:\n/pr, /ar, /my, /lh, /mt, /cf, /ss, /ca, /cm, /lt, /hl, /gr, /sc, /gt, /ij.'


def inicializar_bd():
    try:
        conn = mysql.connector.connect(user='root', password='admin', host='127.0.0.1',database='tuenviofinder')
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print('Usuario o contraseña incorrectos.')
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print('La base de datos no existe.')
        else:
            print(err)
    
    cursor = conn.cursor()
    return (conn, cursor)  


def obtener_ajuste_bot(clave):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT valor FROM ajustes_bot WHERE clave = %s''', (clave, ))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        debug_print(f'obtener_ajuste_bot: clave {clave} inexistente')
    return False


def debug_print(message, tipo='estado'):
    print(message)
    conn, cursor = inicializar_bd()
    fecha = datetime.datetime.now()
    cursor.execute('''INSERT INTO log(mensaje, fecha, tipo) VALUES(%s, %s, %s)''', (message, fecha, tipo))
    conn.commit()
    conn.close()


# Retorna una lista con tuplas de id de tienda y su nombre dada una provincia
def obtener_tiendas(prov):
    conn, cursor = inicializar_bd()
    tiendas = []
    cursor.execute('''SELECT tid, nombre FROM tienda WHERE prov_id=%s''', (prov, ))
    for (tid, nombre) in cursor:
        tiendas.append( (tid, nombre) )
    conn.close()
    return tiendas

def obtener_todas_las_tiendas():
    conn, cursor = inicializar_bd()
    tiendas = []
    cursor.execute('''SELECT tid FROM tienda''')
    for (tid, ) in cursor:
        tiendas.append(tid)
    conn.close()
    return tiendas   


def obtener_nombre_tienda(tid):
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT nombre FROM tienda WHERE tid=%s''', (tid, ))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        return False
    except Exception as ex:
         print('obtener_nombre_tienda', ex)


def obtener_nombre_provincia(prov_id):
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT nombre FROM provincia WHERE prov_id=%s''', (prov_id, ))
        result = cursor.fetchone()
        conn.close()
        return result[0]
    except:
         print('obtener_nombre_provincia', ex)


def obtener_logo_provincia(prov_id):    
    return LOGOS[prov_id]


def obtener_ids_provincias():
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT prov_id FROM provincia''')
    provincias = []
    for (prov_id) in cursor:
        provincias.append(prov_id)
    conn.close()
    return provincias


def obtener_nombre_logo_provincia(prov_id):
    return ( obtener_nombre_provincia(prov_id), obtener_logo_provincia(prov_id) )    


def obtener_ajustes_usuario(idchat):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT * FROM ajustes_usuario WHERE uid=%s''', (idchat, ))
    au = cursor.fetchone()
    conn.close()
    if au:
        return {
            'prov_id': au[1],
            'tid': au[2],
            'cid': au[3],
            'did': au[4],
            'cat_kb_message_id': au[5]
        }
    return False


def obtener_nombre_categoria(cid):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT nombre FROM categoria WHERE cid=%s''', (cid, ))
    result = cursor.fetchone()
    conn.close()
    return result[0]


def obtener_nombre_departamento(did):
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT nombre FROM departamento WHERE did=%s''', (did, ))
        result = cursor.fetchone()
        conn.close()
        return result[0]
    except:
         print('obtener_nombre_departamento', ex)


# Determina si el argumento pasado es un id de provincia
def es_id_de_provincia(prov_id):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT * FROM provincia WHERE prov_id=%s''', (prov_id, ))
    result = len(cursor.fetchall())
    conn.close()
    return result


def es_categoria(cat):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT * FROM categoria WHERE nombre=%s''', (cat, ))
    result = len(cursor.fetchall())
    conn.close()
    return result


def es_departamento(did):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT * FROM departamento WHERE did=%s''', (did, ))
    result = len(cursor.fetchall())
    conn.close()
    return result  


def obtener_departamentos():
    conn, cursor = inicializar_bd()
    cursor.execute('SELECT nombre FROM departamentos')
    deps = []
    for row in cursor.fetchall():
        deps.append(row[0])
    conn.close()
    return deps



def mensaje_seleccion_provincia(prov):
    try:
        provincia, logo = obtener_nombre_logo_provincia(prov)
        texto_respuesta = f'Ha seleccionado: {logo} <b>{provincia}</b>. Tiendas disponibles:\n\n'
        for tid, tienda in obtener_tiendas(prov):
            tid_no_dashs = tid.replace('-', '_')
            texto_respuesta += f'🏬 <b>{tienda}</b>. /ver_categorias_{tid_no_dashs}\n\n'
        return texto_respuesta
    except Exception as ex:
        print('mensaje_seleccion_provincia', ex)


def obtener_mensaje(clave):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT texto FROM mensaje WHERE mid=%s''', (clave, ))
    result = cursor.fetchone()
    conn.close()
    return result[0]     


# Inicializar todo
updater = Updater(TOKEN, use_context=True)
#updater = Updater(TOKEN, use_context=True, request_kwargs=REQUEST_KWARGS)
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


def resetear_ajustes_usuario(uid):
    conn, cursor = inicializar_bd()
    cursor.execute('''DELETE FROM ajustes_usuario WHERE uid=%s''', (uid, ))
    cursor.execute('''INSERT INTO ajustes_usuario(uid) values (%s)''', (uid, ))
    conn.commit()
    conn.close()


def iniciar_aplicacion(update, context):
    try:
        mensaje_bienvenida = obtener_mensaje('bienvenida')

        idchat = update.effective_chat.id

        registrar_usuario(update, context)
        resetear_ajustes_usuario(idchat)

        
        button_list = [
            [ BOTONES['INICIO'], BOTONES['AYUDA'], BOTONES['INFO'] ],
            [ BOTONES['PROVINCIAS'], BOTONES['CATEGORIAS'], BOTONES['SUBS'] ],
            [ BOTONES['MAS_BUSCADOS'], BOTONES['PRODUCTOS'], BOTONES['ACERCA_DE'] ]
        ]

        reply_markup = ReplyKeyboardMarkup(button_list, resize_keyboard=True)
        context.bot.send_message(chat_id=idchat,
                                 text=mensaje_bienvenida,
                                 reply_markup=reply_markup)
    except Exception as ex:
        print('iniciar_aplicacion:', ex)


# Definicion del comando /ayuda
def ayuda(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=TEXTO_AYUDA,
                             parse_mode='HTML')


dispatcher.add_handler(CommandHandler('ayuda', ayuda))


def ultimos_registros_bot(update, context):
    texto_respuesta = ''
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT lid, mensaje FROM log ORDER BY fecha DESC LIMIT 10''')
    for (lid, mensaje) in cursor:
        texto_respuesta += f'{lid}. 📜 {mensaje}\n'
    conn.close()
    if texto_respuesta:
        texto_respuesta = 'Últimos registros del log:\n\n' + texto_respuesta
        context.bot.send_message(chat_id=update.effective_chat.id,
                             text=texto_respuesta,
                             parse_mode='HTML')
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                             text='No se encontraron registros.',
                             parse_mode='HTML')


dispatcher.add_handler(CommandHandler('log', ultimos_registros_bot))


def credito_usuarios(update, context):
    try:
        idchat = update.effective_chat.id
        if idchat in SUPER_ADMINS:
            conn, cursor = inicializar_bd()
            cursor.execute('''SELECT uid, nombre, credito FROM usuario WHERE credito > 0 ORDER BY credito DESC LIMIT 10''')
            texto_respuesta = ''
            for (uid, nombre, credito) in cursor:
                cup = credito / 80
                texto_respuesta += f'{uid}. 👤{nombre} 💰{credito} = ${cup}\n'
            if texto_respuesta:
                texto_respuesta = '<b>Top 10 usuarios con crédito</b>\n\n' + texto_respuesta
                context.bot.send_message(chat_id=idchat,
                                         text=texto_respuesta,
                                         parse_mode='HTML')
            else:
                context.bot.send_message(chat_id=idchat,
                                         text='Nadie con crédito disponible.')
            conn.close()
    except Exception as ex:
        debug_print(f'credito_usuarios: {ex}', 'error')


dispatcher.add_handler(CommandHandler('credito', credito_usuarios))


def ultimas_subscripciones(update, context):
    texto_respuesta = ''
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT sid, criterio, nombre, frecuencia FROM subscripcion join usuario WHERE subscripcion.uid = usuario.uid  ORDER BY fecha DESC LIMIT 10''')
    for (sid, criterio, nombre, frecuencia) in cursor:
        texto_respuesta += f'{sid}. 📜{criterio} 👤{nombre} ⏰{frecuencia}\n'
    conn.close()
    if texto_respuesta:
        texto_respuesta = 'Últimas subscripciones:\n\n' + texto_respuesta
        context.bot.send_message(chat_id=update.effective_chat.id,
                             text=texto_respuesta,
                             parse_mode='HTML')
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                             text='No se encontraron subscripciones.',
                             parse_mode='HTML')


dispatcher.add_handler(CommandHandler('subs', ultimas_subscripciones))


def resetear_provincia_usuario(idchat, prov):
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''DELETE FROM ajustes_usuario WHERE uid=%s''', (idchat, ))
        cursor.execute('''INSERT INTO ajustes_usuario(uid, prov_id) values (%s, %s)''', (idchat, prov))
        conn.commit()
        conn.close()
    except Exception as ex:
        print('resetear_provincia_usuario', ex)


def actualizar_categoria_seleccionada(idchat, cat):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT cid FROM categoria WHERE nombre=%s''', (cat, ))
    cid = cursor.fetchone()[0]
    cursor.execute('''UPDATE ajustes_usuario SET cid=%s WHERE uid=%s''', (cid, idchat))
    conn.commit()
    conn.close()


def actualizar_departamento_seleccionado(idchat, dep):
    conn, cursor = inicializar_bd()
    cursor.execute('''UPDATE ajustes_usuario SET did=%s WHERE uid=%s''', (dep, idchat))
    conn.commit()
    conn.close()


def enviar_registro_escaneos_subscripciones(update, context, idchat):
    conn, cursor = inicializar_bd()
    cadena_busqueda = f'%búsqueda programada%{idchat}%'
    cursor.execute('''SELECT lid, mensaje, fecha FROM log WHERE mensaje LIKE %s ORDER BY fecha desc limit 10''', (cadena_busqueda, ))
    texto_respuesta = ''
    for (lid, mensaje, fecha) in cursor:
        desde = timeago.format(fecha, datetime.datetime.now(), 'es')
        texto_respuesta += f'{lid}. <i>{mensaje}</i> {desde}\n'
    if texto_respuesta:
        texto_respuesta = 'Registros de escaneos recientes:\n\n' + texto_respuesta
        context.bot.send_message(text=texto_respuesta,
                                 chat_id=idchat,
                                 parse_mode='HTML')
    else:
        context.bot.send_message(text='Aún no hay registros de escaneo de subscripciones.',
                                 chat_id=idchat,
                                 parse_mode='HTML')                
    conn.close()


def formatear_frecuencia(frecuencia):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT texto FROM frecuencia_escaneo WHERE frecuencia = %s''', (frecuencia, ))
    texto_frec = cursor.fetchone()[0]
    conn.close()
    return f'cada ⏰ {texto_frec}'


def enviar_subscripciones_procesadas(update, context):
    try:
        idchat = update.effective_chat.id
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT max(sid) as sid, criterio, prov_id, max(ultimo_escaneo) as ultimo \
                        FROM subscripcion where uid=%s group by criterio, prov_id \
                        order by ultimo desc limit 10''', (idchat, ))
        texto_respuesta = ''
        for (sid, criterio, prov_id, ultimo_esc) in cursor:
            texto_respuesta += f'{sid}. <i>{criterio}</i> [{prov_id}] /activar_{sid}\n'
        conn.close()
        if texto_respuesta:
            texto_respuesta = '<b>Historial de subscripciones procesadas:</b>\n\n' + texto_respuesta        
            context.bot.send_message(text=texto_respuesta,
                                     chat_id=idchat,
                                     parse_mode='HTML')
        else:        
            context.bot.send_message(text='No se encontraron subscripciones procesadas',
                                     chat_id=idchat,
                                     parse_mode='HTML')
    except Exception as ex:
        debug_print(f'enviar_subscripciones_procesadas: {ex}', 'error')


# Manejador de los teclados inlines disponibles
# TODO: Identificar cada query.data con un prefijo de la operación a realizar
def manejador_teclados_inline(update, context):
    try: 
        query = update.callback_query
        idchat = update.effective_chat.id
        if query.data == 'cat_atras':
            generar_teclado_categorias(update, context, nuevo=True)
        elif query.data.split(':')[0] == 'sub':
            opcion = query.data.split(':')[1]
            if opcion == 'nueva':
                context.bot.send_message(text='Ok, envíe a continuación el criterio de búsqueda (palabras) para su subscripción.',
                                              chat_id=query.message.chat_id,
                                              parse_mode='HTML')
                RESPUESTA_PENDIENTE[idchat] = 'sub:nueva'
            elif opcion == 'elim':
                eliminar_subscripciones_activas(idchat)
                context.bot.send_message(chat_id=idchat,
                                         text=f'Se han eliminado correctamente sus opciones de subscripción, \
                                         si las tenía. Recuerde que siempre puede volver a subscribirse utilizando <b>/sub provincia palabras</b>.',
                                         parse_mode='HTML')
            elif opcion == 'log':
                enviar_registro_escaneos_subscripciones(update, context, idchat)
            elif opcion == 'proc':
                enviar_subscripciones_procesadas(update, context)
            else:
                # Acción por defecto, es un ID de provincia con los demás datos para crear la subscripción
                prov_id, criterio, frec = opcion.split('<-->')
                if registrar_subscripcion(idchat, prov_id, criterio, int(frec)):
                    context.bot.send_message(chat_id=idchat,
                                             text=f'Ha actualizado correctamente sus opciones de subscripción. Envíe <b>/sub</b> para chequear sus subscripciones o <b>/sub elim</b> para eliminarlas. Las subscripciones activas serán eliminadas automáticamente luego de 24 horas.',
                                             parse_mode='HTML')
                else:
                    context.bot.send_message(chat_id=idchat,
                                             text=f'Ha alcanzado el número máximo de subscripciones posibles para este tipo de cuenta.',
                                             parse_mode='HTML')
        elif query.data.split(':')[0] == 'sub-prod':
            opcion = query.data.split(':')[1]
            prov_id, pid = opcion.split('<-->')
            nombre_producto = obtener_producto_segun_pid(pid)[1]
            if registrar_subscripcion(idchat, prov_id, nombre_producto, 1800):
                context.bot.send_message(chat_id=idchat,
                                         text=f'Ha actualizado correctamente sus opciones de subscripción. Envíe <b>/sub</b> para chequear sus subscripciones o <b>/sub elim</b> para eliminarlas. Las subscripciones activas serán eliminadas automáticamente luego de 24 horas.',
                                         parse_mode='HTML')
            else:
                context.bot.send_message(chat_id=idchat,
                                         text=f'Ha alcanzado el número máximo de subscripciones posibles para este tipo de cuenta.',
                                         parse_mode='HTML')
        elif query.data.split(':')[0] == 'mb':
            pal = query.data.split(':')[1]
            if obtener_credito_usuario(idchat) > 0:
                enviar_mensaje_productos_encontrados(update, context, palabras=pal)
            else:
                context.bot.send_message(chat_id=idchat, 
                                     text=f'🎩 Bot en mantenimiento. Gracias por su apoyo.')
        elif es_id_de_provincia(query.data):
            try:
                prov = query.data
                provincia = obtener_nombre_provincia(prov)
                resetear_provincia_usuario(idchat, prov)
                texto_respuesta = mensaje_seleccion_provincia(prov)
                context.bot.edit_message_text(text=texto_respuesta,
                                              chat_id=query.message.chat_id,
                                              message_id=query.message.message_id,
                                              parse_mode='HTML')
            except Exception as ex:
                print('manejador_teclados_inline (select provincia):', ex)
        # Cuando se selecciona una categoría o departamento
        elif es_categoria(query.data):
            actualizar_categoria_seleccionada(idchat, query.data)
            generar_teclado_departamentos(update, context)
            # Cuando se selecciona un departamento
        elif es_departamento(query.data):
            actualizar_departamento_seleccionado(idchat, query.data)
            enviar_mensaje_productos_encontrados(update, context, palabras=False, dep=True)        
        else:
            context.bot.send_message(chat_id=idchat,
                         text='Debe seleccionar una tienda antes de acceder a esta función.')
        context.bot.answerCallbackQuery(query.id)
    except Exception as ex:
        print('manejador_teclados_inline:', ex)


dispatcher.add_handler(CallbackQueryHandler(manejador_teclados_inline))


# Definicion del comando /prov
# Al enviar /prov se recibe el teclado inline con las provincias
def prov(update, context):
    generar_teclado_provincias(update, context)


dispatcher.add_handler(CommandHandler('prov', prov))


def generar_teclado_provincias(update, context):
    try:
        botones_provincias = []
        conn, cursor = inicializar_bd()
        cursor.execute('SELECT prov_id, nombre FROM provincia')
        for (prov_id, nombre) in cursor:
            logo = obtener_logo_provincia(prov_id)
            botones_provincias.append(InlineKeyboardButton(f'{logo} {nombre}', callback_data=prov_id))

        conn.close()

        teclado = construir_menu(botones_provincias, n_cols=3)

        reply_markup = InlineKeyboardMarkup(teclado)

        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Seleccione una provincia',
                                 reply_markup=reply_markup)
    except Exception as ex:
        print('generar_teclado_provincias:', ex)

# Definicion del comando /dptos
# Al enviar /dptos en el teclado se recibe el teclado inline con los departamentos
def dptos(update, context):
    generar_teclado_departamentos(update, context)

dispatcher.add_handler(CommandHandler('dptos', dptos))


# Generar el teclado con las categorías
def generar_teclado_categorias(update, context, nuevo=False):
    try:
        botones = []
        idchat = update.effective_chat.id
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT tid FROM ajustes_usuario WHERE uid=%s''', (idchat, ))
        result = cursor.fetchone()
        if result:
            tid = result[0]
            nombre_tienda = obtener_nombre_tienda(tid)
            cursor.execute('''SELECT nombre FROM tienda_categoria JOIN categoria WHERE tienda_categoria.cid=categoria.cid and tid=%s''', (tid,))
            for (cat, ) in cursor:
                botones.append(InlineKeyboardButton(cat, callback_data=cat))

            if botones:
                teclado = construir_menu( botones, n_cols=2 )
                reply_markup = InlineKeyboardMarkup(teclado)
                texto_respuesta = f'Categorías disponibles en 🏬 <b>{nombre_tienda}</b>'
                cursor.execute('''SELECT cat_kb_message_id FROM ajustes_usuario WHERE uid=%s''', (idchat, ))
                result = cursor.fetchone()[0]
                if result and not nuevo:
                    context.bot.edit_message_text(chat_id=idchat,
                                                  text=texto_respuesta,
                                                  message_id=result[0],                        
                                                  reply_markup=reply_markup,
                                                  parse_mode='HTML')
                else:
                    message = context.bot.send_message(chat_id=idchat,
                                                       text=texto_respuesta,
                                                       reply_markup=reply_markup,
                                                       parse_mode='HTML')
                    # Se almacena el id del mensaje enviado para editarlo despues
                    cursor.execute('''UPDATE ajustes_usuario SET cat_kb_message_id=%s WHERE uid=%s''', (message.message_id, idchat))
                    conn.commit()
            else:
                message = context.bot.send_message(chat_id=idchat,
                                         text=f'⛔️ No se encontraron categorías en <b>{nombre_tienda}</b>. <b>¿Quizás está offline?</b>',
                                         parse_mode='HTML')
        else:
            message = context.bot.send_message(chat_id=idchat,
                                         text=f'⛔️ Debe seleccionar una tienda antes de consultar las categorías.',
                                         parse_mode='HTML')
        conn.close()
    except Exception as ex:
        print('generar_teclado_categorias:', ex)



def cat(update, context):
    parsear_menu_departamentos(update.effective_chat.id)
    generar_teclado_categorias(update, context, nuevo=True)

dispatcher.add_handler(CommandHandler('cat', cat))


# Generar el teclado con los departamentos
def generar_teclado_departamentos(update, context):
    botones = []
    idchat = update.effective_chat.id
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT cid, tid FROM ajustes_usuario WHERE uid=%s''', (idchat, ))
    result = cursor.fetchone()
    cid = result[0]
    tid = result[1]
    cursor.execute('''SELECT did, nombre FROM departamento WHERE cid=%s''', (cid, ))

    texto_respuesta = 'Seleccione un departamento para ver los productos disponibles.'
    
    for (did, nombre) in cursor:
        botones.append(InlineKeyboardButton(nombre, callback_data=did))

    teclado = construir_menu( botones, n_cols=2)
    teclado.append( [InlineKeyboardButton('👈 Atrás', callback_data='cat_atras')] )

    reply_markup = InlineKeyboardMarkup(teclado)

    # Reemplazar el teclado
    cursor.execute('''SELECT cat_kb_message_id FROM ajustes_usuario WHERE uid=%s''', (idchat, ))
    result = cursor.fetchone()
    if result[0]:
        context.bot.edit_message_text(chat_id=idchat, 
                                 text=texto_respuesta,
                                 message_id=result[0],                            
                                 reply_markup=reply_markup)
    elif tid and cid:
        context.bot.send_message(chat_id=idchat, 
                                 text=texto_respuesta,
                                 reply_markup=reply_markup)
    else:
        context.bot.send_message(chat_id=idchat, 
                                 text='⛔️ Debe seleccionar una tienda y una categoría antes de mostrar los departamentos.')
    conn.close()



def generar_teclado_opciones_subscripcion(update, context):
    botones = [
        InlineKeyboardButton('🆕 Crear nueva', callback_data='sub:nueva'),     
        InlineKeyboardButton('🗑 Eliminar todas', callback_data='sub:elim'),
        InlineKeyboardButton('📠 Ver registro', callback_data='sub:log'),
        #InlineKeyboardButton('🕔 Procesadas', callback_data='sub:proc'),
    ]

    idchat = update.effective_chat.id
    subs_act = subscripciones_activas_con_formato(idchat)
    if subs_act:
        texto_respuesta = '⚠️ <b>Subscripciones activas:</b> ⚠️\n\n' + subs_act
    else:
        texto_respuesta = 'Usted no tiene subscripciones activas en este momento.'

    reply_markup = InlineKeyboardMarkup( construir_menu( botones, n_cols=2) )

    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text=texto_respuesta,
                             reply_markup=reply_markup,
                             parse_mode='HTML')



def subscripciones_activas(idchat):
    conn, cursor = inicializar_bd()
    subs = []
    cursor.execute('''SELECT criterio, fecha, prov_id, sid, frecuencia FROM subscripcion WHERE uid=%s and estado=%s''', (idchat, 'activa'))
    for (criterio, fecha, prov_id, sid, frecuencia) in cursor:
        subs.append( (criterio, fecha, prov_id, sid, frecuencia) )
    conn.close()
    return subs


def eliminar_subscripciones_activas(idchat):
    conn, cursor = inicializar_bd()
    cursor.execute('''DELETE FROM subscripcion WHERE uid=%s and estado=%s''', (idchat, 'activa'))
    conn.commit()
    conn.close()


# Definicion del comando sub
def sub(update, context):
    idchat = update.effective_chat.id
    args = context.args
    subs_act = subscripciones_activas(idchat)
    texto_no_subscripciones = 'Usted no tiene ninguna subscripción activa. Para subscribirse utilice /sub provincia palabras'
    # Si se envia el comando con 1 argumento, si se trata de una provincia se muestran las
    # subscripciones por esta via a esa provincia, si no se muestran las subscripciones a
    # la palabra seleccionada. Si se llama sin argumentos se muestran todas.
    if len(args) == 0:
        if subs_act:
            mostrar_subscripciones(update, context)
        else:
            context.bot.send_message(chat_id=idchat,
                                     text=texto_no_subscripciones)
    elif len(args) == 1:
        prov = args[0]
        if prov == 'elim':
            # Lo que desea es eliminar
            if subs_act:
                eliminar_subscripciones_activas(idchat)
                context.bot.send_message(chat_id=idchat,
                                         text="Se han eliminado correctamente sus opciones de subscripción, \
                                         si las tenía. Recuerde que siempre puede volver a subscribirse utilizando /sub provincia palabras.")
            else:
                context.bot.send_message(chat_id=idchat,
                                         text=texto_no_subscripciones)
    else:
        prov = args[0]
        palabras = ' '.join(args[1:])
        if es_id_de_provincia(prov):
            if registrar_subscripcion(idchat, prov, palabras, 1800):
                context.bot.send_message(chat_id=idchat,
                                         text=f'Ha actualizado correctamente sus opciones de subscripción. Envíe `/sub` para chequear sus subscripciones o `/sub elim` para eliminarlas. Las subscripciones activas serán eliminadas automáticamente luego de 24 horas.',
                                         parse_mode='HTML')
            else:
                context.bot.send_message(chat_id=idchat,
                                         text=f'Ha alcanzado el número máximo de subscripciones posibles para este tipo de cuenta.',
                                         parse_mode='HTML')
        else:
            # Si no comienza con el identificador de provincia se asume que está buscando la subscripción
            context.bot.send_message(chat_id=idchat,
                                     text=f'El primer argumento debe ser el código de la provincia, p.ej: `/sub lh pollo`',
                                     parse_mode='HTML')


dispatcher.add_handler(CommandHandler('sub', sub))


def eliminar_subscripcion_unica(update, context):
    try:
        conn, cursor = inicializar_bd()
        sid = update.message.text.split('_')[-1]
        cursor.execute('''DELETE FROM subscripcion WHERE sid=%s''', (sid, ))
        conn.commit()
        conn.close()
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'⚠️ ¡Subscripción eliminada correctamente! Envíe <b>/sub</b> para ver sus subscripciones activas.',
                                 parse_mode='HTML')
    except Exception as ex:
        print('eliminar_subscripcion_unica:', ex)



def cambiar_frecuencia_subscripcion(update, context):
    try:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Próximamente disponible.',
                                 parse_mode='HTML')
    except Exception as ex:
        print('cambiar_frecuencia_subscripcion:', ex)


# Retorna una lista con las subscripciones en un estado dado
def obtener_subscripciones_segun_estado(estado):
    try:
        conn, cursor = inicializar_bd()
        subscripciones = []
        cursor.execute('''SELECT sid FROM subscripcion WHERE estado=%s''', (estado, ))
        for (sid, ) in cursor:
            subscripciones.append(sid)
        conn.close()
        return subscripciones
    except Exception as ex:
        print('obtener_subscripciones_segun_estado:', ex)


def activar_subscripcion_procesada(update, context):
    sid = update.message.text.split('_')[-1]
    conn, cursor = inicializar_bd()
    cursor.execute('''UPDATE subscripcion SET estado=%s WHERE sid=%s''', ('activa', sid))
    context.bot.send_message(text='Subscripción activada con éxito. Pulse /sub para chequear sus subscripciones.',
                             chat_id=update.effective_chat.id)
    dispatcher.add_handler(CommandHandler(f'cambiar_frec_{sid}', cambiar_frecuencia_subscripcion), 1)
    dispatcher.add_handler(CommandHandler(f'eliminar_sub_{sid}', eliminar_subscripcion_unica), 1)
    conn.commit()
    conn.close() 


def cargar_comandos_subscripcion():
    try:        
        for sid in obtener_subscripciones_segun_estado('activa'):
            dispatcher.add_handler(CommandHandler(f'eliminar_sub_{sid}', eliminar_subscripcion_unica), 1)
            dispatcher.add_handler(CommandHandler(f'cambiar_frec_{sid}', cambiar_frecuencia_subscripcion), 1)
        for sid in obtener_subscripciones_segun_estado('procesada'):
            dispatcher.add_handler(CommandHandler(f'activar_{sid}', activar_subscripcion_procesada), 1)
    except Exception as ex:
        print('cargar_comandos_subscripcion:', ex)


cargar_comandos_subscripcion()


def es_admin(uid):
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT tipo FROM usuario WHERE uid=%s''', ('uid', ))
        result = cursor.fetchone()
        conn.close()
        if result:
            if result[0]:
                return result[0] == 'admin'
        return False
    except Exception as ex:
        print('es_admin:', ex)


def consultar_credito_usuario(update, context):
    try:
        idchat = update.effective_chat.id
        #es_admin(idchat)
        uid = update.message.text.split('_')[-1]
        credito = obtener_credito_usuario(uid)
        context.bot.send_message(chat_id=update.effective_chat.id, 
                                 text=f'El monto del usuario con id: <b>{uid}</b> es de <b>{credito} TEF</b>.',
                                 parse_mode='HTML')
    except Exception as ex:
        debug_print('consultar_credito_usuario', ex)


def cargar_comandos_credito():
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT uid FROM usuario''')
        for (uid, ) in cursor:
            dispatcher.add_handler(CommandHandler(f'credito_{uid}', consultar_credito_usuario), 1)
        conn.close()
    except Exception as ex:
        print('cargar_comandos_credito:', ex)

cargar_comandos_credito()



def desactivar_notificacion(uid, criterio, prov_id):
    conn, cursor = inicializar_bd()
    cursor.execute('''UPDATE subscripcion SET estado=%s WHERE uid=%s and criterio=%s and prov_id=%s''',
                     ('procesada', uid, criterio, prov_id))
    sid = cursor.lastrowid
    dispatcher.add_handler(CommandHandler(f'activar_{sid}', activar_subscripcion_procesada), 1)
    conn.commit()
    conn.close()


def obtener_credito_usuario(idchat):
    try:        
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT credito FROM usuario WHERE uid=%s''', (idchat, ))
        result = cursor.fetchone()
        conn.close()        
        if result:
            if result[0]:
                return result[0]
        return 0
    except Exception as ex:
        print('obtener_credito_usuario:', ex)


def registrar_subscripcion(idchat, prov_id, palabras, frec):
    try:
        subs_act = subscripciones_activas(idchat)
        if len(subs_act) < int(obtener_ajuste_bot('max_subscripciones_permitidas')) or obtener_credito_usuario(idchat) > 0:
            conn, cursor = inicializar_bd()
            ahora = datetime.datetime.now()
            cursor.execute('''INSERT INTO subscripcion(uid, criterio, fecha, prov_id, frecuencia, ultimo_escaneo) VALUES(%s, %s, %s, %s, %s, %s)''', 
                            (idchat, palabras, ahora, prov_id, frec, ahora))
            sid = cursor.lastrowid
            dispatcher.add_handler(CommandHandler(f'eliminar_sub_{sid}', eliminar_subscripcion_unica), 1)
            dispatcher.add_handler(CommandHandler(f'cambiar_frec_{sid}', cambiar_frecuencia_subscripcion), 1)            
            conn.commit()
            conn.close()
            return True
        else:
            return False
    except Exception as ex:
        print('registrar_subscripcion:', ex)



def generar_teclado_provincias_subscripcion(update, context, pid):
    try:
        botones_provincias = []
        conn, cursor = inicializar_bd()
        cursor.execute('SELECT prov_id, nombre FROM provincia')
        for (prov_id, nombre) in cursor:
            logo = obtener_logo_provincia(prov_id)
            botones_provincias.append(InlineKeyboardButton(f'{logo} {prov_id}', callback_data=f'sub-prod:{prov_id}<-->{pid}'))
        conn.close()



        reply_markup = InlineKeyboardMarkup( construir_menu(botones_provincias, n_cols=4) )

        nombre_producto = obtener_producto_segun_pid(pid)[1]
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f'Seleccione una provincia para subscribirse a {nombre_producto}',
                                 reply_markup=reply_markup)
    except Exception as ex:
        print('generar_teclado_provincias_subscripcion:', ex)      


def sub_a(update, context):
    try:
        pid = update.message.text.split('_')[-1]        
        generar_teclado_provincias_subscripcion(update, context, pid)
    except Exception as ex:
        print('sub_a:', ex)

       
def cargar_comandos_subscripcion_a_producto():
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT pid FROM producto''')
    for (pid, ) in cursor:
        dispatcher.add_handler(CommandHandler(f'subscribirse_a_{pid}', sub_a), 1)
    conn.close()    

cargar_comandos_subscripcion_a_producto()         
    

# Generar masivamente los comandos de selección de provincia
# TODO: Responder cuando se pasa como argumento el producto
def seleccionar_provincia(update, context):
    # Seleccionar el id de provincia sin "/"
    # Si no hay argumentos solo se cambia de provincia
    idchat = update.effective_chat.id
    if not context.args:
        prov = update.message.text.split('/')[1]
        texto_respuesta = mensaje_seleccion_provincia(prov)
        resetear_provincia_usuario(idchat, prov)
        context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')
    else:
        prov = update.message.text.split()[0].split('/')[1]
        palabras = ''
        for pal in update.message.text.split()[1:]:
            palabras += f'{pal} '
        resetear_provincia_usuario(idchat, prov)
        enviar_mensaje_productos_encontrados(update, context, palabras)


for prov in obtener_ids_provincias():
    dispatcher.add_handler(CommandHandler(prov, seleccionar_provincia))


def obtener_tienda_a_partir_de_comando(comando):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT tid FROM comandos_tienda WHERE comando=%s''', (comando, ))
    result = cursor.fetchone()
    conn.close()
    return result[0]  


def usuarios_vip():
    u_perm = []
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT uid FROM usuario WHERE tipo = %s''', ('vip', ))
    for (uid, ) in cursor:
        u_perm.append(uid)
    conn.close()
    return u_perm


def acreditar_usuario(update, context):
    idchat = update.effective_chat.id
    if idchat in SUPER_ADMINS:
        if len(context.args) != 2:
            context.bot.send_message(chat_id=idchat, text='Error, número incorrecto de parámetros')
        else:
            try:
                conn, cursor = inicializar_bd()
                uid = context.args[0]
                monto = context.args[1]
                ahora = datetime.datetime.now()
                cursor.execute('''UPDATE usuario SET credito = credito + %s WHERE uid=%s''', (monto, uid))
                cursor.execute('''INSERT INTO operacion_credito(uid, descripcion, tipo, monto, fecha) VALUES(%s, %s, %s, %s, %s)''',
                              (idchat, 'Recarga', 'crédito', monto, ahora))
                conn.commit()
                conn.close()
                context.bot.send_message(chat_id=idchat, 
                                         text=f'Monto acreditado correctamente, pulse /credito_{uid} para consultar el saldo del usuario acreditado.')
                # Notificar al usuario que recibe la acreditación
                context.bot.send_message(chat_id=uid, 
                                         text=f'Se han acreditado {monto} TEF a su cuenta de usuario. Consulte {BOTONES["INFO"]} para conocer su crédito.')
                debug_print(f'Acreditados {monto} TEF a la cuenta de usuario {uid}')
                dispatcher.add_handler(CommandHandler(f'credito_{uid}', consultar_credito_usuario), 1)
            except Exception as ex:
                debug_print(f'acreditar_usuario: {ex}', 'error')                      


dispatcher.add_handler(CommandHandler('acreditar', acreditar_usuario))


def solicitar_credito(update, context):
    try:
        idchat = update.effective_chat.id
        context.bot.send_message(chat_id=idchat, 
                                 text=f'Se ha enviado una solicitud de depósito de crédito, en breve será atendido.')
        for admin in SUPER_ADMINS:
            context.bot.send_message(chat_id=admin, 
                                     text=f'El usuario {idchat} ha solicitado un depósito de crédito.')
    except Exception as ex:
        debug_print(f'solicitar_credito: {ex}', 'error') 


dispatcher.add_handler(CommandHandler('solicitar_credito', solicitar_credito))


def seleccionar_categorias_tienda(update, context):
    idchat = update.effective_chat.id
    try:
        if obtener_credito_usuario(idchat):
            conn, cursor = inicializar_bd()
            comando = update.message.text.split('/')[1]
            tid = obtener_tienda_a_partir_de_comando(comando)        
            cursor.execute('''UPDATE ajustes_usuario SET tid=%s WHERE uid=%s''', (tid, idchat))
            conn.commit()
            nombre_tienda = obtener_nombre_tienda(tid)
            texto_respuesta = f'Espere mientras se obtienen las categorías para: 🏬 <b>{nombre_tienda}</b>'    
            context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')
            conn.close()
            parsear_menu_departamentos(idchat)
            generar_teclado_categorias(update, context, nuevo=True)
        else:
            context.bot.send_message(chat_id=idchat, 
                                     text=f'🎩 Bot en mantenimiento. Gracias por su apoyo.')
    except Exception as ex:
        print('seleccionar_categorias_tienda:', ex)
    


def actualizar_comandos_tienda(dispatcher):
    conn, cursor = inicializar_bd()
    for tid in obtener_todas_las_tiendas():
        comando = f'ver_categorias_{tid}'.replace('-', '_')
        cursor.execute('''SELECT * FROM comandos_tienda WHERE tid=%s''', (tid, ))
        result = cursor.fetchall()
        if not result:
            cursor.execute('''INSERT INTO comandos_tienda(tid, comando) VALUES(%s, %s)''', (tid, comando))
            conn.commit()  
        dispatcher.add_handler(CommandHandler(comando, seleccionar_categorias_tienda))
    cursor.close()

actualizar_comandos_tienda(dispatcher)


def mostrar_informacion_usuario(update, context):
    try:        
        idchat = update.effective_chat.id
        result = obtener_ajustes_usuario(idchat)
        credito = obtener_credito_usuario(idchat)
        if result:
            nombre_provincia = nombre_tienda = categoria = departamento = 'Sin selección'
            if result['prov_id']:
                nombre_provincia = obtener_nombre_provincia(result['prov_id'])
            if result['tid']:
                nombre_tienda = obtener_nombre_tienda(result['tid'])
            if result['cid']:
                categoria = obtener_nombre_categoria(result['cid'])
            if result['did']:
                departamento = obtener_nombre_departamento(result['did'])
            texto_respuesta = f'📌📌 Información Seleccionada 📌📌\n\n🌆 <b>Provincia:</b> {nombre_provincia}\n🛒 <b>Tienda:</b> {nombre_tienda}\n🔰 <b>Categoría:</b> {categoria}\n📦 <b>Departamento:</b> {departamento}\n💰 Crédito: {credito}'
            context.bot.send_message(chat_id=idchat, 
                                     text=texto_respuesta, 
                                     parse_mode='HTML')
        else:
            context.bot.send_message(chat_id=idchat, 
                                     text='Usted no tiene ajustes registrados aún.', 
                                     parse_mode='HTML')
    except Exception as ex:
        print('mostrar_informacion_usuario:', ex)



# Retorna las subscripciones activas listas para enviar en un mensaje
# (Se debe añadir la cabecera)
def subscripciones_activas_con_formato(idchat):
    subs = []
    i = 1
    for (criterio, fecha, prov_id, sid, frecuencia) in subscripciones_activas(idchat):
        nombre_provincia = obtener_nombre_provincia(prov_id)
        frec_formato = formatear_frecuencia(frecuencia)
        subs.append(f'<b>{i}.</b> 📜<b>{criterio}</b> en {nombre_provincia} {frec_formato} /eliminar_sub_{sid} o /cambiar_frec_{sid}')
        i = i + 1
    if subs:
        return '\n\n'.join(subs)
    return False


def mostrar_subscripciones(update, context):
    idchat = update.effective_chat.id
    subs_act = subscripciones_activas_con_formato(idchat)
    if subs_act:
        texto_respuesta = '⚠️ <b>Subscripciones activas:</b> ⚠️\n\n' + subs_act
    else:
        texto_respuesta = 'Usted no tiene subscripciones activas en este momento.'

    context.bot.send_message(chat_id=idchat,
                             text=texto_respuesta, 
                             parse_mode='HTML')


# Definir una funcion para cada tipo de elemento a parsear
def parsear_productos(soup, url_base):
    try:
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
    except Exception as ex:
        print('parsear_productos', ex)    


def registrar_producto(**kargs):
    try:
        nombre = kargs['nombre']    
        precio = kargs['precio']    
        enlace = kargs['enlace']    
        pid = kargs['pid']    
        did = kargs['did']

        conn, cursor = inicializar_bd() 
        cursor.execute('''SELECT pid FROM producto WHERE pid=%s''', (pid, ))
        result = cursor.fetchall()
        if not result:
            cursor.execute('''INSERT INTO producto(pid, nombre, precio, enlace, did) VALUES(%s, %s, %s, %s, %s)''',
                           (pid, nombre, precio, enlace, did))
            conn.commit()
        conn.close()
    except Exception as ex:
        print('registrar_producto:', ex)


def actualizar_resultados_busqueda(**kargs):
    try:
        # Extract args
        url = kargs['url']
        ahora = kargs['ahora']
        tid = kargs['tienda']
        mensaje = kargs['mensaje']
        idchat = kargs['idchat']
        did = kargs['did']

        respuesta = session.get(url, headers=HEADERS)
        data = respuesta.content.decode('utf8')
        soup = BeautifulSoup(data, 'html.parser')
        productos = parsear_productos(soup, url)
        conn, cursor = inicializar_bd()

        if did == '0':
            cursor.execute('''INSERT INTO busqueda(uid, criterio, fecha, tid) VALUES(%s, %s, %s, %s)''',
                            (idchat, mensaje, ahora, tid) )                
        else:
            cursor.execute('''INSERT INTO busqueda(uid, did, fecha, tid) VALUES(%s, %s, %s, %s)''',
                            (idchat, did, ahora, tid) )
        bid = cursor.lastrowid
        conn.commit()

        for nombre, precio, plink, pid in productos:
            # Solo lo adiciona a la base de datos si no existe
            registrar_producto(nombre=nombre, precio=precio, enlace=plink, pid=pid, did=did)
            cursor.execute('''INSERT INTO resultado(bid, pid) VALUES(%s, %s)''', (bid, pid) )
            conn.commit()

        conn.close()

        return bid
    except Exception as e:        
        print('actualizar_resultados_busqueda:', e)



def mas_buscados(update, context):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT criterio, count(uid) as total FROM busqueda where criterio is not null group by criterio order by total desc limit 12;''')
    
    botones = []
    for row in cursor:
        texto = row[0]
        total = row[1]
        botones.append( InlineKeyboardButton(f'{texto} ({total})', callback_data=f'mb:{texto}') )

    conn.close()

    reply_markup = InlineKeyboardMarkup(construir_menu(botones, n_cols=3))

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Los 12 términos más buscados. Haga clic en cualquiera de ellos y se buscará en la provincia que tiene seleccionada actualmente.',
                             reply_markup=reply_markup)


dispatcher.add_handler(CommandHandler('mb', mas_buscados))  


def enviar_foto(update, context):
    context.bot.send_photo(chat_id=update.effective_chat.id,
               photo='https://www.portalveterinaria.com/upload/thumbs/20200529101926vison.jpg',
               caption='Aquí enviando una foto de ejemplo')

dispatcher.add_handler(CommandHandler('sf', enviar_foto))    


def obtener_resultados_busqueda_en_bd(idchat, mensaje, tienda, did):
    conn, cursor = inicializar_bd()
    if did == '0':
        cursor.execute('''SELECT bid, fecha FROM busqueda WHERE uid=%s and criterio=%s \
                          and tid=%s ORDER BY fecha DESC LIMIT 1''', (idchat, mensaje, tienda))
    else:
        cursor.execute('''SELECT bid, fecha FROM busqueda WHERE uid=%s and did=%s \
                          and tid=%s ORDER BY fecha DESC LIMIT 1''', (idchat, did, tienda))
    res_busqueda = cursor.fetchone()
    conn.close()
    if res_busqueda:
        return {
            'bid': res_busqueda[0],
            'fecha': res_busqueda[1]
        }
    return False


# Realiza la búsqueda de la palabra clave en tuenvio.cu
# mensaje: lo que se va a buscar
# nombre: nombre de usuario para los logs
# idchat: el id de chat desde el que se invocó la búsqueda
# buscar_en_dpto: si esta búsqueda es general en un departamento
# TODO: definir correctamente el nombre para esta funcion
def obtener_soup(mensaje, nombre, idchat, buscar_en_dpto=False, tienda=False):
    try:        
        # Seleccionar provincia que tiene el usuario en sus ajustes  
        prov_id = obtener_ajustes_usuario(idchat)['prov_id']
        tiendas = []
        if buscar_en_dpto:
            did = obtener_ajustes_usuario(idchat)['did']
            cadena_busqueda = f'Products?depPid={did}'
            tiendas = [ obtener_ajustes_usuario(idchat)['tid'] ]
        else:
            did = '0'
            cadena_busqueda = f'Search.aspx?keywords=%22{mensaje}%22&depPid=0'
            if tienda:
                tiendas = [ tienda ]
            else:
                for tid, nombre_tienda in obtener_tiendas(prov_id):
                    tiendas.append( tid )

        # Se hace el procesamiento para cada tienda en cada provincia
        # si se trata de un criterio de busqueda
        bid_results = []
        for tienda in tiendas:            
            ahora = datetime.datetime.now()
            
            res_busqueda = obtener_resultados_busqueda_en_bd(idchat, mensaje, tienda, did)

            se_debe_actualizar = False
            # Si el resultado no se encuentra cacheado buscar y guardar
            if not res_busqueda:
                debug_print(f'Buscando: "{mensaje}" para {nombre} en {tienda}')
                se_debe_actualizar = True            
            # Si el resultado está cacheado
            else:
                delta = ahora - res_busqueda['fecha']
                # Si aún es válido se retorna lo que hay en cache
                if delta.total_seconds() <= int( obtener_ajuste_bot('intervalo_busqueda') ):
                    if buscar_en_dpto:
                        debug_print(f'Término aún en la cache, no se realiza la búsqueda.')
                    else:
                        debug_print(f'"{mensaje}" aún en la cache, no se realiza la búsqueda.')
                # Si no es válido se actualiza la cache
                else:
                    debug_print(f'Actualizando: "{mensaje}" para {nombre} en {tienda}')
                    se_debe_actualizar = True

            if se_debe_actualizar:
                url_base = f'{URL_BASE_TUENVIO}/{tienda}'
                url = f'{url_base}/{cadena_busqueda}'
                bid = actualizar_resultados_busqueda(url=url, mensaje=mensaje, tienda=tienda,
                                               ahora=ahora, idchat=idchat, did=did)
                bid_results.append( (bid, tienda, False) )
            else:
                bid = res_busqueda['bid']
                bid_results.append( (bid, tienda, True) )       

        return bid_results
                    
    except Exception as e:
        print('obtener_soup:', e)



# Busca la categoria y si existe devuelve el ID
# Si no existe la inserta y retorna el ID
def obtener_id_categoria(cat):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT cid FROM categoria WHERE nombre=%s''', (cat, ))
    result = cursor.fetchone()
    if not result:
        cursor.execute('''INSERT INTO categoria(nombre) VALUES(%s)''', (cat, ))
        conn.commit()
        cursor.execute('''SELECT cid FROM categoria WHERE nombre=%s''', (cat, ))
        cid = cursor.fetchone()[0]
    else:
        cid = result[0]
    conn.close()
    return cid


def existe_departamento_en_categoria(did, cid):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT did FROM departamento WHERE did=%s and cid=%s''', (did, cid))
    result = cursor.fetchall()
    conn.close()
    return len(result)


def registrar_categoria_en_tienda(tid, cid):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT tid FROM tienda_categoria WHERE tid=%s and cid=%s''', (tid, cid))
    result = cursor.fetchall()
    if not result:
        cursor.execute('''INSERT INTO tienda_categoria(tid, cid) VALUES(%s, %s)''', (tid, cid))
        conn.commit()
    conn.close()  


# deps es un diccionario donde para cada categoria de la tienda
# se listan los departamentos asociados
def actualizar_departamentos_en_categoria(tid, deps):
    try:
        conn, cursor = inicializar_bd()
        for cat in deps:
            cid = obtener_id_categoria(cat)
            registrar_categoria_en_tienda(tid, cid)
            for did, nombre in deps[cat].items():
                if not existe_departamento_en_categoria(did, cid):
                    cursor.execute('''INSERT INTO departamento(did, nombre, cid) VALUES(%s, %s, %s)''', (did, nombre, cid))                    
                    conn.commit()
                    registrar_categoria_en_tienda(tid, cid)
        conn.close()
    except Exception as ex:
        print('actualizar_departamentos_en_categoria', ex)



# Obtiene las categorias y departamentos de la tienda actual
def parsear_menu_departamentos(idchat):
    try:
        tienda = obtener_ajustes_usuario(idchat)['tid']

        conn, cursor = inicializar_bd()
        # Si no se le ha generado menu a la tienda o el que existe aun es valido
        cursor.execute('''select departamento.did, departamento.nombre from departamento join \
                       categoria join tienda_categoria where departamento.cid = categoria.cid \
                       and tienda_categoria.cid = categoria.cid and tienda_categoria.tid=%s''', (tienda, ))
        results = cursor.fetchall()
        conn.close()
        if not results:
            respuesta = session.get(f'{URL_BASE_TUENVIO}/{tienda}', headers=HEADERS)
            data = respuesta.content.decode('utf8')
            soup = BeautifulSoup(data, 'html.parser')
            ahora = datetime.datetime.now()
            
            deps = {}
            navbar = soup.select('.mainNav .navbar .nav > li:not(:first-child)')
            for child in navbar:
                cat = child.select('a')[0].contents[0]
                deps[cat] = {}
                for d in child.select('div > ul > li'):
                    d_id = d.select('a')[0]['href'].split('=')[1]
                    d_nombre = d.select('a')[0].contents[0]
                    deps[cat][d_id] = d_nombre
            
            actualizar_departamentos_en_categoria(tienda, deps)
            # TODO: Incorporar la cache
    except Exception as ex:
        print('parsear_menu_departamentos', ex)



def hay_productos_en_provincia(criterio, prov_id):
    tiendas = obtener_tiendas(prov_id)
    for tid, nombre in tiendas:
        url = f'{URL_BASE_TUENVIO}/{tid}/Search.aspx?keywords=%22{criterio}%22&depPid=0'
        respuesta = session.get(url, headers=HEADERS)
        data = respuesta.content.decode('utf8')
        soup = BeautifulSoup(data, 'html.parser')
        productos = parsear_productos(soup, url)
        if productos:
            return productos
    else:
        return False


# Reduce el credito en monto al usuario
def deducir_credito_usuario(context, uid, monto = 1):
    conn, cursor = inicializar_bd()
    ahora = datetime.datetime.now()
    debug_print(f'Deduciendo {monto} crédito al usuario {uid}')
    cursor.execute('''UPDATE usuario SET credito = credito - %s WHERE uid = %s and credito > 0''', (monto, uid))
    cursor.execute('''INSERT INTO operacion_credito(uid, descripcion, tipo, monto, fecha) VALUES(%s, %s, %s, %s, %s)''',
                    (uid, 'Deducción por búsqueda', 'débito', monto, ahora))
    conn.commit()    
    conn.close()
    if obtener_credito_usuario(uid) == 0:
        context.bot.send_message(chat_id=uid, 
                                 text='Su crédito se ha agotado, por favor, recargue 👍.',
                                 parse_mode='HTML')
        debug_print(f'Agotado el crédito del usuario {uid}')



def esta_en_turno_de_escaneo(uid, criterio, prov_id):
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT ultimo_escaneo, frecuencia FROM subscripcion WHERE uid=%s and criterio=%s and prov_id=%s''',
                        (uid, criterio, prov_id))
        (ultimo_escaneo, frecuencia) = cursor.fetchone()
        conn.close()
        ttrans = (datetime.datetime.now() - ultimo_escaneo).total_seconds()
        return ttrans >= frecuencia
    except Exception as ex:
        debug_print(f'esta_en_turno_de_escaneo: {ex}', 'error')


def actualizar_ultimo_escaneo(uid, criterio, prov_id):
    conn, cursor = inicializar_bd()
    debug_print(f'Actualizando último escaneo para {uid}')
    ahora = datetime.datetime.now()
    cursor.execute('''UPDATE subscripcion SET ultimo_escaneo = %s WHERE uid = %s and criterio = %s and prov_id = %s''', 
                    (ahora, uid, criterio, prov_id))
    conn.commit()
    conn.close()


# A partir de la lista de ID de usuarios separada por coma retorna aquellos 
# a los que se les puede efectuar la busqueda
def obtener_usuarios_listos_para_escaneo(uids, criterio, prov_id):
    listos = []
    for uid in uids.split(','):
        if obtener_credito_usuario(uid) > 0 and esta_en_turno_de_escaneo(uid, criterio, prov_id):
            listos.append(uid)
    return listos


def obtener_nombre_usuario(uid):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT nombre FROM usuario WHERE uid=%s''', (uid, ))
    result = cursor.fetchone()
    if result:
        return result[0]
    conn.close() 
    return 'Desconocido'


def notificar_subscritos(context):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT criterio, prov_id, group_concat(uid) as uids FROM subscripcion WHERE estado=%s group by criterio asc, prov_id''', ('activa', ))
    for (criterio, prov_id, uids) in cursor:
        nombre_provincia = obtener_nombre_provincia(prov_id)
        busqueda_realizada = productos = alguien_tiene_credito = False
        listos = obtener_usuarios_listos_para_escaneo(uids, criterio, prov_id)
        for uid in listos:
            debug_print(f'Ejecutando búsqueda programada de {criterio} para {uid}')
            deducir_credito_usuario(context, uid, 1 / len(listos))
            actualizar_ultimo_escaneo(uid, criterio, prov_id)
            alguien_tiene_credito = True
            # Si no ha sido obtenido para otro usuario buscarlo
            if not busqueda_realizada:     
                try:      
                    productos = hay_productos_en_provincia(criterio, prov_id)
                except ConnectionResetError:
                    debug_print('Error de conexión al localizar productos para notificar', 'error')
                except Exception as ex:
                    debug_print(f'Error desconocido al localizar productos para notificar, se obtuvo {ex}', 'error')
                busqueda_realizada = True      
            if productos:
                for uid in uids.split(','):
                    if obtener_credito_usuario(uid) > 0:
                        texto_respuesta = f'Atención: Se encontró <b>{criterio}</b> en <b>{nombre_provincia}</b>.\n\n'
                        i = 1
                        for producto, precio, plink, pid in productos:
                            texto_respuesta += f'{i}. 📦 {producto} --> {precio} <a href="{plink}">ver producto</a>\n'
                            i += 1          
                        context.bot.send_message(chat_id=uid, text=texto_respuesta, parse_mode='HTML')
                        nombre_usuario = obtener_nombre_usuario(uid)
                        texto_debug_info = f'Notificado {uid} ({nombre_usuario}) sobre criterio {criterio} en {nombre_provincia}'
                        debug_print(texto_debug_info, 'estado')
                        # Temporal para informar que alguien encontró producto como subscrito
                        for admin in SUPER_ADMINS:
                            context.bot.send_message(chat_id=admin, text=texto_debug_info, parse_mode='HTML')
                    else:
                        context.bot.send_message(chat_id=uid,
                                                 text=f'Su crédito de operaciones se ha agotado, por favor, envíe cualquier donación para continuar usando los servicios de búsqueda y subscripción.', 
                                                 parse_mode='HTML')
                    # Activar esta llamada segun ajuste del sistema, para que se elimine la subscripcion
                    # una vez encontrado el criterio
                    #desactivar_notificacion(uid, criterio, prov_id)

        else:
            if not alguien_tiene_credito:
                debug_print(f'Procesados todos los usuarios subscritos a {criterio} en {nombre_provincia}.')
    conn.close()


def obtener_producto_segun_pid(pid):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT nombre, precio, enlace FROM producto WHERE pid=%s''', (pid, ))
    result = cursor.fetchone()
    conn.close()
    return( pid, result[0], result[1], result[2] )


def obtener_productos_resultado_busqueda(bid):
    try:
        conn, cursor = inicializar_bd()
        productos = []
        cursor.execute('''SELECT pid FROM busqueda JOIN resultado WHERE busqueda.bid = resultado.bid \
                            and busqueda.bid=%s''', (bid, ))
        for (pid, ) in cursor:
            productos.append(obtener_producto_segun_pid(pid))

        conn.close()
        return productos
    except Exception as ex:
        print('obtener_productos_resultado_busqueda', ex)                                  


# Buscar los productos en la provincia seleccionada
def enviar_mensaje_productos_encontrados(update, context, palabras=False, dep=False):
    idchat = update.effective_chat.id
    nombre = update.effective_user.username
    au = obtener_ajustes_usuario(idchat)
    if dep:        
        did = au['did']
        cat = au['cid']
    prov = au['prov_id']
    tid = au['tid']

    texto_respuesta = ''
    try:
        if dep:
            bid_results = obtener_soup(dep, nombre, idchat, True)
        else:
            if not palabras:
                palabras = update.message.text
            bid_results = obtener_soup(palabras, nombre, idchat)
        conn, cursor = inicializar_bd()    
        for bid, tienda, en_cache in bid_results:
            if not en_cache:  
                deducir_credito_usuario(context, idchat)       
            nombre_provincia = obtener_nombre_provincia(prov)
            nombre_tienda = obtener_nombre_tienda(tienda)
            
            productos = obtener_productos_resultado_busqueda(bid)
            texto_respuesta_tid = ''
            if productos:
                for pid, producto, precio, plink in productos:
                    dispatcher.add_handler( CommandHandler(f'subscribirse_a_{pid}', sub_a), 1)                       
                    texto_respuesta_tid += f'📦{producto} --> {precio} <a href="{plink}">ver producto</a> o /subscribirse_a_{pid}\n'
                if dep:
                    nombre_dep = obtener_nombre_departamento(did)                
                    texto_respuesta_tid = f'<b>Resultados en: 🏬 {nombre_tienda}</b>\n\n<b>Departamento:</b> {nombre_dep}\n\n{texto_respuesta_tid}\n'
                else:
                    texto_respuesta_tid = f'<b>Resultados en: 🏬 {nombre_tienda}</b>\n\n{texto_respuesta_tid}\n'
            texto_respuesta = f'{texto_respuesta}{texto_respuesta_tid}'
            texto_respuesta_tid = ''
        if texto_respuesta:
            texto_respuesta = f'🎉🎉🎉¡¡¡Encontrado!!! 🎉🎉🎉\n\n{texto_respuesta}'
        else:
            if dep:
                texto_respuesta = 'No hay productos en el departamento seleccionado ... 😭'
            else:
                texto_respuesta = 'No hay productos que contengan la palabra buscada ... 😭'

    except Exception as ex:
        print('enviar_mensaje_productos_encontrados:', ex)

    context.bot.send_message(chat_id=idchat, text=texto_respuesta, parse_mode='HTML')



def es_comando_valido(comando):
    comandos_validos = [
        '/subscribirse_a_',
        '/eliminar_',
        '/credito_',
        '/cambiar_frec_',
        '/activar_'
    ]
    for com_val in comandos_validos:
        if comando.startswith(com_val):
            return True
    return False


# No procesar comandos incorrectos
def desconocido(update, context):
    text = update.message.text
    if not es_comando_valido(text):
        texto_respuesta = f'Lo sentimos, "{text}" no es un comando.'
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=texto_respuesta)

dispatcher.add_handler(MessageHandler(Filters.command, desconocido))


def existe_registro_usuario(idchat):
    try:
        conn, cursor = inicializar_bd()
        cursor.execute('''SELECT * FROM usuario WHERE uid=%s''', (idchat, ))
        result = len(cursor.fetchall())
        cursor.close()
        return result
    except Exception as ex:
        print('existe_registro_usuario', ex)


def registrar_usuario(update, context):
    try:
        conn, cursor = inicializar_bd()
        idchat = update.effective_chat.id
        nombre = update.effective_user.username
        cursor.execute('''INSERT INTO usuario(uid, nombre) VALUES(%s, %s)''', (idchat, nombre))
        conn.commit()
    except Exception as ex:
        print('registrar_usuario', ex)


# 1. Chequea si existe alguna busqueda con ese criterio para el usuario actual
# y aun esta activa segun el TTL
# def respuesta_cacheada(uid, criterio, did, tid):
#     conn, cursor = inicializar_bd()    
#     if criterio:        
#         filtro = 'criterio=%s'
#         params = (uid, criterio, tid)
#     else:
#         filtro = 'did=%s and tid=%s'
#         params = (uid, did, tid)
#     consulta = '''SELECT bid, fecha, tid FROM busqueda WHERE uid=%s and ''' 
#                 + filtro + ''' order by fecha desc limit 1'''

#     cursor.execute(consulta, params)
#     result = cursor.fetchone()
#     conn.close()
#     if result:
#         bid = result[0]
#         fecha = result[1]
#         tid = result[2]
#         if criterio and not tienda_pertenece_a_provincia(tid, obtener_ajustes_usuario(uid)['prov_id']):
#             return False
#         else:
#             ahora = datetime.datetime.now()
#             antig_busq = (ahora - fecha).total_seconds()    
#             if antig_busq < TTL:        
#                 return bid    
#     return False        


# Version 2.0 mejorada
# def buscar_producto(update, context, **kargs):
#     idchat = update.effective_chat.id
#     if 'criterio' in kargs:
#         criterio = kargs['criterio']
#     elif 'did' in kargs:
#         did = kargs['did']
#     tid = obtener_ajustes_usuario('idchat')['tid']


    

    


    # 2. Si no hay una busqueda con resultados disponibles proceder a descargar la
    # pagina (chequear si hay conexion o esta dando mensaje denegado)
    # sugerencia: buscar en head > title si el contenido tiene "Mantenimiento"


    # 3. De obtener un resultado en la pagina proceder a parsear los productos

    # 4. Enviar el mensaje con la respuesta


def enviar_listado_productos_segun_criterio(update, context, palabra):
    idchat = update.effective_chat.id
    conn, cursor = inicializar_bd()
    criterio = '%'.join(palabra.split())
    criterio = f'%{criterio}%'
    cursor.execute('''SELECT pid, nombre, precio FROM producto WHERE nombre like %s limit 10''', (criterio, ))
    result = cursor.fetchall()
    if result:
        mensaje = f'Algunos de los productos que contienen <b>{palabra}</b>\n\n'
        for (pid, nombre, precio) in result:
            mensaje += f'📦 {nombre} -> {precio} /subscribirse_a_{pid}\n'
        context.bot.send_message(chat_id=idchat, text=mensaje, parse_mode='HTML')
    else:
        context.bot.send_message(chat_id=idchat, 
                                 text='No hay productos que coincidan con el criterio enviado en nuestra base de datos', 
                                 parse_mode='HTML')

    conn.close()


def obtener_frecuencias():
    conn, cursor = inicializar_bd()
    frecuencias = []
    cursor.execute('''SELECT frecuencia, texto FROM frecuencia_escaneo''')
    for frec in cursor:
        frecuencias.append( frec )
    conn.close()  
    return frecuencias


def generar_teclado_frecuencias_subscripcion(update, context, ajustes, palabra):
    prov_id = ajustes['prov_id']

    botones = []
    for frec, texto in obtener_frecuencias():
        botones.append( InlineKeyboardButton(texto, callback_data=f'sub:{prov_id}<-->{palabra}<-->{frec}') )

    reply_markup = InlineKeyboardMarkup( construir_menu(botones, n_cols=2) )

    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f'Seleccione la frecuencia de escaneo para {palabra}',
                             reply_markup=reply_markup)


def procesar_respuesta_pendiente(update, context, ajustes, palabra):
    try:
        idchat = update.effective_chat.id
        prov_id = ajustes['prov_id']
        if RESPUESTA_PENDIENTE[idchat] == 'sub:nueva':
            prov_id = ajustes['prov_id']
            if prov_id:
                generar_teclado_frecuencias_subscripcion(update, context, ajustes, palabra)
            else:
                context.bot.send_message(chat_id=idchat,
                                         text=f'Por favor, seleccione antes una provincia para registrar la subscripción',
                                         parse_mode='HTML')
        elif RESPUESTA_PENDIENTE[idchat] == 'prod:list':
            enviar_listado_productos_segun_criterio(update, context, palabra)
        del RESPUESTA_PENDIENTE[idchat]
    except Exception as ex:
        print('procesar_respuesta_pendiente', ex)


def procesar_categorias(update, context, ajustes):
    try:
        idchat = update.effective_chat.id
        if not ajustes['prov_id']:
            context.bot.send_message(chat_id=idchat,
                                     text='Seleccione su provincia para comenzar a hacer uso del bot.')
        elif not ajustes['tid']:
            context.bot.send_message(chat_id=idchat,
                                     text='Debe haber seleccionado una tienda antes de acceder a sus categorías.')
        else:
            parsear_menu_departamentos(idchat)
            generar_teclado_categorias(update, context, nuevo=True)
    except Exception as ex:
        print('procesar_categorias', ex)



def numero_busquedas_ultima_hora(idchat):
    conn, cursor = inicializar_bd()
    cursor.execute('''SELECT * FROM busqueda WHERE timestampdiff(SECOND, fecha, now()) < 3600 and uid=%s''', (idchat, ))
    result = cursor.fetchall()
    conn.close()
    if result:
        return len(result)    
    return 0


def actualizar_estado_subscripciones(context):
    conn, cursor = inicializar_bd()
    cursor.execute('''UPDATE subscripcion SET estado = %s WHERE timestampdiff(SECOND, fecha, now()) > 86400''', ('expirada', ))
    conn.commit()
    conn.close()  


# Procesar mensajes de texto que no son comandos
def procesar_palabra(update, context):
    try:
        palabra = update.message.text
        idchat = update.effective_chat.id
        if existe_registro_usuario(idchat):
            ajustes = obtener_ajustes_usuario(idchat)
            if ajustes:
                if palabra == BOTONES['PROVINCIAS']:        
                    generar_teclado_provincias(update, context)
                elif palabra == BOTONES['AYUDA']:
                    ayuda(update, context)
                elif palabra == BOTONES['INICIO']:
                    iniciar_aplicacion(update, context)
                elif palabra == BOTONES['INFO']:
                    mostrar_informacion_usuario(update, context)
                elif palabra == BOTONES['SUBS']:
                    generar_teclado_opciones_subscripcion(update, context)
                elif palabra == BOTONES['MAS_BUSCADOS']:
                    mas_buscados(update, context)
                elif palabra == BOTONES['PRODUCTOS']:
                    context.bot.send_message(chat_id=idchat,
                             text='Envíe una o varias palabras y recibirá un listado con los productos registrados relacionados.')
                    RESPUESTA_PENDIENTE[idchat] = 'prod:list'
                elif palabra == BOTONES['ACERCA_DE']:
                    context.bot.send_message(chat_id=idchat,
                                            text='<b>Reportes de errores y sugerencias a:</b>\n\n @disnelr\n+53 56963700\ndisnelrr@gmail.com',
                                            parse_mode='HTML')
                elif obtener_credito_usuario(idchat) > 0:
                    if palabra == BOTONES['CATEGORIAS']:
                        procesar_categorias(update, context, ajustes)
                    elif idchat in RESPUESTA_PENDIENTE:
                        procesar_respuesta_pendiente(update, context, ajustes, palabra)                
                    else:
                        if numero_busquedas_ultima_hora(idchat) > int( obtener_ajuste_bot('max_busquedas_por_hora') ) and obtener_credito_usuario(idchat) == 0:
                            debug_print(f'Usuario {idchat} rebasó búsquedas máximas por hora y no dispone de crédito.')
                            context.bot.send_message(chat_id=idchat, 
                                            text=f'Ha rebasado el número de búsquedas permitidas en una hora. Intente más tarde.')
                        else:
                            enviar_mensaje_productos_encontrados(update, context)
                else:
                    context.bot.send_message(chat_id=idchat, 
                                     text=f'🎩 Bot en mantenimiento. Gracias por su apoyo.')
            else:
                context.bot.send_message(chat_id=idchat, 
                                        text=f'Sus datos no han sido registrados. Pulse /start para registrarlos.')
        else:
            registrar_usuario(update, context)
            context.bot.send_message(chat_id=idchat, 
                                     text=f'Sus datos han sido registrados. Ahora pruebe seleccionar una provincia.')
    except Exception as ex:
        print('procesar_palabra', ex)


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


job_queue = updater.job_queue
job_queue.run_repeating(notificar_subscritos, int(obtener_ajuste_bot('intervalo_busqueda_subscripcion')) )
#job_queue.run_repeating(actualizar_estado_subscripciones, int(obtener_ajuste_bot('intervalo_busqueda_subscripcion')) / 2)