#!/usr/bin/python
#Copyright (c) 2012, Eng Eder de Souza
#Accessing the Google API for speech recognition With Asterisk!
#Eng Eder de Souza
#date 15/01/2012
#http://ederwander.wordpress.com/2012/01/16/google-speech-python-asterisk/
#
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2. See the COPYING file
# at the top of the source tree.
#
import scikits.audiolab as audiolab
from matplotlib.mlab import find
from tempfile import mkstemp
import scipy.signal
import numpy as np
import urllib2
import math
import sys
import re
import os


#For Portuguese Brazilian Speech Recognizer!
Lang="pt-BR"

#or for English Speech Recognizer
#Lang="en-US"

url = 'https://www.google.com/speech-api/v1/recognize?xjerr=1&client=chromium&lang='+Lang

rms2=0;
silence=True
env = {}
RawRate=8000
chunk=1024

#http://en.wikipedia.org/wiki/Vocal_range
#Assuming Vocal Range Frequency upper than 75 Hz
VocalRange = 75.0


#cd, FileNameTmp    = mkstemp('TmpSpeechFile.flac')


#Assuming Energy threshold upper than 15 dB
Threshold = 15

#10 seconds x 16000 samples/second x ( 16 bits / 8bits/byte ) = 160000 bytes
#160000/1024 = +/- 157
#157*1024 = 160768
TimeoutSignal = 160768

#then 1 second x 16000 = 16000
#16000/1024 = 15,625 round to 16
#16*1024 = 16384
Timeout_NoSpeaking=16384

#normalization for RMS Calc
SHORT_NORMALIZE = (1.0/32768.0)

#
LastBlock=''

#File Descriptor delivery in Asterisk
FD=3

#Open File Descriptor
file=os.fdopen(FD, 'rb')

signal=0

all=[]


while 1:
   	line = sys.stdin.readline().strip()

   	if line == '':
      		break
   	key,data = line.split(':')
   	if key[:4] <> 'agi_':
      		sys.stderr.write("Did not work!\n");
      		sys.stderr.flush()
      		continue
   	key = key.strip()
   	data = data.strip()
   	if key <> '':
      		env[key] = data



for key in env.keys():
   	sys.stderr.write(" -- %s = %s\n" % (key, env[key]))
   	sys.stderr.flush()



def SendSpeech(File):
	flac=open(File,"rb").read()
	header = {'Content-Type' : 'audio/x-flac; rate=8000'}
	req = urllib2.Request(url, flac, header)
	data = urllib2.urlopen(req)
	#sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" + "You Said ..." + "\" " + "\n")
        #sys.stdout.flush()
	find = re.findall('"utterance":(.*),', data.read())
	result = find[0].replace('"', '')
	#utterance
	os.remove(File)
	try:
		print find[0]
		sys.stdout.write('SET VARIABLE GoogleUtterance "%s"\n'% str(result))
		sys.stdout.flush()
		sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" "%s \n"% str(result))
		sys.stdout.flush()
	except:
		sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" + "speech not recognized ..." + "\" " + "\n")
        	sys.stdout.flush()

def Filter(samps):
	FC = 0.05/(0.5*RawRate)
        N = 200
        a = 1
        b = scipy.signal.firwin(N, cutoff=FC, window='hamming')
        return scipy.signal.lfilter(b, a, samps)
	
def Pitch(signal):
	crossing = [math.copysign(1.0, s) for s in signal]
	index = find(np.diff(crossing));
	f0=round(len(index) *RawRate /(2*np.prod(len(signal))))
	return f0;

def rms(shorts):
	global rms2 
	count = len(shorts)/2
    	sum_squares = 0.0
    	for sample in shorts:
        	n = sample * SHORT_NORMALIZE
        	sum_squares += n*n
		rms2 = math.pow(sum_squares/count,0.5);
	return rms2 * 1000

def speaking(data):
	rms_value = rms(data) 
	if rms_value > Threshold:
		return True
	else:
		return False

def VAD(SumFrequency, data2):
	AVGFrequency = SumFrequency/(Timeout_NoSpeaking+1);
	if AVGFrequency > VocalRange/2:
		S=speaking(data2)
		if S:
			return True;
		else: 
			return False;


	else:
		return False;

def RecordSpeech(TimeoutSignal, LastBlock, LastLastBlock):
	for s in LastLastBlock:
                all.append(s)
	for s in LastBlock:
                all.append(s)
	signal=0;
	while signal <= TimeoutSignal:	
		RawSamps = file.read(Timeout_NoSpeaking)
		samps = np.fromstring(RawSamps, dtype=np.int16)	
		for s in samps:
                	all.append(s)
		signal = signal + Timeout_NoSpeaking;
		#rms_value=rms(samps)
		Speech=speaking(samps)
		#sys.stdout.write("EXEC NOOP %s \"\"\"\n"% str(rms_value))
		#sys.stdout.flush()

		#if rms_value > Threshold:
		if Speech:
			sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" + "Speech Found ..." + "\" " + "\n")
			sys.stdout.flush()
		else:
			sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" + "End of the Speech..." + "\" " + "\n")	
			sys.stdout.flush()
			signal=TimeoutSignal+1

def PlayStream (params):
	sys.stderr.write("STREAM FILE %s \"\"\n" % str(params))
	sys.stderr.flush()
	sys.stdout.write("STREAM FILE %s \"\"\n" % str(params))
	sys.stdout.flush()
	result = sys.stdin.readline().strip()


sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" + "Hello Waiting For Speech ..." + "\" " + "\n")
sys.stdout.flush()



PlayStream("beep");

while silence:
	#Input Real-time Data Raw Audio from Asterisk
	RawSamps = file.read(chunk)
	samps = np.fromstring(RawSamps, dtype=np.int16)
	samps2=Filter(samps)
	Frequency=Pitch(samps2)
	rms_value=rms(samps)
	signal = signal + chunk;	
	if (rms_value > Threshold) and (Frequency > VocalRange):
		silence=False
		LastLastBlock=LastBlock
		LastBlock=samps
		sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" + "Speech Detected Recording..." + "\" " + "\n")
		sys.stdout.flush()	
	if (signal > TimeoutSignal):
		sys.stdout.write("EXEC " + "\"" + "NOOP" + "\" \"" + "Time Out No Speech Detected ..." + "\" " + "\n")	
		sys.stdout.flush()
		#os.remove(FileNameTmp)
		sys.exit()

RecordSpeech(TimeoutSignal, LastBlock, LastLastBlock)


array = np.array(all)


fmt         = audiolab.Format('flac', 'pcm16')
nchannels   = 1


cd, FileNameTmp    = mkstemp('TmpSpeechFile.flac')

# making the file .flac
afile =  audiolab.Sndfile(FileNameTmp, 'w', fmt, nchannels, RawRate)

#writing in the file
afile.write_frames(array)

SendSpeech(FileNameTmp)
