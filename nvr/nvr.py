import requests
from PIL import Image
from StringIO import StringIO
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import time
import xml.etree.ElementTree as et
import operator
import os, sys
import logging
import argparse
from pprint import pprint as pp
from pprint import pformat as pf


def writeCsv(alarms, filename, echo = False ):
    logging.info('writeCsv(,{},).alarms={}'.format(filename,len(alarms)))
    alarmsFile = open(filename, 'w')
    for i, alarm in enumerate(alarms):
        if i == 0:
            lastAlarm = alarms[-1]
            keys = lastAlarm.values.keys ()
            keys.sort()
            for i,key in enumerate(keys):
                col = "%s" % key
                if i < len(keys) - 1:
                    col  += ','
                alarmsFile.write(col)
                if echo:
                    print col,
            if echo:
                print
            alarmsFile.write('\n')
        for i,key in enumerate(keys):
            val = alarm.values.get(key)
            if val:
                col = '%s' % val
            else:
                col = ''
            if i < len(keys) - 1:
                col  += ','
            alarmsFile.write(col)
            if echo:
                print col,
        alarmsFile.write('\n')
        if echo:
            print

def readCsv(filename, echo = False ):
    logging.debug('readCsv({}).'.format(filename))
    alarmsFile = open(filename, 'r')
    header = alarmsFile.readline().strip().split(',')
    alarms = list()
    for line in alarmsFile.readlines():
        row = line.strip().split(',')
        alarm = Alarm ()
        for i, key in enumerate(header):
            alarm.values[key] = row[i]
        alarms.append(alarm)
    logging.debug('readCsv:{} alarms read.'.format(len(alarms)))
    return alarms

class AlarmFileSystem:
    def __init__(self, camera):
        self.camera = camera
        self.filename = camera + '/' + 'alarms' + '.csv'
        self.imageDir = camera + '/images'
        self.croppedDir = camera + '/cropped'
        if not os.path.exists(camera):
            os.makedirs(camera)

    def getAlarms( self, numalarms = -1, startalarmid = 0, minscore = 0, minalt = 0 ):
        alarms = Alarms()
        all = readCsv(self.filename)
        
        for alarm in all:
            if alarm.getScore() >=  minscore and alarm.getAlt() >= minalt and alarm.getId () >= startalarmid:
                alarms.alarms.append ( alarm  )

        return alarms
        # todo. Filter it.

    def appendMavpos ( self, alarms ):
        pass

    def putAlarms(self, alarms):
        writeCsv(alarms.alarms, self.filename)

    def putAlarmImages(self, alarms, alarmServer):
        logging.info('putImage')
        if not os.path.exists(self.imageDir):
            os.makedirs(self.imageDir)
        for i, alarm in enumerate(alarms.alarms):
            logging.info('Writing image %dof%d:%s,%s,%s.' % (i, len(alarms.alarms),alarm.getId (), alarm.getTime (), alarm.getScore()))
            img = alarmServer.getImage(alarm.getTime())
            img.save('%s/%4.1f %s %4s.jpg' % (self.imageDir, alarm.getScore(), alarm.getTime (), alarm.getId ()))

    def putCroppeds(self, alarms, alarmServer):
        logging.info('putCroppeds')
        if not os.path.exists(self.croppedDir):
            os.makedirs(self.croppedDir)
        for i, alarm in enumerate(alarms.alarms):
            logging.info('Writing cropped %dof%d:%s,%s,%s' % (i, len(alarms.alarms),alarm.getId (), alarm.getTime (), alarm.getScore()))
            img = alarmServer.getCropped(alarm.getTime(), float(alarm.values['mix']), float(alarm.values['miy']),float(alarm.values['max']),float(alarm.values['may']))
            img.save('%s/%4.1f %s %4s.jpg' % (self.croppedDir, alarm.getScore(), alarm.getTime (), alarm.getId ()))

    def getImage ( self, time ):
        for filename in os.listdir(self.imageDir):
            path = os.path.join(self.imageDir, filename)
            if time in filename:
                return Image.open(path)
        return None

    def getCropped ( self, time, mix, miy, max, may ):
        logging.debug('getCropped(time={}.{};{};{};{}.'.format(time, mix, miy, max, may))
        for filename in os.listdir(self.croppedDir):
            path = os.path.join(self.croppedDir, filename)
            if time in filename:
                return Image.open(path)
        return None

