# Facebook Page Scaper Bot
[![it](https://img.shields.io/badge/lang-it-green.svg)](https://github.com/giacar/telegram-channel-bot/blob/main/README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/giacar/telegram-channel-bot/blob/main/README.en.md)

Facebook Page Scaper Bot is a Telegram bot that allows to scrape and pubblish last posts of a specific Facebook page in a Telegram channel. In order to get them, it exploits both [RSS.app](https://www.rss.app) service and a [PIP](https://pypi.org/project/facebook-scraper) library. It's recommended to use Facebook account login cookies (otherwise Facebook can block it) when PIP library is used. Moreover it allows to interact with itself in order to get the last pubblished post.

## Language
The application is written in Python, in particular using the [Telegram](https://python-telegram-bot.readthedocs.io) API library in order to take advantage of all the available functions. In addition there is also the possibility to choose between a Postgres database or a local file to store some essential information for the its functioning. For scraping, the service [RSS.app](https://www.rss.app) and the library [PIP](https://pypi.org/project/facebook-scraper) are used. There is a log via webhook [Discord](https://pypi.org/project/discord-webhook). Everything can be hosted on the [Heroku](https://www.heroku.com) platform.

## Functionality
The bot allows you to take advantage of the following features:
* Pubblishing of a new facebook post into a Telegram channel, including photos and photo-only post.
* Interaction with the bot in order to get last post.
* Possibility to customize the scraping choosing between RSS service, PIP library or both of them. 

## To Do
* ~~Integrate photos into posts and support photo-only posts.~~\
\
For other suggestions and reports you can open an issue from [here](https://github.com/giacar/telegram-channel-bot/issues).

# Known Bugs
* Possibility to have duplicated posts: some measures have been taken but the risk remains.

## Donation
If the bot was useful to you and you want to support me, you can do it by making me a PayPal donation [clicking here](https://www.paypal.me/gianmarcocariggi). Thank you for the support!
