from feedReader.models import SiteInfo
import feedparser
import hashlib
from feedReader.mongoFunctions import Mongo
from time import mktime
from datetime import datetime
from django.utils.html import strip_tags
import time
from bs4 import BeautifulSoup
#from urllib2 import Request, urlopen
import urllib3
import re


class ParsingFuncs:

    '''
    Contains all functions to get and parse the feeds
    '''

    def __init__(self):
        '''
        Initialise mongodb connection
        '''
        self.mongo = Mongo()

    def fetchFeeds(self):
        '''
        Fetches all the entries in the table siteInfo and fetches its feeds ..
        Stores to the database
        '''
        siteList = SiteInfo.objects.all()
        for site in siteList:
            modifiedStr = self.createLastModifiedStr(site.lastModified, site.etag)
            if modifiedStr is not None:
                feeds = feedparser.parse(site.feedUrl, modifiedStr)
            else:
                feeds = feedparser.parse(site.feedUrl)
            # find the last modified date. This value will be in feed.updated, feed.last_modified
            lastModified = self.findLastModifiedDate(feeds.feed)
            try:
                etag = feeds.feed.etag
            except:
                etag = None

            feedsHash = self.md5Feeds(feeds)  # calculating the hash of entire feeds
            if(site.feedHash == feedsHash):
                continue  # if no change in feeds ignore it.
            site.feedHash = feedsHash  # if changed save it in db
            if etag is None:
                site.lastModified = lastModified
            else:
                site.etag = etag
            site.save()
            for entry in feeds.entries:
                dt = datetime.fromtimestamp(mktime(entry.published_parsed))  # the format of published_parsed is not..
                entry['published_parsed'] = dt                              # compactible with mongodb
                try:
                    mediaContnet = entry['media_content']
                except:
                    mediaContnet = None
                try:
                    content = entry['content'][0]['value']
                except:
                    content = None
                entry['image_link'] = self.getImage(media_content=mediaContnet,
                                                    summary=entry['summary'],
                                                    content=content,
                                                    link=entry['link'])
                self.mongo.insertFeeds(entry, site.id)

    def allFeeds(self,user_id, lastDate=None):
        if lastDate is not None:
            return self.mongo.selectFeeds(user_id=user_id,dateOfLastItem=lastDate)
        return self.mongo.selectFeeds(user_id=user_id)

    def md5Feeds(self, feed):
        '''
        find md5 of feed
        '''
        md5 = hashlib.md5(str(feed).encode('utf-8'))
        return md5.hexdigest()

    def selectFeedById(self, id):
        return self.mongo.selectFeedById(id)

    def getSiteTitle(self, siteId):
        siteObject = SiteInfo.objects.filter(id=siteId)
        for site in siteObject:
            return site.title

    def getSummary(self, summary):
        summary1000wds = strip_tags(summary)
        summary1000wds = summary1000wds[:300] + "..."
        return summary1000wds

    def getFullPost(self, summaryDetail):
        post = strip_tags(summaryDetail)
        return post

    def createLastModifiedStr(self, last_modified=None, etag=None):
        modiStr = None
        if etag is not None:
            modiStr = "etag = " + str(etag)
        if last_modified is not None:
            modiStr = "modified = " + str(last_modified.utctimetuple())
        return modiStr

    def findLastModifiedDate(self, feed):
        try:
            last_modified = datetime.fromtimestamp(mktime(feed.updated_parsed))  # if updated date is present
        except:
            try:
                last_modified = datetime.fromtimestamp(mktime(feed.date_parsed))  # if date field is present
            except:
                try:
                    # if published_parsed is present
                    last_modified = datetime.fromtimestamp(mktime(feed.published_parsed))
                except:
                    structTime = time.localtime()
                    last_modified = datetime(*structTime[:6])
        return last_modified

    def getFullPostURLOpen(self, link, summary):
        http = urllib3.PoolManager()
        #req = Request(link, headers={'User-Agent': "ireadr"})
        try:
            page = http.request('GET', link)
            page = page.data
            #page = urlopen(req)
        except:
            page = None
        if page is not None:
            soup = BeautifulSoup(page)
            summary = summary[:25]
            # modify this like check match for entire summary.
            #if not found find a substring of length 50 and check again
            # if again not found then reduce the length and try again
            element = soup.find(text=re.compile(summary))
            post = element.findParent('div')
            return post
        return None

    def findImgsrcFromHtml(self, content):
        soup = BeautifulSoup(content)
        img_links = soup.findAll('img')
        if len(img_links) > 0:
            for link in img_links:
                try:
                    if link['height'] == '1' or link['width'] == '1':
                        continue
                    else:
                        return (link['src'])
                except:
                    return (link['src'])
        return None

    def getImage(self, media_content=None, summary=None, content=None, link=None):
        if media_content is not None:
            return (media_content[0]['url'])
        # if media_content is None
        if summary is not None:
            return (self.findImgsrcFromHtml(summary))
        # if no matching image is found in summary
        if content is not None:
            return (self.findImgsrcFromHtml(content))
        # if image is not found in content then fetch the original page and extract the image
        if link is not None:
            post = self.getFullPostURLOpen(link, summary)
            if post is not None:
                return(self.findImgsrcFromHtml(post))
        return None
