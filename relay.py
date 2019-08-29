import json
import yaml
import inspect
import traceback
import os
import time
import requests
import schedule

import ESI
import notifier

from pathlib import Path
from datetime import datetime
from datetime import timezone

import mysql.connector as DatabaseConnector

def dataFile():

    filename = inspect.getframeinfo(inspect.currentframe()).filename
    path = os.path.dirname(os.path.abspath(filename))
    
    dataLocation = str(path)
    
    return(dataLocation)

if Path(dataFile() + "/config/config.json").is_file():

    with open(dataFile() + "/config/config.json", "r") as configFile:
        configData = json.load(configFile)
        
        databaseInfo = configData["Database"]
        appInfo = configData["App"]
    
else:
    raise Warning("Configuration file has not been generated!")
    
with open(dataFile() + "/resources/data/geographicInformation.json", "r") as geographyFile:
    geographicInformation = json.load(geographyFile)
        
with open(dataFile() + "/resources/data/TypeIDs.json", "r") as typeIDFile:
    typeIDList = json.load(typeIDFile)

def startRelay():
    try:
        charactersChecked = 0
        
        pingTypes = {"slack_webhook":{"everyone":"<!channel>","here":"<!here>","none":""}, "discord_webhook":{"everyone":"@everyone","here":"@here","none":""}}
        
        currentTime = datetime.now()
        readableCurrentTime = currentTime.strftime("%d %B, %Y - %H:%M:%S EVE")
        print("[" + readableCurrentTime + "] Monitoring Started!")

        sq1Database = DatabaseConnector.connect(user=databaseInfo["Username"], password=databaseInfo["Password"], host=databaseInfo["Server"] , port=int(databaseInfo["Port"]), database=databaseInfo["Name"])

        firstCursor = sq1Database.cursor(buffered=True)

        relayQuery = ("SELECT * FROM relays")

        firstCursor.execute(relayQuery)

        for (relayName, relayID, relayCorpID, relayCorp, relayRefreshToken, relayAllianceID, relayAlliance, relayRoles) in firstCursor:

            accessToken = ESI.getAccessToken(appInfo, relayRefreshToken)
            
            if accessToken != "Bad Token":
                notificationDict = ESI.getNotifications(relayID, accessToken)
                
                secondCursor = sq1Database.cursor(buffered=True)
                configurationQuery = ("SELECT * FROM configurations WHERE targetid = {targetid}".format(targetid=relayID))
                secondCursor.execute(configurationQuery)
                
                for (configurationID, configurationType, configurationChannel, configurationURL, configurationPingType, configurationTargetName, configurationTargetID, configurationWhitelist, configurationTimestamp, configurationAlliance, configurationAllianceID, configurationCorporation, configurationCorporationID) in secondCursor:
                
                    whitelist = json.loads(configurationWhitelist)
                    
                    for notifications in notificationDict:
                    
                        if "timestamp" not in notifications:
                            print(str(notificationDict))
                    
                        notificationTime = datetime.strptime(notifications["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
                        timestamp = int(notificationTime.replace(tzinfo=timezone.utc).timestamp())
                        readableNotificationTime = datetime.utcfromtimestamp(timestamp).strftime("%d %B, %Y - %H:%M:%S EVE")
                                        
                        if notifications["type"] in whitelist and configurationTimestamp < timestamp:
                            thirdCursor = sq1Database.cursor(buffered=True)
                            configurationQuery = ("SELECT * FROM notifications WHERE (id = {notificationID} AND configurationid = '{configurationID}')".format(notificationID=notifications["notification_id"], configurationID=configurationID))
                            thirdCursor.execute(configurationQuery)
                            
                            knownTestList = []
                            
                            for testers in thirdCursor:
                                knownTestList.append(testers)
                                
                            if not knownTestList:
                            
                                fullDetails = yaml.load(notifications["text"], Loader=yaml.FullLoader)
                                toCall = notifier.findFunction(notifications["type"])    

                                pinger = pingTypes[configurationType][configurationPingType]
                            
                                if configurationType == "discord_webhook":
                                    bolders = "**"
                                    
                                    messageToPost = toCall(readableNotificationTime, fullDetails, typeIDList, geographicInformation, bolders, pinger, accessToken)
                                    
                                    notifier.postToDiscord(messageToPost, configurationURL)
                                
                                else:
                                    bolders = "*"
                                    
                                    messageToPost = toCall(readableNotificationTime, fullDetails, typeIDList, geographicInformation, bolders, pinger, accessToken)
                                    
                                    notifier.postToSlack(messageToPost, configurationURL)
                                
                                fourthCursor = sq1Database.cursor(buffered=True)                        
                                insertion = ("INSERT INTO notifications (timestamp, type, configurationid, id) VALUES ({timestamp}, '{type}', '{configurationid}', {id})").format(timestamp=timestamp, type=notifications["type"], configurationid=configurationID, id=int(notifications["notification_id"]))
                                fourthCursor.execute(insertion)
                                
                                sq1Database.commit()
                                
                                print(notifications["type"] + " Notification Sent for " + configurationCorporation + "!")
            
                charactersChecked += 1
            
            else:
                print("Failed to get access token for " + relayName)
            
        sq1Database.close()
        
        currentTime = datetime.now()
        readableCurrentTime = currentTime.strftime("%d %B, %Y - %H:%M:%S EVE")
        print("[" + readableCurrentTime + "] Monitoring Concluded!\n" + str(charactersChecked) + " characters checked!\n\n")
        
    except:
        traceback.print_exc()

schedule.every(150).seconds.do(startRelay)
        
while True:
    schedule.run_pending()
    time.sleep(1)