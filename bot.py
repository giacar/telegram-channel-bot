from facebook_scraper import get_posts
from operator import itemgetter
import urllib.request
from urllib.error import URLError, HTTPError
import time
import sys
import os
from io import StringIO, BytesIO
import facebook_scraper
import pandas as pd
import logging
import traceback
import signal
from datetime import datetime
from dateutil import parser
import psycopg2
import hashlib

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram

from discord_webhook import DiscordWebhook, DiscordEmbed

logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] %(message)s', datefmt='%Y-%m-%d,%H:%M:%S', level=logging.INFO)
logging.getLogger("facebook_scrapper").setLevel(logging.ERROR)
list_module = ["1855560011294106", "1851449055038535", "1854403658076408", "1853766861473421", "1852702961579811", "1851690341681073"]
for mod in list_module:
    logging.getLogger(mod).setLevel(logging.ERROR)
facebook_scraper.enable_logging(logging.ERROR)

FEEDRSS = os.environ.get("FEED_RSS", None)

DONATION = os.environ.get("DONATION", None)

TOKEN = os.environ.get("TOKEN_BOT", None)
CHANNEL = os.environ.get("CHANNEL_ID", None)
RESETBOT = "https://api.telegram.org/bot"+str(TOKEN)+"/setWebhook?url="
DATABASE_URL = os.environ.get("DATABASE_URL", None)

DISCORD_URL = os.environ.get("DISCORD_URL", None)
DISCORD_AUTHOR_URL = "http://t.me/ilcomunedicastelmadamabot"
DISCORD_AUTHOR_ICON = "https://i.ibb.co/CtSBXRV/image.jpg"

webhook = DiscordWebhook(url=DISCORD_URL)

# Initialize value
useCredentials = False      # FB credential or cookies
useFBScraping = True        # Enable FB scraping
useDB = True                # Use DB or local file to store information

last_timestamp = 0
last_message = ""
last_md5 = ""

# create cookies.txt file using env var value
if not useCredentials:
    with open("cookies.txt", "w") as file:
        file.write(str(os.environ.get("COOKIES", None)))

# check the connection with the postgres database
def check_conn():
    global conn     # used to refer to global variable conn

    if conn.closed:
        logging.warning("Database connection is closed, open another one")
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM state;")
        cur.close()
    except psycopg2.OperationalError:
        logging.error("Problem with database connection, open another one")
        cur.close()
        conn.close()
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        logging.info("Database connection is OK")

# compute md5 fingerprint of an input string
def compute_md5(input):
    return hashlib.md5(input.encode()).hexdigest()

# clean message from ... used by Facebook
def clean_msg(input):
    return input.replace("...", "", 1)

# Signal capture handler
def handle_stop(sig, frame):
    logging.info("Updating state before to exit...")
    
    if useDB:
        check_conn()

        cur = conn.cursor()
        
        cur.execute("SELECT * FROM state;")
        if len(cur.fetchall()) == 0:
            cur.execute("INSERT INTO state VALUES (%s,%s);", (str(last_timestamp),str(last_message)))
        else:
            cur.execute("UPDATE state SET ts = %s, msg = %s;", (str(last_timestamp),str(last_message)))

        conn.commit()
        
        cur.close()
        conn.close()
    else:
        with open("last_state.txt", "w") as file:
            file.write(str(last_timestamp)+'\n'+str(last_message))

    logging.info("Last state is updated")

    upd.stop()
    logging.info("Stop polling, now I can exit safely")
    
    # pubblish on my Discord Channel
    reboot_msg = "Il dyno si è riavviato."
    embed = DiscordEmbed(title='♻️♻️♻️ Stato ♻️♻️♻', description=reboot_msg)
    embed.set_author(name='Comune di Castel Madama Bot', url=DISCORD_AUTHOR_URL, icon_url=DISCORD_AUTHOR_ICON)
    webhook.add_embed(embed)
    webhook.execute()

    sys.exit(0)


# export last state in the database
def fromVarToDB():
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM state;")
    if len(cur.fetchall()) == 0:
        cur.execute("INSERT INTO state VALUES (%s,%s);", (str(last_timestamp),str(last_message)))
    else:
        cur.execute("UPDATE state SET ts = %s, msg = %s;", (str(last_timestamp),str(last_message)))

    conn.commit()
    cur.close()


# import last state from the database
def fromDBToVar():
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM state;")
    rows = cur.fetchall()

    ts = 0
    lm = ""

    for row in rows:
        ts = int(row[0])
        lm = str(row[1])

    cur.close()
    return ts, lm


# export last state to local file
def fromVarToFile():
    with open("last_state.txt", "w") as file:
        file.write(str(last_timestamp)+'\n'+str(last_message))


# export last state from local file
def fromFileToVar():
    ts = 0
    
    try:
        with open("last_state.txt", "r") as file:
            ts = int(file.readline().strip())
            msg = str(file.readline().strip())
    
    except FileNotFoundError:
        pass
    
    return ts, msg


# get the RSS content of the page
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


# build the table based on RSS information
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


