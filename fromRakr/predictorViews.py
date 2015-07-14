from django.shortcuts import render
from django.http import HttpResponse

from predictor.PredictorFuncs import PredictorFuncs

def preparePosts(request):
    predFuncs = PredictorFuncs()
    predFuncs.processAllExistingFeeds()
    return HttpResponse("True")

def calculatePref(request):
	user_id = request.user.id
	predFuncs = PredictorFuncs()
	predFuncs.calculateUserPostDist(user_id)
	return HttpResponse("True")