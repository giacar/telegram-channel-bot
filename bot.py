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
from telegram import InputMediaPhoto
import telegram

from discord_webhook import DiscordWebhook, DiscordEmbed

logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] %(message)s', datefmt='%Y-%m-%d,%H:%M:%S', level=logging.INFO)

logging.getLogger('facebook_scrapper').setLevel(logging.ERROR)
facebook_scraper.enable_logging(logging.ERROR)

FEEDRSS = os.environ.get('FEED_RSS', None)

DONATION = os.environ.get('DONATION', None)

TOKEN = os.environ.get('TOKEN_BOT', None)
CHANNEL = os.environ.get('CHANNEL_ID', None)
RESETBOT = "https://api.telegram.org/bot"+str(TOKEN)+"/setWebhook?url="
DATABASE_URL = os.environ.get('DATABASE_URL', None)

DISCORD_URL = os.environ.get('DISCORD_URL', None)
DISCORD_AUTHOR_URL = os.environ.get('DISCORD_AUTHOR_URL', None)
DISCORD_AUTHOR_ICON = os.environ.get('DISCORD_AUTHOR_ICON', None)

webhook = DiscordWebhook(url=DISCORD_URL)

# Initialize value
useCredentials = False      # FB credential (True) or cookies (False)
useRSS = False              # Enable scraping using RSS.app
useFBScraping = True        # Enable FB scraping (facebook-scraper module)
useDB = True                # Use DB (True) or local file (False) to store state

# compute md5 fingerprint of an input string
def compute_md5(input):
    return hashlib.md5(input.encode()).hexdigest()

# clean message from ... used by Facebook
def clean_msg(input):
    return input.replace("...", "", 1)

# last post class
class LastPost:
    def __init__(self, pid, msg, ts, imgs, iids, scraped):
        self.post_id = pid
        self.message = msg
        self.md5 = compute_md5(clean_msg(msg))
        self.timestamp = ts
        self.images = imgs
        self.image_ids = iids
        self.isScraped = scraped

# State
last_post = LastPost(0, '', 0, [], [], True)


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


# Signal capture handler
def handle_stop(sig, frame):
    logging.info("Updating state before to exit...")
    
    if useDB:
        check_conn()

        cur = conn.cursor()
        
        cur.execute("SELECT * FROM state;")
        if len(cur.fetchall()) == 0:
            cur.execute("INSERT INTO state VALUES (%s,%s,%s,%s,%s);", (str(last_post.post_id),str(last_post.message),str(last_post.timestamp),str(' '.join(map(str,last_post.images))),str(' '.join(map(str,last_post.image_ids)))))
        else:
            cur.execute("UPDATE state SET ts=%s, msg=%s, post_id=%s, img_urls=%s, img_ids=%s;", (str(last_post.post_id),str(last_post.message),str(last_post.timestamp),str(' '.join(map(str,last_post.images))),str(' '.join(map(str,last_post.image_ids)))))

        conn.commit()
        
        cur.close()
        conn.close()
    else:
        with open("last_state.txt", "w") as file:
            file.write(str(last_post.post_id)+'\n'+str(last_post.message)+'\n'+str(last_post.timestamp)+'\n'+str(' '.join(map(str,last_post.images)))+'\n'+str(' '.join(map(str,last_post.image_ids))))

    logging.info("Last state is updated")

    upd.stop()
    logging.info("Stop polling, now I can exit safely")
    
    # pubblish on my Discord Channel
    reboot_msg = "Il dyno si è fermato."
    embed = DiscordEmbed(title='🔴️ Stato 🔴️', description=reboot_msg)
    embed.set_author(name='Comune di Castel Madama Bot', url=DISCORD_AUTHOR_URL, icon_url=DISCORD_AUTHOR_ICON)
    webhook.add_embed(embed)
    webhook.execute(remove_embeds=True)

    sys.exit(0)


