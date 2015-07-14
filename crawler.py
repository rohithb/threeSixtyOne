import urllib3
from mongoFunctions import MongoFns
import threading
from bs4 import BeautifulSoup


class CrawlerThread(threading.Thread):
    def __init__(self, binarySemaphore, url):
        self.binarySemaphore = binarySemaphore
        self.url = url
        self.threadId = hash(self)
        self.mongo = MongoFns()
        self.http = urllib3.PoolManager()
        threading.Thread.__init__(self)

    def run(self):
        try:
            print('Getting %s' % self.url)
            response = self.http.request('GET', self.url)
        except:
            response.status = 400
        if response.status == 200:
            soup = BeautifulSoup(response.data.decode('utf-8'), "html.parser")
            try:
                feedUrl = soup.find('link', rel="alternate", type="application/rss+xml")
                if ('href' in dict(feedUrl)):
                    feedUrl = feedUrl['href']
            except:
                feedUrl = ''
            atags = soup.findAll('a')
            links = []
            for tag in atags:
                if ('href' in dict(tag.attrs)):
                    links.append(tag['href'])
            print('%s : %s' % (self.threadId, len(links)))
            # self.binarySemaphore.acquire()
            print('%s acquired lock' % self.threadId)
            self.mongo.saveCrawl(self.url, feedUrl, response.data, links)
            print('%s written to db' % self.threadId)
            # self.binarySemaphore.release()
            print('%s lock released' % self.threadId)

            for link in links:
                CrawlerThread(self.binarySemaphore, link).start()


if __name__ == "__main__":
    binarySemaphore = threading.Semaphore(1)
    urls = ["http://us.lifehacker.com/", "http://techcrunch.com",
            "http://venturebeat.com/"]
    for url in urls:
        CrawlerThread(binarySemaphore, url).start()