# build the table based on Facebook scraping information
def initScrapedTable():
    if not useFBScraping:
        return -1
    
    list_data = []

    try:
        if useCredentials:
            posts = get_posts('ilcomunedicastelmadama', pages=2, credentials=(os.environ.get("FB_EMAIL", None), os.environ.get("FB_PASS", None)))
        else:
            posts = get_posts('ilcomunedicastelmadama', pages=2, cookies="cookies.txt")

        for post in posts:
            if post["text"] != None and post["time"] != None:
                if post["post_id"] == None:
                    post_id = ""
                else:
                    post_id = post["post_id"]
                
                list_data.append([ post_id, post["text"].replace("...", ""), int(datetime.timestamp(post["time"])) ])
        
        if len(list_data) == 0:
            return -1

        list_data = sorted(list_data, key=itemgetter(2), reverse=True)      # sorting for timestamp in descending order

        df_scraped = pd.DataFrame(list_data, columns = ['post_id', 'text', 'timestamp'])

        return df_scraped
    
    except Exception as e:
        logging.error(traceback.format_exc())
        return -1


# check and send new post found RSS and/or FB scraping 
def checkAndSendNewPost():
    global last_timestamp
    global last_message
    global last_md5

    isNewPost = False
    
    head_rss_ts = int(datetime.timestamp(parser.parse(df["Date"][0])))
    
    if head_rss_ts > last_timestamp :
        logging.info("New post detected!")
        last_timestamp = head_rss_ts
        detected_msg = clean_msg(df["Description"][0])
        detected_md5 = compute_md5(detected_msg)
        if last_md5 != detected_md5:
            last_message = detected_msg
            last_md5 = last_md5
            isNewPost = True
    
    if useFBScraping and (not (isinstance(df_scraped, int) and df_scraped == -1)):
        head_scraped_ts = int(df_scraped["timestamp"][0])
        
        if head_scraped_ts > last_timestamp:
            logging.info("New post detected!")
            last_timestamp = head_scraped_ts
            detected_msg = clean_msg(df_scraped["text"][0])
            detected_md5 = compute_md5(detected_msg)
            if last_md5 != detected_md5:
                last_message = detected_msg
                last_md5 = last_md5
                isNewPost = True
    
    if isNewPost:
        logging.info("New value last_timestamp = "+str(last_timestamp))
        if useDB:
            fromVarToDB()
            logging.info("New state stored in the database")
        else:
            fromVarToFile()
            logging.info("New state stored in the local file")
        
        logging.info("Sending new post to Channel...")
        if last_message == "" :
            logging.info("... empty message, not sent!")
        else:
            bot.sendMessage(CHANNEL, last_message)
            logging.info("... sent!")
    else:
        logging.info("Duplicated post, ignored")


# retrieve last message if var is empty
def retrieveLastMessage():
    global last_timestamp
    global last_message
    
    head_rss_ts = int(datetime.timestamp(parser.parse(df["Date"][0])))
    
    if head_rss_ts == last_timestamp :
        last_message = df["Description"][0].replace("...", "", 1)
    
    if useFBScraping and (not (isinstance(df_scraped, int) and df_scraped == -1)):
        head_scraped_ts = int(df_scraped["timestamp"][0])
        
        if head_scraped_ts == last_timestamp:
            last_message = df_scraped["text"][0].replace("...", "", 1)


# some handling message functions for the different bot commands
def start_message(update, context):
    logging.info("Command /start from chat_id: " + str(update.message.chat.id))
    update.message.reply_text("Benvenuto! Questo bot è utile per la pubblicazione dei messaggi nel canale.")
    update.message.reply_text("Se vuoi leggere l'ultimo post pubblicato, usa il comando /ultimo")
    update.message.reply_text("Se vuoi fare una piccola donazione, usa il comando /dona")

def last_post_message(update, context):
    if last_message != "":
        update.message.reply_text(last_message)
    else:
        retrieveLastMessage()
        if last_message == "":
            update.message.reply_text("Mi dispiace ma l'ultimo post al momento non è disponibile. Riprova più tardi.")
        else:
            update.message.reply_text(last_message)

def donation_message(update, context):
    donation_msg = "Se il bot ti piace e vuoi supportarmi, puoi fare una donazione tramite PayPal [cliccando qui](%s)\. *Grazie\!*"%str(DONATION)
    update.message.reply_text(donation_msg, parse_mode="MarkdownV2", disable_web_page_preview=True)

def nocmd_message(update, context):
    update.message.reply_text("Comando non riconosciuto: scegli tra /start , /ultimo e /dona")

def error(update, context):
    # Log Errors caused by Updates.
    logging.warning('Update "%s" caused error "%s"', update, context.error)


if useDB:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')

signal.signal(signal.SIGTERM, handle_stop)
signal.signal(signal.SIGINT, handle_stop)

urllib.request.urlopen(RESETBOT)

bot = telegram.Bot(TOKEN)
upd = Updater(TOKEN, use_context=True)
disp = upd.dispatcher

disp.add_handler(CommandHandler("start", start_message))
disp.add_handler(CommandHandler("ultimo", last_post_message))
disp.add_handler(CommandHandler("dona", donation_message))
disp.add_handler(MessageHandler(Filters.text, nocmd_message))

disp.add_error_handler(error)

upd.start_polling()

if useDB:
    last_timestamp, last_message = fromDBToVar()            # load the timestamp from old epochs
    last_md5 = compute_md5(last_message)
else:
    last_timestamp, last_message = fromFileToVar()          # load the timestamp from old epochs
    last_md5 = compute_md5(last_message)
logging.info("Recovered last state, last timestamp: "+str(last_timestamp))

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