# export last state in the database
def fromVarToDB():
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM state;")
    if len(cur.fetchall()) == 0:
        cur.execute("INSERT INTO state VALUES (%s,%s,%s,%s,%s);", (str(last_post.post_id),str(last_post.message),str(last_post.timestamp),str(' '.join(map(str,last_post.images))),str(' '.join(map(str,last_post.image_ids)))))
    else:
        cur.execute("UPDATE state SET ts=%s, msg=%s, post_id=%s, img_urls=%s, img_ids=%s;", (str(last_post.post_id),str(last_post.message),str(last_post.timestamp),str(' '.join(map(str,last_post.images))),str(' '.join(map(str,last_post.image_ids)))))

    conn.commit()
    cur.close()


# import last state from the database
def fromDBToVar():
    check_conn()

    cur = conn.cursor()
    
    cur.execute("SELECT * FROM state;")
    rows = cur.fetchall()

    pid = 0
    msg = ""
    ts = 0
    iurl = [] 
    iid = []

    for row in rows:
        pid = int(row[0])
        msg = str(row[1])
        ts = int(row[2])
        iurl = [str(el) for el in row[3].strip().split()]
        iid = [int(el or 0) for el in row[4].strip().split()]

    cur.close()
    return pid, msg, ts, True if ts>0 else False, iurl, iid


# export last state to local file
def fromVarToFile():
    with open("last_state.txt", "w") as file:
        file.write(str(last_post.post_id)+'\n'+str(last_post.message)+'\n'+str(last_post.timestamp)+'\n'+str(' '.join(map(str,last_post.images)))+'\n'+str(' '.join(map(str,last_post.image_ids))))


# export last state from local file
def fromFileToVar():
    pid = 0
    msg = ""
    ts = 0
    iurl = []
    iid = []
    
    try:
        with open("last_state.txt", "r") as file:
            pid = int(file.readline().strip())
            msg = str(file.readline().strip())
            ts = int(file.readline().strip())
            iurl = [str(el) for el in file.readline().strip().split()]
            iid = [int(el or 0) for el in file.readline().strip().split()]
    
    except FileNotFoundError:
        logging.error("File last_state.txt not found, default values applied")
        pass
    
    return pid, msg, ts, True if ts>0 else False, iurl, iid


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
    if isinstance(s, int) and s == -1:
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
            posts = get_posts(CHANNEL[1:], pages=2, credentials=(os.environ.get('FB_EMAIL', None), os.environ.get('FB_PASS', None)))
        else:
            posts = get_posts(CHANNEL[1:], pages=2, cookies="cookies.txt")

        for post in posts:
            if post['text'] != None and post['time'] != None:
                post_id = post['post_id'] if post['post_id'] != None else 0
                images = post['images'] if post['images'] != None else []
                image_ids = post['image_ids'] if post['image_ids'] != None else []
                
                list_data.append([ post_id, clean_msg(post['text']), int(datetime.timestamp(post['time'])), images, image_ids ])
        
        if len(list_data) == 0:
            return -1

        list_data = sorted(list_data, key=itemgetter(0), reverse=True)      # sorting for post_id in descending order

        df_scraped = pd.DataFrame(columns = ['post_id', 'text', 'timestamp', 'images', 'image_ids'])
        df_scraped['images'] = df_scraped['images'].astype('object')
        df_scraped['image_ids'] = df_scraped['image_ids'].astype('object')

        column_list = df_scraped.columns.values.tolist()
        for j in range(len(column_list)) :
            df_scraped[column_list[j]] = [list_data[i][j] for i in range(len(list_data))]

        return df_scraped
    
    except Exception as e:
        logging.error(traceback.format_exc())
        return -1