class AlarmServer:
    def __init__(self, svr, camera):
        self.svr = 'http://' + svr + '/nvrs/nvr_server'
        self.camera = camera

    def getAlarms( self, numalarms = -1, startalarmid = 9, minscore = 0, minalt = 0 ):
        payload = { 'camera':self.camera,
              'alarmtype':'ObjectDetected',
              #'low_bw':'AlarmID;NVRTime;AlarmDetail'
            }
        #if numalarms >= 0:
        #    payload['numalarms'] = numalarms-1

        if startalarmid > 0:
            payload['startalarmid']=startalarmid

        filter= ''
        if minscore > 0:
            if len(filter) > 0:
                filter += ' AND '
            filter += 'ad;sc;>=;' + str(minscore)
        if minalt > 0:
            if len(filter) > 0:
                filter += ' AND '
            filter += 'ad;relalt;>=;' + str(minalt * 1000)
        if len(filter) > 0:
            payload['alarmfilter'] = filter
        if numalarms > 0:
            payload['numalarms'] = str(numalarms)
        

        r = requests.get ( self.svr + '?listalarms',
                           auth=('admin', 'admin'),
                           params = payload
                         )
        tree = et.ElementTree(et.fromstring(r.text))

        logging.debug(r.text)
        alarms = Alarms()
        alarmsTree=tree.find('Alarms[0]')  # xpath
        for alarmTree in alarmsTree:
            alarm = Alarm ()
            for attr in alarmTree:
                alarm.values[attr.tag] = attr.text
            # merge in the alarm detail
            alarmDetail = dict ()
            for attr in alarmTree.find('AlarmDetail[0]'):
                alarmDetail[attr.tag] = attr.text
            alarm.values.update(alarmDetail)
            alarms.alarms.append(alarm)

        return alarms

    def getMavpos ( self, time ):
        ## http://54.79.61.179/nvrs/nvr_server?getimage&camera=flycam1&time=2014-07-11%2000-15-51-670&mavposition
        payload = { 'camera':self.camera, 'time':time, 'mavposition':True }
        r = requests.get(self.svr + '?getimage', auth=('admin', 'admin'), params=payload)
        tree = et.ElementTree(et.fromstring(r.text))
        logging.debug(r.text)
        mavposTag = tree.find('mavpos[0]')  # xpath
        mavpos = dict((attr.tag, attr.text) for attr in mavposTag)
        logging.debug(pf(mavpos))
        return mavpos

    def getMavposXml ( self, time ):
        ## http://54.79.61.179/nvrs/nvr_server?getimage&camera=flycam1&time=2014-07-11%2000-15-51-670&mavposition
        payload = { 'camera':self.camera, 'time':time, 'mavposition':True }
        r = requests.get(self.svr + '?getimage', auth=('admin', 'admin'), params=payload)
        return r.text

    def getTimeline ( self ):
        #http://52.64.122.46/nvrs/nvr_server?gettimeline&camera=thunder
        payload = { 'camera':self.camera }
        r = requests.get(self.svr + '?gettimeline', auth=('admin', 'admin'), params=payload)
        tree = et.ElementTree(et.fromstring(r.text))
        logging.debug(r.text)
        firstTag = tree.find('CameraNVRData/CameraNVRSetting/NewFirstSavedCamImageDateTimeForNVR').text  # xpath
        lastTag = tree.find('CameraNVRData/CameraNVRSetting/NewLastSavedCamImageDateTimeForNVR').text  # xpath
        return (firstTag, lastTag)

    def getImageList ( self, startTime, endTime ):
        #http://10.0.0.1/nvrs/nvr_server?listfiles&camera=flycam1&time=2015-06-07 10-02-05-859&endTime=2015-06-07 10-02-06-181
        payload = { 'camera':self.camera,
                    'time':startTime,
                    'endTime':endTime
                  }
        r = requests.get(self.svr + '?listfiles', auth=('admin', 'admin'), params=payload)
        tree = et.ElementTree(et.fromstring(r.text))
        #logging.debug(r.text)
        #f = open('listfiles.txt', 'w')
        #f.write(r.text)

        return tree.getroot()        

    def getImage ( self, time ):
        payload = { 'camera':self.camera,
                    'time':time.replace('+', ' '),
                    'mavposition':False,
                    'quality':100,
                    'fullimg': True,
                    'timestamp': False,
                    'showjoes': False
                }
        r = requests.get(self.svr + '?getimage', auth=('admin', 'admin'), params=payload)
        return Image.open(StringIO(r.content))

    def getLiveImage ( self ):
        payload = { 'camera':self.camera,
                    'mavposition':False,
                    'quality':100,
                    'timestamp': 2
                }

        r = requests.get(self.svr + '?getliveimage', auth=('admin', 'admin'), params=payload)
        return Image.open(StringIO(r.content))

    def getLiveImageCropped ( self ):
        payload = { 'camera':self.camera,
                    'mavposition':False,
                    'quality':100,
                    'timestamp': 2,
                    'cropval': '45;45;55;55'
                }

        r = requests.get(self.svr + '?getliveimage', auth=('admin', 'admin'), params=payload)
        return Image.open(StringIO(r.content))

    def getLiveMavpos ( self ):
        payload = { 'camera':self.camera,
                    'mavposition':1,
                }

        r = requests.get(self.svr + '?getliveimage', auth=('admin', 'admin'), params=payload)
        tree = et.ElementTree(et.fromstring(r.text))
        logging.debug(r.text)
        mavposTag = tree.find('mavpos[0]')  # xpath
        mavpos = dict((attr.tag, attr.text) for attr in mavposTag)
        logging.debug(pf(mavpos))
        return mavpos

    def getTime( self ):
        r = requests.get(self.svr + '?gettime', auth=('admin', 'admin'))
        tree = et.ElementTree(et.fromstring(r.text))
        logging.debug(r.text)
        timeTag = tree.find('Time[0]')  # xpath
        return ""


    def getCropped ( self, time, mix, miy, max, may ):
        payload = { 'camera':self.camera,
                    'time':time,
                    'mavposition':False,
                    'stripcomment':True,
                    'timestamp':False,
                    'quality':100,
                    'cropval':getCropVal ( mix, miy, max, may )
                  }
        r = requests.get(self.svr + '?getimage', auth=('admin', 'admin'), params=payload)
        return Image.open(StringIO(r.content))

    def appendMavpos ( self, alarms ):
        for i, alarm in enumerate(alarms.alarms):
            logging.info('Getting mavpos {}of{}.id={}.time={}.'.format(i,len(alarms.alarms),alarm.getId(),alarm.getTime()))
            mavpos = self.getMavpos(alarm.getTime())
            alarm.values.update(mavpos)

