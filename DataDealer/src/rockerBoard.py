#!/usr/local/bin/python
#---------------------------------------------------------------------------------------------------
# Collects all the necessary data to generate rankings for all datasets in the AnalysisOps space.
#---------------------------------------------------------------------------------------------------
import sys, os, math, datetime
import phedexData, popDbData

class rockerBoard():
	def __init__(self):
		phedexCache = os.environ['DATA_DEALER_PHEDEX_CACHE']
		popDbCache = os.environ['DATA_DEALER_POP_DB_CACHE']
		cacheDeadline = int(os.environ['DATA_DEALER_CACHE_DEADLINE'])
		self.rankingCachePath = os.environ['DATA_DEALER_RANKING_CACHE']
		self.threshold = int(os.environ['DATA_DEALER_THRESHOLD'])
		self.budget = os.environ['DATA_DEALER_BUDGET']
		self.phedexData = phedexData.phedexData(phedexCache, cacheDeadline)
		self.popDbData = popDbData.popDbData(popDbCache, cacheDeadline)

#===================================================================================================
#  H E L P E R S
#===================================================================================================
	def weightedChoice(self, choices):
		total = sum(w for c, w in choices.iteritems())
		r = random.uniform(0, total)
		upto = 0
		for c, w in choices.iteritems():
			if upto + w > r:
				return c
			upto += w

	def getPopularity(self, datasetName):
		popularity = 0
		today = datetime.date.today()
		for i in range(1, 8):
			date = today - datetime.timedelta(days=i)
			cpuh = self.popDbData.getDatasetCpus(datasetName, date.strftime('%Y-%m-%d'))
			popularity += cpuh**(1/i)
		return popularity

	def rankingCache(self, datasetRankings, siteRankings):
		if not os.path.exists(self.rankingCachePath):
			os.makedirs(self.rankingCachePath)
		cacheFile = "%s/%s.db" % (self.rankingCachePath, "rankingCache")
		if os.path.isfile(cacheFile):
			os.remove(cacheFile)
		rankingCache = sqlite3.connect(cacheFile)
		with rankingCache:
			cur = rankingCache.cursor()
			cur.execute('CREATE TABLE IF NOT EXISTS Datasets (DatasetName TEXT UNIQUE, Rank REAL)')
			cur.execute('CREATE TABLE IF NOT EXISTS Sites (SiteName TEXT UNIQUE, Rank REAL)')
			for datasetName, rank in datasetRankings.items():
				cur.execute('INSERT INTO Datasets(DatasetName, Rank) VALUES(?, ?, ?)', (datasetName, rank))
			for siteName, rank in siteRankings.items():
				cur.execute('INSERT INTO Sites(SiteName, Rank) VALUES(?, ?, ?)', (siteName, rank))

	def getDatasetRankings(self, datasets):
		alphaValues = dict()
		for datasetName in datasets:
			nReplicas = self.phedexData.getNumberReplicas(datasetName)
			sizeGb = self.phedexData.getDatasetSize(datasetName)
			popularity = getPopularity(datasetName)
			alpha = popularity/float(nReplicas*sizeGb)
			alphaValues[datasetName] = alpha
		mean = (1/len(alphaValues))*sum(v for v in alphaValues.values())
		datasetRankings = dict()
		for k, v in alphaValues.items():
			dev = v - mean
			datasetRankings[k] = dev
		return datasetRankings

	def getSiteRankings(self, sites, datasetRankings):
		siteRankings = dict()
		for siteName in sites:
			datasets = self.phedexData.getDatasetsAtSite(siteName)
			rank = sum(datasetRankings[s] for d in datasets)
			siteRankings[siteName] = rank
		return siteRankings

	def getNewReplicas(self, datasetRankings, siteRankings):
		subscriptions = dict()
		sizeSubscribedGb = 0
		for siteName, rank in siteRankings.items():
			if rank < 0:
				siteRankings[siteName] = -rank
			else:
				del siteRankings[siteName]
		while (sizeSubscribedGb < self.budget and datasetRankings):
			datasetName = max(datasetRankings.iteritems(), key=operator.itemgetter(1))[0]
			del datasetRankings[datasetName]
			siteName = selection.weightedChoice(siteRankings)
			if siteName in subscriptions:
				subscriptions[siteName].append(datasetName)
			else:
				subscriptions[siteName] = [datasetName]
		return subscriptions

#===================================================================================================
#  M A I N
#===================================================================================================
	def rba(self, datasets, sites):
		datasetRankings = self.getDatasetRankings(datasets)
		siteRankings = self.getSiteRankings(sites, datasetRankings)
		self.rankingCache(datasetRankings, siteRankings)
		subscriptions = self.getNewReplicas(datasetRankings, siteRankings)
		return subscriptions