# send message to Telegram Channel
def sendMessage(sendOnlyPhoto):
    logging.info("Sending new post to Channel...")
    sent = True

    if last_post.message == "":
        if len(last_post.images) == 0:
            sent = False
            logging.info("... empty message, not sent!")
    
        elif len(last_post.images) == 1:
            bot.send_photo(CHANNEL, last_post.images[0], disable_notification=True)
        
        else:
            bot.send_media_group(CHANNEL, [InputMediaPhoto(str(imgurl)) for imgurl in last_post.images], disable_notification=True)
    
    else:
        tg_msg = None
        if not sendOnlyPhoto:
            msg = last_post.message
            if last_post.post_id :          # add facebook link if post_id present
                msg = msg+"\n\n"+"https://www.facebook.com/"+CHANNEL[1:]+"/posts/"+str(last_post.post_id)
            tg_msg = bot.send_message(CHANNEL, msg)
        
        if len(last_post.images) == 1:
            bot.send_photo(CHANNEL, str(last_post.images[0]), reply_to_message_id=tg_msg.message_id, disable_notification=(True if not sendOnlyPhoto else False))
        
        elif len(last_post.images) > 1:
            bot.send_media_group(CHANNEL, [InputMediaPhoto(str(imgurl)) for imgurl in last_post.images], reply_to_message_id=tg_msg.message_id, disable_notification=(True if not sendOnlyPhoto else False))
        
    if sent: logging.info("... sent!")

    return sent


# check and send new post found RSS and/or FB scraping 
def checkAndSendNewPost():
    global last_post

    isNewPost = False
    isNeverSend = False
    sendOnlyPhoto = False
    
    '''
    # check last RSS post
    head_rss_ts = int(datetime.timestamp(parser.parse(df["Date"][0])))
    if useRSS and head_rss_ts > last_post.timestamp : # no check on post_id since not present
        isNewPost = True
        logging.info("New post detected!")
        last_post.timestamp = head_rss_ts
        detected_msg = clean_msg(df["Description"][0])
        detected_md5 = compute_md5(detected_msg)
        if last_post.md5 != detected_md5:
            # update state
            last_post.message = detected_msg
            last_post.md5 = detected_md5
            last_post.post_id = 0
            last_post.isScraped = False
            last_post.images = []
            isNeverSend = True
    '''
    
    # check last scraped post 
    if useFBScraping and (not (isinstance(df_scraped, int) and df_scraped == -1)):
        head_scraped_pid = int(df_scraped["post_id"][0])
        head_scraped_ts = int(df_scraped["timestamp"][0])
        
        if head_scraped_pid > last_post.post_id :
            isNewPost = True
            logging.info("New post detected!")
            last_post.post_id = head_scraped_pid
            last_post.timestamp = head_scraped_ts
            detected_msg = clean_msg(df_scraped['text'][0])
            detected_md5 = compute_md5(detected_msg)
            if last_post.md5 != detected_md5:
                # update state
                last_post.message = detected_msg
                last_post.md5 = detected_md5
                last_post.isScraped = True
                last_post.images = df_scraped['images'][0]
                last_post.image_ids = df_scraped['image_ids'][0]
                isNeverSend = True
            elif not last_post.isScraped:
                # update msg post_id since prev RSS copy = 0
                last_post.isScraped = True
                last_post.images = df_scraped['images'][0]
                last_post.image_ids = df_scraped['image_ids'][0]
            elif last_post.image_ids.sort() != df_scraped['image_ids'][0].sort():
                # same or empty text but different images
                last_post.image_ids = df_scraped['image_ids'][0]
                isNeverSend = True
                sendOnlyPhoto = True
    
    if isNewPost:
        logging.info("New values of last post: id = "+str(last_post.post_id)+"timestamp = "+str(last_post.timestamp))
        if useDB:
            fromVarToDB()
            logging.info("New state stored in the database")
        else:
            fromVarToFile()
            logging.info("New state stored in the local file")
        
        if isNeverSend:
            sendMessage(sendOnlyPhoto)
        else:
            logging.info("Duplicated post, not sent")


# some handling message functions for the different bot commands
def start_message(update, context):
    logging.info("Command /start from chat_id: " + str(update.message.chat.id))
    update.message.reply_text("Benvenuto! Questo bot è utile per la pubblicazione dei messaggi nel canale.")
    update.message.reply_text("Se vuoi leggere l'ultimo post pubblicato, usa il comando /ultimo")
    update.message.reply_text("Se vuoi fare una piccola donazione, usa il comando /dona")