class Alarm:
    def __init__(self):
        self.values = dict ()

    def getTime ( self ):
        return self.values['NVRTime']

    def getScore ( self ):
        return float(self.values['sc'])

    def getAlt ( self ):
        return float(float(self.values['alt'])/1000)

    def getId ( self ):
        return self.values['AlarmID']

def find(alarmList, key, value):
    for alarm in alarmList:
        if alarm.values[key] == value:
            return alarm
    return None

class Alarms:
    def __init__(self):
        self.alarms = list ()

    def getByTime (self, time):
        return find(self.alarms,'NVRTime', time)

    def getById (self, id):
        return find(self.alarms,'AlarmID', id)


def getCropVal(mix, miy, max, may):
    logging.debug('getCropVal({};{};{};{}.'.format(mix, miy, max, may))
    t_size = int(5)
    cx = (mix + max) / 2;
    cy = (miy + may) / 2;
    px = cx / 640 * 100;
    py = cy / 480 * 100;
    ix1 = int(px) - t_size;
    ix2 = int(px) + t_size;
    iy1 = int(py) - t_size;
    iy2 = int(py) + t_size;
    while ix1 < 0:
        ix1 += 1
        ix2 += 1
    while iy1 < 0:
        iy1 += 1
        iy2 += 1
    while ix2 > 100:
        ix2 -= 1
        ix1 -= 1
    while iy2 > 100:
        iy2 -= 1
        iy1 -= 1

    #cv = ix1 + ';' + iy1 + ';' + ix2 + ';' + iy2;
    cv = '%d;%d;%d;%d' % ( ix1, iy1, ix2, iy2 )
    logging.debug('cv=%s.' % cv)
    return cv;

