from facebook_scraper import get_posts
from operator import itemgetter
import urllib.request
from urllib.error import URLError, HTTPError
import time
import sys
import os
from io import StringIO, BytesIO
import pandas as pd
import logging
import traceback
import signal
from datetime import datetime
from dateutil import parser
import psycopg2

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram

from discord_webhook import DiscordWebhook, DiscordEmbed

logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] %(message)s', datefmt='%Y-%m-%d,%H:%M:%S', level=logging.INFO)


FEEDRSS = os.environ.get("FEED_RSS", None)

DONATION = os.environ.get("DONATION", None)

TOKEN = os.environ.get("TOKEN_BOT", None)
CHANNEL = os.environ.get("CHANNEL_ID", None)
RESETBOT = "https://api.telegram.org/bot"+TOKEN+"/setWebhook?url="
DATABASE_URL = os.environ.get("DATABASE_URL", None)

DISCORD_URL = os.environ.get("DISCORD_URL", None)
DISCORD_AUTHOR_URL = "http://t.me/ilcomunedicastelmadamabot"
DISCORD_AUTHOR_ICON = "https://i.ibb.co/CtSBXRV/image.jpg"

webhook = DiscordWebhook(url=DISCORD_URL)

# Initialize value
last_timestamp = 0
last_message = ""


def check_conn():
    global conn     # used to refer to global variable conn

    if conn.closed:
        logging.warning("Database connection is closed, open another one")
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM timestamp;")
        cur.close()
    except psycopg2.OperationalError:
        logging.error("Problem with database connection, open another one")
        cur.close()
        conn.close()
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        logging.info("Database connection is OK")


def handle_stop(sig, frame):
    logging.info("Updating timestamp before to exit...")
    
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM timestamp;")
    if len(cur.fetchall()) == 0:
        cur.execute("INSERT INTO timestamp(value) VALUES (%s);", (str(last_timestamp),))
    else:
        cur.execute("UPDATE timestamp SET value = %s;", (str(last_timestamp),))

    conn.commit()
    
    cur.close()
    conn.close()

    logging.info("Last timestamp is updated, now I can exit safely")
    
    reboot_msg = "Il dyno si è riavviato."
    embed = DiscordEmbed(title='♻️♻️♻️ Stato ♻️♻️♻', description=reboot_msg)
    embed.set_author(name='Comune di Castel Madama Bot', url=DISCORD_AUTHOR_URL, icon_url=DISCORD_AUTHOR_ICON)
    webhook.add_embed(embed)
    webhook.execute()

    sys.exit(0)


def fromVarToDB():
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM timestamp;")
    if len(cur.fetchall()) == 0:
        cur.execute("INSERT INTO timestamp(value) VALUES (%s);", (str(last_timestamp),))
    else:
        cur.execute("UPDATE timestamp SET value = %s;", (str(last_timestamp),))

    conn.commit()
    cur.close()


def fromDBToVar():
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM timestamp;")
    list_value = cur.fetchall()

    ts = 0

    for value in list_value:
        ts = int(value[0])

    cur.close()
    return ts


def fromVarToFile():
    with open("last_timestamp.txt", "w") as file:
        file.write(str(last_timestamp))


def fromFileToVar():
    ts = 0
    
    try:
        with open("last_timestamp.txt", "r") as file:
            ts = int(file.readline().strip())
    
    except FileNotFoundError:
        pass
    
    return ts


def getRSSPost():
    try:
        response = urllib.request.urlopen(FEEDRSS)
    
        if response.getcode() == 200:
            contents = response.read().decode("utf-8")
            return contents
        else:
            return -1
    except HTTPError as e:
        logging.error("Error code: "+str(e.code))
        return -1
    except URLError as e:
        logging.error("Reason: "+str(e.reason))
        return -1


def initTable():
    FILECSV = None

    s = getRSSPost()
    if s.isdigit():
        logging.warn("Not possible to GET Data")
        return -1
    else:
        FILECSV = StringIO(s)

    df = pd.read_csv(FILECSV, sep=',')

    return df


