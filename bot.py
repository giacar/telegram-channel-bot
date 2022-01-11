#from facebook_scraper import get_posts
import urllib.request
from urllib.error import URLError, HTTPError
import time
import sys
import os
from io import StringIO, BytesIO
import pandas as pd
import logging
import signal
from datetime import datetime
from dateutil import parser
import psycopg2

import telepot
from telepot.loop import MessageLoop

#from discord_webhook import DiscordWebhook, DiscordEmbed

logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] %(message)s', datefmt='%Y-%m-%d,%H:%M:%S', level=logging.INFO)


FEEDRSS = os.environ.get("FEED_RSS", None)

DONATION = os.environ.get("DONATION", None)

TOKEN = os.environ.get("TOKEN_BOT", None)
CHANNEL = os.environ.get("CHANNEL_ID", None)
RESETBOT = os.environ.get("RESET_BOT", None)
DATABASE_URL = os.environ.get("DATABASE_URL", None)

#DISCORD_URL = os.environ.get("DISCORD_URL", None)
#DISCORD_AUTHOR_URL = ""
#DISCORD_AUTHOR_ICON = ""

#webhook = DiscordWebhook(url=DISCORD_URL)

# Initialize value
last_timestamp = 0


def check_conn():
    global conn     # used to refer to global variable conn

    if conn.closed:
        logging.warning("Database connection is closed, open another one")
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM timestamp;")
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

    cur.execute("UPDATE timestamp SET value = %s;", (str(last_timestamp),))

    conn.commit()

    cur.close()
    conn.close()

    fromVarToDB()

    logging.info("Last timestamp is updated, now I can exit safely")
    '''
    reboot_msg = "Il dyno si è riavviato.\nIscritti totali: %d; attivi: %d, inattivi: %d."%(len(chat_id_dict['active'])+len(chat_id_dict['stopped']), len(chat_id_dict['active']), len(chat_id_dict['stopped']))
    embed = DiscordEmbed(title='♻️♻️♻️ Stato ♻️♻️♻', description=reboot_msg)
    embed.set_author(name='Terremoti Vicovaro Bot', url=DISCORD_AUTHOR_URL, icon_url=DISCORD_AUTHOR_ICON)
    webhook.add_embed(embed)
    webhook.execute()
    '''

    sys.exit(0)


def fromVarToDB():
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM timestamp;", (str(last_timestamp),))
    if len(cur.fetchall()) == 0:
        cur.execute("INSERT INTO timestamp(value) VALUES (%s);", (str(last_timestamp),))
    else:
        cur.execute("UPDATE timestamp SET value = %s;", (str(last_timestamp)))

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


def getFBPost():
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
    FILETXT = None

    s = getFBPost()
    if s.isdigit():
        logging.warn("Not possible to GET Data")
        return -1
    else:
        FILETXT = StringIO(s)

    df = pd.read_csv(FILETXT, sep=',')

    return df


'''
def storeFakeEvent(event, timestamp):
    check_conn()

    cur = conn.cursor()

    cur.execute("INSERT INTO fake_events(eventid, timestamp) VALUES (%s, %s);", (int(event['EventID']), timestamp))

    conn.commit()
    cur.close()

def realNewEvent(event):
    rawtimestamp = str(event['Time'])                                   #2021-01-23T13:09:56.000000
    rawdate = rawtimestamp.split('T')[0]                                #2021-01-23

    eventdate = date.fromisoformat(rawdate)
    todaydate = datetime.now(timezone('Europe/Rome')).date()            # get Italy's date to fix if server is hosted in other countries

    if eventdate == todaydate:
        return True
    return False
'''


def checkIfNewPost():
    global last_timestamp
    
    head_ts = int(datetime.timestamp(parser.parse(df["Date"][0])))
    
    if head_ts > last_timestamp :
        logging.info("New post detected!")
        last_timestamp = head_ts
        logging.info("New value last_timestamp = "+str(last_timestamp))
        return True
    else:
        return False
      

def sendNewPost():
    logging.info("Sending new post to Channel...")
    
    head_ts = int(datetime.timestamp(parser.parse(df["Date"][0])))
    
    if head_ts == last_timestamp :
        bot.sendMessage(CHANNEL, df["Description"][0].replace("...", "", 1))
        logging.info("... Sent")


def handleMessageBot(msg):
    chat_id = msg['chat']['id']
    msg_cont = msg['text'].lower()
    
    if msg_cont == '/start' :
        logging.info("New Chat: " + str(chat_id))
        bot.sendMessage(chat_id, "Benvenuto! Questo bot è utile per la pubblicazione dei messaggi nel canale.")
        bot.sendMessage(chat_id, "Se vuoi leggere l'ultimo post pubblicato, usa il comando /ultimo")
        bot.sendMessage(chat_id, "Se vuoi fare una piccola donazione, usa il comando /dona")
    
    if msg_cont == '/ultimo' :
        localdf = initTable()
        bot.sendMessage(chat_id, localdf["Description"][0].replace("...", "", 1))
        del localdf

    if msg_cont == '/dona':
        donation_msg = "Se il bot ti piace e vuoi supportarmi, puoi fare una donazione tramite PayPal [cliccando qui](%s)\. Grazie\!"%DONATION
        bot.sendMessage(chat_id, donation_msg, parse_mode="MarkdownV2", disable_web_page_preview=True)


conn = psycopg2.connect(DATABASE_URL, sslmode='require')

signal.signal(signal.SIGTERM, handle_stop)
signal.signal(signal.SIGINT, handle_stop)

urllib.request.urlopen(RESETBOT)

bot = telepot.Bot(TOKEN)

#last_timestamp = fromFileToVar()                           # load the timestamp from old epochs
last_timestamp = fromDBToVar()                              # load the timestamp from old epochs
logging.info("Recovered last timestamp: "+str(last_timestamp))

MessageLoop(bot, handleMessageBot).run_as_thread()


# Initialize the table
df = initTable()
while isinstance(df, int) and df==-1:
    df = initTable()

logging.info("Table initialized")
#print(df)

i = 0
j = 0

if checkIfNewPost() == True:
    sendNewPost()

# Loop
while (True):
    # check each 10 minutes
    if i==10:
        i=0

        df = initTable()

        if isinstance(df, int) and df == -1:
            time.sleep(10)
            continue

        if checkIfNewPost() == True:
            sendNewPost()

        if j==60:
            j=0
            logging.info("Bot is active, last timestamp = "+last_timestamp)

    i+=1
    j+=1
    time.sleep(60)

