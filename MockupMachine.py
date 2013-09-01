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
      blank line to end one file (incemental)
    -- line of minus signs to disable all layers again (full reset).

A config file may look like this:

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

TODO: Reset to normal
TODO: Activate layers in inkscape by config file?
TODO: Append currently active layers to config file
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
	activeLayers = []
	inkscapeExecutable = 'inkscape'
	filename = ''
	tempfileCounter = 0

	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option('--outdir', '-o', default="MockupMachine", dest="outdir")
		self.OptionParser.add_option('--config', '-c', default="MockupMachine.txt", dest="config")
		self.options, arguments = self.OptionParser.parse_args()

		try:
			os.mkdir(self.options.outdir);
		except:
			pass
		config = open(self.options.config, 'r').read()

		
	def effect(self):
		self.SVG = self.document.getroot()
		self.parseFile = self.options.outdir+'/temp.MockupMachine'
		
		configLines = (line.rstrip('\n') for line in open(self.options.config, 'r'))
		
		for line in configLines:
			line = line.strip()
			if(line[:2] == '--' or line == ''):
				self.exportCurrent()
			if(line[:2] == '- '):
				self.activeLayers.remove(line[2:].strip())
				list(set(self.activeLayers))
			elif(line[:2] == '+ '):
				self.activeLayers.append(line[2:].strip())
				list(set(self.activeLayers))
			elif(line[:2] == '--'):
				self.activeLayers = []
			elif(line.strip() == ''):
				pass
			else:
				self.filename = line[:-1].strip()
		''' export the last pending image '''
		self.exportCurrent()
		
	def deactivateAll(self):
		for e in self.SVG.findall('./{http://www.w3.org/2000/svg}g'):
			if e.attrib['{http://www.inkscape.org/namespaces/inkscape}groupmode'] != 'layer':
				continue
			style = e.attrib['style']
			style = re.sub(r'display:[a-z]*', '', style)
			style = 'display:none;'+style
			e.attrib['style'] = style

	def activateOne(self, label):
		for e in self.SVG.findall('./{http://www.w3.org/2000/svg}g'):
			if e.get('{http://www.inkscape.org/namespaces/inkscape}groupmode') != 'layer' or e.get('{http://www.inkscape.org/namespaces/inkscape}label') != label:
				continue
			style = e.attrib['style']
			style = style.replace('display:none', 'display:inline');
			e.attrib['style'] = style

	def writeFile(self, filename, content):
		f = open(filename, 'wb')
		f.write(content)
		f.close()
		
	def treatPath(self, str):	
		return str.replace("\\","/").replace('Program Files (x86)', 'PROGRA~2').replace('Program Files', 'PROGRA~1').replace("R\xfcdiger", 'RDIGER~1')
		
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
		shellCmd = [self.treatPath(self.inkscapeExecutable),'-z', '-e', self.treatPath(outfile), '-d', "90", self.treatPath(infile)]
		
		try:
			os.unlink(self.treatPath(outfile))
		except:
			pass
		subprocess.Popen(shellCmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		
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