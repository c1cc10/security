#! /usr/bin/python
#                                                                      #
# Copyright (c) 2013 by        Francesco Rana                          #
# Created on:                  Wed, 10 Dec 2013 11:06:01               #
# Email:                       rana@isolved.it                         #
#                                                                      #
# $Id$                     #
#                                                                      #
########################################################################
#                                                                      #
# This file is property of Isolved It Technologies S.r.L (c) 2013      #
#                                                                      #
########################################################################

import RPi.GPIO as GPIO
import os
from datetime import datetime
import time
import cv2
import shutil
import threading
from uploader import MotionUploader
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

class sendVideo(threading.Thread):
	video = None	

	def __init__(self, content):
		threading.Thread.__init__(self)
		self.video = content

	def run(self):
		try:
			print "before start"
			MotionUploader('./uploader.cfg').upload_video(self.video)
		except Exception,e:
			print "error in uploading file %s : %s" % self.video,e

class sendEmail(threading.Thread):
	messageText = ''
	attach = None

	def __init__(self, bodytext, attachment):
		threading.Thread.__init__(self)
		self.messageText = bodytext
		self.attach = attachment

	def run(self):
        	'''Send an email using the GMail account.'''

		msg = MIMEMultipart('mixed')
		msg['Date'] = datetime.strftime(datetime.now(), '%Y-%m-%d')
		msg['From'] = 'Francesco Rana <ciunociciunozero@gmail.com>'
		msg['To'] = 'Francesco Rana <ciunociciunozero@gmail.com>'
		msg['Subject'] = 'Motion with picture'
		msg.attach(MIMEText(self.messageText))
		
		adjunto = MIMEBase('application', "octet-stream")
		adjunto.set_payload( open(self.attach,"rb").read() )
		encoders.encode_base64(adjunto)
		adjunto.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(self.attach))
		msg.attach(adjunto)

	        server = smtplib.SMTP('smtp.gmail.com:587')
	        server.starttls()
	        server.login('ciunociciunozero@gmail.com', 'XXXXXX')
	        server.sendmail('ciunociciunozero@gmail.com', 'ciunociciunozero@gmail.com', msg.as_string())
	        server.quit()    

class security:
	shotdir='/mnt/MOTION/'
	#shotdir='/mnt/06-Area_Utenti/07-f.rana/'
	default_video_output = '%s/MyOutputVid.avi' % shotdir
	state_machine = {}
	cameraCapture = None	
	fps = 20
	maxFrames = 10
	size = 0
	success = True
	frame = None
	numFramesRemaining = 0
	videoWriter = None
	pool = None

	def __init__(self):

		GPIO.setmode(GPIO.BCM)
		GPIO.setup(23,GPIO.IN)
		self.state_machine = {
		     'idle' : self.idle,
		     'rec_start' : self.rec_start,
		     'rec_progress' : self.rec_progress,
		     'rec_end' : self.rec_end 
		}
		self.cameraCapture = cv2.VideoCapture(0)
		self.size = (int(self.cameraCapture.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)),
	        	int(self.cameraCapture.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)))
		self.initialiaze_videoWriter()
		self._set_max_frames_number()	
		self.state = self.state_machine['idle']
		
	def initialiaze_videoWriter(self):
		self.videoWriter = cv2.VideoWriter(
			self.default_video_output,
			cv2.cv.CV_FOURCC('M','J','P','G'),
			self.fps, 
			self.size)

	def _set_max_frames_number(self):
		self.numFramesRemaining = self.maxFrames * self.fps - 1
	
	def _mark_timestamp(self):
		cv2.putText(self.frame, time.asctime(),(5,25), cv2.FONT_HERSHEY_DUPLEX, 1, 255, 2, 2)

	def _record_video(self):
		self._mark_timestamp()
		try:
			self.videoWriter.write(self.frame)
		except Exception,e:
			print "error in writing frame: %s" % e

	def idle(self):
		print "idle"
	    	time.sleep(0.7)

	def rec_start(self):
		print "rec_start"
	        key_frame_name = '%s/shot_%d_%s.bmp' % (self.shotdir, self.numFramesRemaining, datetime.strftime(datetime.now(), '%Y-%m-%d'))
		self._mark_timestamp()
		cv2.imwrite(key_frame_name, self.frame)
		try:
			sendMail = sendEmail('sono un test', key_frame_name)
			sendMail.start()
		except Exception,e:
			print "error in attaching file : %s" % e

	def rec_progress(self):
		print "rec_progress, frame # %s" % self.numFramesRemaining
		self._record_video()

	def rec_end(self):

		print "rec_end"
	        dst = '%s/video_%s.avi' % (self.shotdir, datetime.strftime(datetime.now(), '%Y-%m-%d'))
		try:
			shutil.copy2(self.default_video_output, dst)
			os.unlink(self.default_video_output)
			self.initialiaze_videoWriter()
			sendMyVideo = sendVideo(dst)
			sendMyVideo.start()
				
		except Exception,e:
			print "error in storing video file: %s" % e
	
	def online(self):
		try:
			self.success, self.frame = self.cameraCapture.read()
		except Exception, e:		
			print "Errore: %s" % e 
		self.numFramesRemaining -= 1
		if GPIO.input(23) == 1:
	       		if self.state == self.state_machine['idle'] or self.state == self.state_machine['rec_end']:
				self.state = self.state_machine['rec_start']
			elif self.state == self.state_machine['rec_start']:
				self.state = self.state_machine['rec_progress']
	    	else:
			if self.state == self.state_machine['rec_progress']:
				self.state = self.state_machine['rec_end']
			else : 
				self.state = self.state_machine['idle']
		if self.numFramesRemaining == 0:
			state = self.state_machine['rec_end']
			self.state()
			self._set_max_frames_number()	
		self.state()
	def offline(self):
	    	GPIO.cleanup()


def main():
        print "Inizio"
	pippo = security()
	while pippo.success and pippo.numFramesRemaining > 0:
		try:
        		pippo.online()
		except KeyboardInterrupt:
			pippo.offline()
			break
	pippo.offline()

if __name__=="__main__":
    main()