def copyAlarms ( source, dest, numalarms, startalarmid, minscore, minalt, numberOfImages ):
    logging.info('copyAlarms({},{},{},{},{})'.format(numalarms, startalarmid, minscore, minalt, numberOfImages))

    logging.info('Getting alarms...')
    alarms = source.getAlarms( numalarms, startalarmid, minscore, minalt )
    logging.info('alarms={}.done'.format(len(alarms.alarms)))

    logging.info('Getting mavpos...')
    source.appendMavpos ( alarms )
    logging.info('done')

    dest.putAlarms(alarms)
    dest.putAlarmImages(alarms, source)
    dest.putCroppeds(alarms, source)

def copyImages ( source, tlog, dest, maxImages = -1 ):
    logging.info('copyImages({},{},{},{})'.format(source, tlog, dest, maxImages))

    logging.info('Read tlog.')

    (firstTime,lastTime) = source.getTimeline()
    
    logging.debug('timeline={}-{}.done'.format(firstTime,lastTime))

    imageList = source.getImageList(firstTime,lastTime)

    #<Status>Succeeded</Status>
    #<Dir><Name>/srv/disk1/flycam1/2015-06-07/0600</Name>
    #<N>2015-06-07 10-02-05-859.jpg</N><N>2015-06-07 10-02-06-128.jpg</N>
    #<Size>84103564</Size><AvgTimeBetweenFrames>345.350494</AvgTimeBetweenFrames><StdDevTimeBetweenFrames>1778.136841</StdDevTimeBetweenFrames><MaxDiffMS>40265</MaxDiffMS><MinDiffMS>237</MinDiffMS></Dir>
    #<FirstFile>2015-06-07 10-02-05-859.jpg</FirstFile>
    #<LastFile>2015-06-08 02-23-02-269.jpg</LastFile>
    #<ListFileResult><Camera>flycam1</Camera><FilesListed>31596</FilesListed>
    #<SizeListed>2656651866</SizeListed>
    #<SizeListedH>2.47G (2656651866 bytes)</SizeListedH>
    #<TotalFiles>31596</TotalFiles><FramesPerSecond>0.536827</FramesPerSecond>
    #<Label></Label>
    #<AvgTimeBetweenFrames>1862.780396</AvgTimeBetweenFrames>
    #<StdDevTimeBetweenFrames>248752.906250</StdDevTimeBetweenFrames>
    #<MaxDiffMS>44105604</MaxDiffMS><MinDiffMS>5</MinDiffMS></ListFileResult>
    #<ResponseTime>1448</ResponseTime>

    numImages = 0
    outputDirName = r'c:\temp\out'
    if not os.path.exists(outputDirName):
      os.makedirs(outputDirName)
    for dir in imageList:
        if dir.tag == 'Dir':
            dirName = dir.find('Name').text
            print dirName
            for file in dir:
                if file.tag == 'N' and (maxImages < 0 or numImages < maxImages):
                    filename = file.text
                    print '  ', filename
                    imageTime = filename.split('.')[0]
                    img = source.getImage(imageTime)
                    img.save(os.path.join(outputDirName, filename))
                    mavPos = source.getMavposXml(imageTime)
                    if mavPos:
                      open(os.path.join(outputDirName,imageTime+'.xml'),'w').write(mavPos)
                    numImages += 1
                    
    

    #dest.putAlarmImages(alarms, source)
