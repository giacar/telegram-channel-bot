# Facebook Page Scaper Bot
[![it](https://img.shields.io/badge/lang-it-green.svg)](https://github.com/giacar/telegram-channel-bot/blob/main/README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/giacar/telegram-channel-bot/blob/main/README.en.md)

Facebook Page Scaper Bot è un bot di Telegram che permette di fare scraping e pubblicare gli ultimi post di una specifica pagina Facebook su un canale Telegram. Per ottenerli, sfrutta sia il servizio (RSS.app)[https://www.rss.app] che una libreria [PIP](https://pypi.org/project/facebook-scraper/). Si consiglia di utilizzare i cookie di accesso ad un account Facebook (altrimenti Facebook può bloccarlo) quando si utilizza la libreria PIP. Inoltre permette di interagire con sé stesso per ottenere l'ultimo post pubblicato.

## Linguaggio
L'applicazione è scritta in Python, in particolare usando la libreria API [Telegram](https://python-telegram-bot.readthedocs.io/) per poter sfruttare tutte le funzioni messe a disposizione. Inoltre c'è anche la possibilità di scegliere tra un database Postgres o un file locale per memorizzare alcune informazioni essenziali per il suo funzionamento. Per lo scraping, viene usato il servizio [RSS.app](https://www.rss.app) e la libreria [PIP](https://pypi.org/project/facebook-scraper). È presente un log tramite webhook [Discord](https://pypi.org/project/discord-webhook).

## Funzionalità
Il bot permette di sfruttare le seguenti funzionalità:
* Pubblicazione dei nuovi post Facebook con foto o post con sole foto su un canale Telegram.
* Interazione diretta con il bot per ottenere l'ultimo post pubblicato.
* Possibilità di personalizzare la sorgente dati scegliendo tra il feed RSS, la libreria pip o entrambe.

## To Do
* ~~Integrare le foto nei post e il supporto ai post con sole foto.~~
* ~~Integrare i video nei post e il supporto ai post con soli video.~~\
\
Per altri suggerimenti o segnalazioni è possibile aprire un issue da [qui](https://github.com/giacar/telegram-channel-bot/issues).

## Bug noti
* Possibilità di avere post duplicati: alcune misure sono state prese ma il rischio resta.

## Donazione
Se il bot ti è stato utile e vuoi supportarmi, puoi farlo facendomi una donazione PayPal [cliccando qui](https://www.paypal.me/gianmarcocariggi). Grazie per il supporto!
