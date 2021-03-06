#!/usr/bin/env python
__author__     = "Ruediger Marwein"
__copyright__  = "Copyright 2013"
__credits__    = ["Ruediger Marwein"]
__license__    = "LGPL"
__version__    = "1.0"
__maintainer__ = "Ruediger Marwein"
__email__      = "ruediger.marwein@gmail.com"
__status__     = "Stable"

'''
Export Inkscape layer constellations as images in batch.

* Create a config file for SVG file (see below)
* Start inkscape with your SVG file
* Select Extensions -> MockupMachine -> Setup
* Enter the full path to your desired output directory
* Enter the full path to your SVG file
* Hit execute and wait.

The configuration

    Filename ends with a colon:
    + Layer to activate
    - Layer to deactivate
    ; comment line, ignored
      blank line to end one file (incemental)
    -- line of minus signs to disable all layers again (full reset).

A config file may look like this:

; This is a comment
myfile-1.0:
+ layer1
+ layer2

myfile-1.1:
- layer2
+ layer3
+ layer4
-----------------
myfile-2.0:
+ layer10
+ layer11

myfile-2.1:
- layer10
+ layer12

This will create the files myfile-1.0.png, myfile-1.1.png, myfile-2.0.png and myfile-2.1.png
'''

import inkex, os, csv, math
import optparse
import os
import subprocess
import shutil
import re
import time
import threading
import sys
from xml.etree.ElementTree import ElementTree, XML, fromstring, tostring

class MockupMachine(inkex.Effect):

	parseFile = ''
	SVG = ''
	options = []
	availableLayers = []
	activeLayers = []
	inkscapeExecutable = 'inkscape'
	filename = ''
	tempfileCounter = 0
	renderBoxId = ''

	'''
	Initialize config options, load config file and create output-dir.
	
	'''
	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option('--outdir', '-o', default="MockupMachine", dest="outdir")
		self.OptionParser.add_option('--config', '-c', default="MockupMachine.txt", dest="config")
		self.options, arguments = self.OptionParser.parse_args()

		try:
			os.mkdir(self.options.outdir);
		except:
			pass


		
	'''
	Go through config file line by line, collect active layers and start rendering
	
	'''
	def effect(self):
		if not os.path.exists(self.options.config):
			inkex.debug("! Config file not found. Path correct?");
			return
		if not os.path.exists(self.options.outdir):
			inkex.debug("! Output path inaccessible. Permissions?");
			return
	
		self.SVG = self.document.getroot()
		self.scanAvailableLayers()
		
		self.parseFile = self.options.outdir+'/temp.MockupMachine'
		
		configLines = (line.rstrip('\n') for line in open(self.options.config, 'r'))
		
		
		for line in configLines:			
			line = line.strip()
			command1 = line[:1]
			command2 = line[:2]
			command2val = line[2:].strip()
			
			exported = False
			
			if(command1 == ';'):
				# comment, no action
				continue
			if(command2 == '--' or line == ''):
				self.exportCurrent()
				exported = True
				self.renderBoxId = ''
			if(command2 == '- '):
				if not command2val in self.availableLayers:
					inkex.debug("!- Layer '"+command2val+"' unknown.")
				else:
					while command2val in self.activeLayers:
						self.activeLayers.remove(command2val)
					list(set(self.activeLayers))
			elif(command2 == '+ '):
				if not command2val in self.availableLayers:
					inkex.debug("!+ Layer '"+command2val+"' unknown.")
				else:
					if not command2val in self.activeLayers:
						self.activeLayers.append(command2val)
					list(set(self.activeLayers))
			elif(command2 == '# '):
				if self.getElementById(command2val) is not None:
					self.renderBoxId = command2val
				else:
					inkex.debug("!# Box ID '"+command2val+"' unknown.")
			elif(command2 == '--'):
				self.activeLayers = []
			elif(line == ''):
				pass
			else:
				self.filename = line[:-1]
		''' export the last pending image '''
		if not exported:
			self.exportCurrent()
	
	'''
	Deactivate all layers in the current file
	
	Sanitize position of display:none for easier adaption later.
	'''
	def deactivateAll(self):
		for e in self.SVG.findall('./{http://www.w3.org/2000/svg}g'):
			if e.attrib['{http://www.inkscape.org/namespaces/inkscape}groupmode'] != 'layer':
				continue
			style = e.attrib['style']
			style = re.sub(r'display:[a-z]*', '', style)
			style = 'display:none;'+style
			e.attrib['style'] = style

	'''
	Extract layer labels that are valid to use in config
	
	'''
	def scanAvailableLayers(self):
		for e in self.SVG.findall('./{http://www.w3.org/2000/svg}g'):
			if e.attrib['{http://www.inkscape.org/namespaces/inkscape}groupmode'] != 'layer':
				continue
			self.availableLayers.append(e.attrib['{http://www.inkscape.org/namespaces/inkscape}label'])

	'''
	Activate the layer with the given label
	
	'''
	def activateOne(self, label):
		for e in self.SVG.findall('./{http://www.w3.org/2000/svg}g'):
			if e.get('{http://www.inkscape.org/namespaces/inkscape}groupmode') != 'layer' or e.get('{http://www.inkscape.org/namespaces/inkscape}label') != label:
				continue
			style = e.attrib['style']
			style = style.replace('display:none', 'display:inline');
			e.attrib['style'] = style

	'''
	Write the given content to the given file
	
	'''
	def writeFile(self, filename, content):
		f = open(filename, 'wb')
		f.write(content)
		f.close()
		
	'''
	Do path sanitation due to issues with german umlauts and spaces in file paths
	
	Converts "Program Files" to the DOS 8+3 name and replaces \ by /
	'''
	def treatPath(self, str):	
		return str.replace("\\","/").replace('Program Files (x86)', 'PROGRA~2').replace('Program Files', 'PROGRA~1').replace("R\xfcdiger", 'RDIGER~1')
		
	'''
	Activate the collected layers from config file and write png.
	
	Uses an inkscape subprocess to render. Inkscape starts in background. 
	A thread deletes aech temporary svg file when done.
	'''
	def exportCurrent(self):
		self.deactivateAll()
		for layer in self.activeLayers:
			self.activateOne(layer)
		inkex.debug("Exporting "+self.filename);
		
		self.tempfileCounter += 1
		useFile = self.parseFile+'-'+str(self.tempfileCounter)
		self.writeFile(useFile, tostring(self.SVG))
		infile = os.path.abspath(useFile)
		
		outfile = self.options.outdir+'/'+self.filename+'.png'
		
		if(self.renderBoxId):
			shellCmd = [self.treatPath(self.inkscapeExecutable),'-i', self.renderBoxId, '-z', '-e', self.treatPath(outfile), '-d', "90", self.treatPath(infile)]
		else:
			shellCmd = [self.treatPath(self.inkscapeExecutable),'-z', '-e', self.treatPath(outfile), '-d', "90", self.treatPath(infile)]
		
		try:
			os.unlink(self.treatPath(outfile))
		except:
			pass
		subprocess.Popen(shellCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		
		''' cleanup thread. 20 seconds max render time '''
		def clearTempFileWhenDone():
			t = 0
			while not os.path.isfile(outfile) and t < 20:
				time.sleep(1);
				t += 1
			if t >= 20:
				print("- Not ready within 20 seconds. Result may be broken.");
			os.unlink(self.treatPath(infile))		
		t = threading.Timer(1, clearTempFileWhenDone).start();

if __name__ == '__main__':
	mm = MockupMachine()
	mm.affect(args=sys.argv[1:], output=False)