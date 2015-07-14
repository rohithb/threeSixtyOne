from pymongo import MongoClient
from datetime import datetime


class MongoFns:
    def __init__(self):
        self.client = MongoClient()
        self.db = self.client.three_sixty_one

    def saveCrawl(self, url, feedUrl, data, links):
        crawls = self.db.crawls
        crawl = {"url": url,
                 "feed_url": feedUrl,
                 "data": data,
                 "links": links,
                 "date": datetime.now()}
        crawls.insert_one(crawl)