def initScrapedTable():
    list_data = []

    try:
        for post in get_posts('ilcomunedicastelmadama', pages=2, credentials=(os.environ.get("FB_EMAIL", None), os.environ.get("FB_PASS", None)), cookies=StringIO(os.environ.get("COOKIES", None))):
            list_data.append([ post["post_id"], post["text"].replace("...", ""), int(datetime.timestamp(post["time"])) ])
        
        if len(list_data) == 0:
            return -1

        list_data = sorted(list_data, key=itemgetter(2), reverse=True)      # sorting for timestamp in descending order

        df_scraped = pd.DataFrame(list_data, columns = ['post_id', 'text', 'timestamp'])

        return df_scraped
    
    except Exception as e:
        logging.error(traceback.format_exc())
        return -1


def checkAndSendNewPost():
    global last_timestamp
    
    head_rss_ts = int(datetime.timestamp(parser.parse(df["Date"][0])))
    
    if head_rss_ts > last_timestamp :
        logging.info("New post detected!")
        last_timestamp = head_rss_ts
        last_message = df["Description"][0].replace("...", "", 1)
        logging.info("New value last_timestamp = "+str(last_timestamp))
        fromVarToDB()
        logging.info("New value stored in the database")

        logging.info("Sending new post to Channel...")
        bot.sendMessage(CHANNEL, last_message)
        logging.info("... sent!")
    
    if not (isinstance(df_scraped, int) and df_scraped == -1):
        head_scraped_ts = int(df_scraped['timestamp'][0])
        
        if head_scraped_ts > last_timestamp:
            logging.info("New post detected!")
            last_timestamp = head_scraped_ts
            last_message = df_scraped["text"][0].replace("...", "", 1)
            logging.info("New value last_timestamp = "+str(last_timestamp))
            fromVarToDB()
            logging.info("New value stored in the database")
            
            logging.info("Sending new post to Channel...")
            bot.sendMessage(CHANNEL, last_message)
            logging.info("... sent!")


def start_message(update, context):
    logging.info("Command /start from chat_id: " + str(update.message.chat.id))
    update.message.reply_text("Benvenuto! Questo bot è utile per la pubblicazione dei messaggi nel canale.")
    update.message.reply_text("Se vuoi leggere l'ultimo post pubblicato, usa il comando /ultimo")
    update.message.reply_text("Se vuoi fare una piccola donazione, usa il comando /dona")

def last_message(update, context):
    update.message.reply_text(last_message)

def donation_message(update, context):
    donation_msg = "Se il bot ti piace e vuoi supportarmi, puoi fare una donazione tramite PayPal [cliccando qui](%s)\. Grazie\!"%DONATION
    update.message.reply_text(donation_msg, parse_mode="markdown", disable_web_page_preview=True)

def nocmd_message(update, context):
    update.message.reply_text("Comando non riconosciuto: scegli tra /start , /ultimo e /dona")

def error(update, context):
    # Log Errors caused by Updates.
    logging.warning('Update "%s" caused error "%s"', update, context.error)


conn = psycopg2.connect(DATABASE_URL, sslmode='require')

signal.signal(signal.SIGTERM, handle_stop)
signal.signal(signal.SIGINT, handle_stop)

urllib.request.urlopen(RESETBOT)

bot = telegram.Bot(TOKEN)
upd = Updater(TOKEN, use_context=True)
disp = upd.dispatcher

disp.add_handler(CommandHandler("start", start_message))
disp.add_handler(CommandHandler("ultimo", last_message))
disp.add_handler(CommandHandler("dona", donation_message))
disp.add_handler(MessageHandler(Filters.text, nocmd_message))

disp.add_error_handler(error)

upd.start_polling()

#last_timestamp = fromFileToVar()                           # load the timestamp from old epochs
last_timestamp = fromDBToVar()                              # load the timestamp from old epochs
logging.info("Recovered last timestamp: "+str(last_timestamp))

# Initialize tables
df = initTable()
df_scraped = initScrapedTable()
while isinstance(df, int) and df==-1:
    time.sleep(10)
    df = initTable()

logging.info("Table initialized")

i = 0
j = 0

checkAndSendNewPost()

# Loop
while (True):
    # check each 30 minutes
    if i==30:
        i=0

        df = initTable()
        df_scraped = initScrapedTable()

        if isinstance(df, int) and df == -1:
            time.sleep(10)
            continue

        checkAndSendNewPost()

    #check each 1 hour
    if j==60:
        j=0
        logging.info("Bot is active, last timestamp = "+str(last_timestamp))

    i+=1
    j+=1
    time.sleep(60)

