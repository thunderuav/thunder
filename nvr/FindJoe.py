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
from nvr import *


def recordLive ( source, dest ):
    logging.info('recordLive ()')


    #plt.ion()
    print 'Time,LiveImageCropped,LiveImage,LiveMavPos'
    while True:

        #try:
        #    before = time.clock ()
        #    source.gettime()
        #    after = time.clock ()
        #    print after - before, ',',
        #except:
        #    print 'gettime=failed',

        #try:
        #    before = time.clock ()
        #    img = source.getLiveImageCropped()
        #    after = time.clock ()
        #    print after - before, ',',
        #except:
        #    print 'getLiveImageCropped=failed',

        try:
            before = time.clock ()
            img = source.getLiveImage()
            after = time.clock ()
            print after - before, ',',
            imgplot = plt.imshow(np.asarray(img))
            plt.show()
        except:
            print 'getLiveImage=failed',

        #try:
        #    before = time.clock ()
        #    r = source.getLiveMavpos()
        #    after = time.clock ()

        #    print after - before
        #except Exception as inst:
        #    print 'getLiveMavpos=failed',

        #print server.getLiveMavpos()
        #print 'hello'
        #time.

        #print server.getLiveMavpos()
        time.sleep(1)
    #                 
    #imgplot = plt.imshow(np.asarray(img))
    #plt.show()

    #print server.getLiveMavpos()

    #logging.info('Getting alarms...')
    #alarms = source.getAlarms( numalarms, startalarmid, minscore, minalt )
    #logging.info('alarms={}.done'.format(len(alarms.alarms)))

    #logging.info('Getting mavpos...')
    #source.appendMavpos ( alarms )
    #logging.info('done')

    #dest.putAlarms(alarms)
    #dest.putImages(alarms, source)
    #dest.putCroppeds(alarms, source)

def do ( alarmsSource, numalarms, startalarmid, minscore, minalt, numberOfImages ):
    logging.info('do({},{},{},{},{})'.format(numalarms, startalarmid, minscore, minalt, numberOfImages))

    logging.info('Getting alarms...')
    alarms = alarmsSource.getAlarms( numalarms, startalarmid, minscore, minalt )
    logging.info('done')

    logging.info('Sorting')
    alarms.sort(reverse=True, key=Alarm.getScore)
    logging.info('done')

    logging.info('Total %d alarms.' % len(alarms))

    #logging.info('Filtering top %d based on score' % numberOfImages)
    #alarms = alarms[0:numberOfImages]

    logging.info('Getting mavpos...')
    alarmsSource.appendMavpos ( alarms )
    logging.info('done')

    writeCsv(alarms.alarms, 'test.csv')

    # full image
    logging.info('Save images')
    for alarm in alarms:
        logging.info('%s,%s,%s' % (alarm.getId (), alarm.getTime (), alarm.getScore()))
        img = alarmsSource.getImage(alarm.getTime())
        imgplot = plt.imshow(np.asarray(img))
        plt.show()

def AnalyseSinglePhoto ( server, alarmsSource ):
    logging.info('AnalyseSinglePhoto()')

    logging.info('Getting alarms...')
    alarms = alarmsSource.getAlarms()
    logging.info('done')

    #logging.info('Getting mavpos...')
    #alarmsSource.appendMavpos ( alarms )
    #logging.info('done')

    time = '2014-07-11 00-14-58-198'
    alarm = alarms.getByTime(time)

    logging.info('%s,%s,%s' % (alarm.getId (), alarm.getTime (), alarm.getScore()))
    plt.figure(1)
    img = alarmsSource.getImage(alarm.getTime())
    plot1 = plt.imshow(np.asarray(img))

    print 'max=', alarm.values['max']
    plt.figure(2)
    cropped = server.getCropped(time, float(alarm.values['mix']), float(alarm.values['miy']),float(alarm.values['max']),float(alarm.values['may']))
    plot2 = plt.imshow(np.asarray(cropped))

    plt.show()



def MarkScore(alarm):
    rpsNormalise = 131.0
    rpsBias = 0.2
    scNormalise = 968.0

    return float(alarm.values['rps'])/rpsNormalise*rpsBias + float(alarm.values['sc'])/scNormalise

