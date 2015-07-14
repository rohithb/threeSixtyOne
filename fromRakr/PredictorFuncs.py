from predictor.models import DepWords
from feedReader.mongoFunctions import Mongo
from bs4 import BeautifulSoup
from nltk.corpus import stopwords
from nltk.stem.wordnet import WordNetLemmatizer
from math import ceil, sqrt
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)


class PredictorFuncs:

    def __init__(self):
        '''
        Initialise mongodb connection
        '''
        self.mongo = Mongo()

    def removeStopWords(self, splitText):
        modified_stopwords = stopwords.words('english')
        modified_stopwords.extend(('[...]','.read','read','more…', '…','more...','more.read'))
        filtered_words = [
            w for w in splitText if not w in modified_stopwords]
        return filtered_words

    def stemWords(self, sent, rmStopWords=True):
        sent = sent.split()
        if(rmStopWords == True):
            sent = self.removeStopWords(sent)
        retSent = []
        for word in sent:
            retSent.append(WordNetLemmatizer().lemmatize(word, 'v'))
        sent = " ".join(retSent)
        return sent

    def processAllExistingFeeds(self):
        allFeeds = self.mongo.selectUnProcessedFeeds()
        for entry in allFeeds:
            depValues = self.classify(entry['feed'])
            logger.info('control back in processfn')
            if depValues != 0:
                self.mongo.updateDepValues(entry['_id'], depValues)

    def calculateWeight(self, wordsInDepList, sentence, index):
        depList = []
        tempWts = {}
        try:
            if index >= 2:
                sentence[index - 2].replace('.', '')
                sentence[index - 2].replace(',', '')
                if sentence[index - 2].isalnum():
                    depList.append(wordsInDepList.get(sentence[index - 2], 0))
            else:
                depList.append(0)
        except IndexError:
            depList.append(0)
        try:
            if index >= 1:
                sentence[index - 1].replace('.', '')
                sentence[index - 1].replace(',', '')
                if sentence[index - 1].isalnum():
                    depList.append(wordsInDepList.get(sentence[index - 1], 0))
            else:
                depList.append(0)
        except IndexError:
            depList.append(0)
        try:
            sentence[index + 1].replace('.', '')
            sentence[index + 1].replace(',', '')
            if sentence[index + 1].isalnum():
                depList.append(wordsInDepList.get(sentence[index + 1], 0))
        except IndexError:
            depList.append(0)
        try:
            sentence[index + 2].replace('.', '')
            sentence[index + 2].replace(',', '')
            if sentence[index + 2].isalnum():
                depList.append(wordsInDepList.get(sentence[index + 2], 0))
        except IndexError:
            depList.append(0)
        for entry in depList:
            if (entry != 0):
                for item in entry:
                    try:
                        tempWts[item['category']] += item['value']
                    except KeyError:
                        tempWts[item['category']] = item['value']
        return tempWts

    def addToDepList(self, wordsInDepList, depValues, sentList):
        for sentence in sentList:
            sentence = sentence.split()
            for index, word in enumerate(sentence):
                tempWts = self.calculateWeight(wordsInDepList, sentence, index)
                if tempWts:
                    normFactor = max(tempWts.values())
                    normFactor = ceil(normFactor)
                for item in tempWts:
                    category = item
                    value = tempWts[item]
                    value = value / normFactor
                    if value > 1:
                        assert False
                    #logger.info(word + ' ' + category + ' ' + str(value))
                    try:
                        depentry = DepWords.objects.get(
                            word=word, category=category)
                        oldValue = depentry.value
                        value = 0.16 * value + 0.84 * oldValue
                        if(value > 1):
                            value = value / normFactor
                        depentry.save()
                    except DepWords.DoesNotExist:
                        depentry = DepWords(
                            word=word, value=value, samples=-1, category=category)
                        depentry.save()

    def classify(self, feed):
        title = feed['title']
        try:
            content = feed['summary_detail']['value']
        except:
            content = feed['summary']
        tags = []
        try:
            temp = feed['tags']
            for tag in temp:
                tags.append(tag['term'])
        except KeyError:
            pass
        soup = BeautifulSoup(content)
        text = soup.getText()
        text = text.lower()
        text = text.replace('.',' . ')
        spChars = '~`!@#$%^&*()_-—+=[]{}|:?;"\'\\/>,<“”’‘»…' #all special char except '.'
        text = ''.join(c for c in text if c  not in spChars)
        text = self.stemWords(text)
        sentList = text.split('.')
        depValues = {
            "automobile": 0.0,
            "bussiness": 0.0,
            "fashion": 0.0,
            "food": 0.0,
            "health": 0.0,
            "history": 0.0,
            "movie": 0.0,
            "music": 0.0,
            "real-estate": 0.0,
            "science": 0.0,
            "sports": 0.0,
            "technology": 0.0,
            "travel": 0.0
        }
        wordToAddInDepList = {}
        for sentence in sentList:
            sentence = sentence.split()
            for word in sentence:
                depEntries = DepWords.objects.filter(word=word)
                if depEntries:
                    for entry in depEntries:
                        depValues[entry.category] = depValues.get(
                            entry.category, 0) + entry.value
                        # Calculate new dependancy values
                        try:
                            wordToAddInDepList[entry.word].append(
                                {'category': entry.category, 'value': entry.value})
                        except KeyError:
                            wordToAddInDepList[entry.word] = []
                            wordToAddInDepList[entry.word].append(
                                {'category': entry.category, 'value': entry.value})
        # normalize depValues
        normFactor = max(depValues.values())
        normFactor = ceil(normFactor)
        if normFactor == 0:
            return 0
        for entry in depValues:
            depValues[entry] = depValues[entry] / normFactor
        self.addToDepList(
            wordToAddInDepList, depValues, sentList)
        return depValues

    def euclideanDist(self, userVals , postVals):
        distSqare = 0
        for entry in userVals:
            distSqare += (userVals[entry]-postVals[entry])**2
        dist = sqrt(distSqare)
        normalizedDist = dist / sqrt(len(userVals))
        return normalizedDist

    def calculateUserPostDist(self, user_id):
        user = self.mongo.selectUser(user_id)
        user_dep = user.get('depValues')
        processedFeeds = self.mongo.selectProcessedFeeds(user_id)
        for feed in processedFeeds:
            feed_dep = feed.get('depValues')
            prefValue = self.euclideanDist(user_dep, feed_dep)
            pref = {"user_id" : user_id , "value" : prefValue}
            feed['pref'][str(user_id)] = prefValue
            self.mongo.updateUserPref(feed['_id'], feed['pref'])