def last_post_message(update, context):
    if last_post.message == "":
        if len(last_post.images) == 0:
            update.message.reply_text("Mi dispiace ma l'ultimo post al momento non è disponibile. Riprova più tardi.")

        elif len(last_post.images) == 1:
            update.message.reply_photo(str(last_post.images[0]), disable_notification=True)
        
        else:
            update.message.reply_media_group([InputMediaPhoto(str(imgurl)) for imgurl in last_post.images], disable_notification=True)
    
    else:
        msg = last_post.message
        if last_post.post_id :          # add facebook link if post_id present
            msg = msg+"\n\n"+"https://www.facebook.com/"+CHANNEL[1:]+"/posts/"+str(last_post.post_id)
        tg_msg = update.message.reply_text(msg)
        
        if len(last_post.images) == 1:
            update.message.reply_photo(str(last_post.images[0]), reply_to_message_id=tg_msg.message_id, disable_notification=True)
        
        elif len(last_post.images) > 1:
            update.message.reply_media_group([InputMediaPhoto(str(imgurl)) for imgurl in last_post.images], reply_to_message_id=tg_msg.message_id, disable_notification=True)


def donation_message(update, context):
    donation_msg = "Se il bot ti piace e vuoi supportarmi, puoi fare una donazione tramite PayPal [cliccando qui](%s)\. *Grazie\!*"%str(DONATION)
    update.message.reply_text(donation_msg, parse_mode="MarkdownV2", disable_web_page_preview=True)

def nocmd_message(update, context):
    update.message.reply_text("Comando non riconosciuto: scegli tra /start , /ultimo e /dona")

def error(update, context):
    # Log Errors caused by Updates.
    logging.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    # global vars
    global conn
    global bot
    global upd
    global disp
    global last_post
    global df
    global df_scraped

    # pubblish on my Discord Channel
    reboot_msg = "Il dyno si è avviato."
    embed = DiscordEmbed(title='✅️ Stato ✅️', description=reboot_msg)
    embed.set_author(name='Comune di Castel Madama Bot', url=DISCORD_AUTHOR_URL, icon_url=DISCORD_AUTHOR_ICON)
    webhook.add_embed(embed)
    webhook.execute(remove_embeds=True)

    # create cookies.txt file using env var value
    if not useCredentials:
        with open("cookies.txt", "w") as file:
            file.write(str(os.environ.get("COOKIES", None)))

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
        last_post.post_id, last_post.message, last_post.timestamp, last_post.isScraped, last_post.images, last_post.image_ids = fromDBToVar()    # load the old epoch's state
        last_post.md5 = compute_md5(last_post.message)
    else:
        last_post.post_id, last_post.message, last_post.timestamp, last_post.isScraped, last_post.images, last_post.image_ids = fromFileToVar()  # load the old epoch's state
        last_post.md5 = compute_md5(last_post.message)
    logging.info("Recovered last state, post_id = "+str(last_post.post_id)+", timestamp = "+str(last_post.timestamp))

    # Initialize tables
    df = initTable()
    while isinstance(df, int) and df==-1:
        time.sleep(10)
        df = initTable()
    df_scraped = initScrapedTable()
    while isinstance(df_scraped, int) and df_scraped==-1:
        time.sleep(10)
        df_scraped = initScrapedTable()

    print(df_scraped)

    logging.info("Table initialized")
    logging.info("Bot is ready")

    i = 0
    j = 0

    checkAndSendNewPost()

    # Loop
    while (True):
        # check each 30 minutes
        if i==30:
            i=0

            df = initTable()
            if isinstance(df, int) and df == -1:
                time.sleep(10)
                continue

            df_scraped = initScrapedTable()
            if isinstance(df_scraped, int) and df_scraped == -1:
                time.sleep(10)
                continue

            checkAndSendNewPost()

        #log each 1 hour
        if j==60:
            j=0
            logging.info("Bot is active, post_id = "+str(last_post.post_id)+", timestamp = "+str(last_post.timestamp))

        i+=1
        j+=1
        time.sleep(60)


if __name__ == "__main__":
    main()