def MarkThreshold(alarm):
    rpsThreshold = 140.0
    scThreshold  = 970

    return float(alarm.values['rps']) > rpsThreshold and float(alarm.values['sc']) > scThreshold


def writeQPFile(alarms, filename):
    hitfile = open(filename, 'w')
    hitfile.write('QGC WPL 110\n')
    hitfile.write('%s\n' % '0	1	0	16	0	0	0	0	-31.215995	149.361244	561.000000	1')
    
    for i, alarm in enumerate(alarms):
        hitfile.write('{} 0 3 16 0 {} {} {} {} {} 1\n'.format ( i+1,
                                                                  alarm.getId(), 
                                                                  alarm.values['sc'],
                                                                  alarm.values['rps'],
                                                                  alarm.values['la'],
                                                                  alarm.values['lo'],
                                                                  float(alarm.values['alt'])/1000
                                                                )
                     )
    hitfile.close()  

def Mark1 ( alarmsSource ):
    logging.info('AnalyseSinglePhoto()')

    logging.info('Getting alarms...')
    alarms = alarmsSource.getAlarms()
    logging.info('done')

    logging.info('Getting mavpos...')
    alarmsSource.appendMavpos ( alarms )
    logging.info('done')

    hits = list ()

    for alarm in alarms.alarms:
        if MarkThreshold(alarm):
            hits.append(alarm)

    writeCsv(hits, 'mark1.csv')
    #pp(alarm.values)
    writeQPFile(hits, 'mark1.txt')

def Mark2 ( alarmsSource ):
    logging.info('AnalyseSinglePhoto()')

    logging.info('Getting alarms...')
    alarms = alarmsSource.getAlarms()
    logging.info('done')

    logging.info('Getting mavpos...')
    alarmsSource.appendMavpos ( alarms )
    logging.info('done')

    logging.info('Sorting')
    alarms.alarms.sort(reverse=True, key=MarkScore)
 
    hits = alarms.alarms[0:20]
 
    writeCsv(hits, 'mark2.csv')
    writeQPFile(hits, 'mark2.txt')
    

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Get images of Joe.')
    parser.add_argument('--svr', default = '54.79.61.179:8000')
    parser.add_argument('--camera', default = 'flycam')
    parser.add_argument('--numalarms', '-n', type=int, default = -1)
    parser.add_argument('--startalarmid', type=int, default = 0)
    parser.add_argument('--minscore', type=int, default = 965)
    parser.add_argument('--minalt', type=int, default = 50)
    parser.add_argument('--numberOfImages', '-i', type=int, default  = -1)

    args = parser.parse_args()

    #live = AlarmServer ( args.svr, args.camera )
    #rec = AlarmFileSystem ( 'rec' )

    #recordLive(live, rec)

    #flycam1 = AlarmFileSystem('flycam1')

    # Get the alarms from the server to file
    copyAlarms(AlarmServer ( args.svr, args.camera ), AlarmFileSystem(args.camera), args.numalarms, args.startalarmid, args.minscore, args.minalt, args.numberOfImages)
    
    # An example of copying
    #copyAlarms(AlarmServer ( "10.0.0.1", "flycam" ), AlarmFileSystem ( 'flycam20140904' ), args.numalarms, args.startalarmid, args.minscore, args.minalt, args.numberOfImages)

    #copyAlarms(AlarmFileSystem ( 'flycam20140904' ), AlarmFileSystem ( 'f5' ), -1, 0, 965, 50.0, 50)
    #copyAlarms(AlarmServer ( "52.64.122.46", "Thunder" ), AlarmFileSystem ( 'ThunderOBC2014' ), -1, 0, 965, 50.0, -1)

    # Do something, can be live from the server or from the filesystem
    #do(AlarmFileSystem(args.camera), args.numalarms, args.startalarmid, args.minscore, args.minalt, args.numberOfImages)
    #do(AlarmServer ( args.svr, args.camera ), args.numalarms, args.startalarmid, args.minscore, args.minalt, args.numberOfImages)
    
    # an example of analysing a single photo
    #AnalyseSinglePhoto(server, AlarmFileSystem('flycam1'))
    #Mark1(flycam1)
    #Mark2(flycam1)

if __name__ == "__main__":
    main()
