#!/usr/bin/python
##########################################################################
# bentv_ui, Copyright Graham Jones 2013 (grahamjones139@gmail.com)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
##########################################################################
# Description:
# This program is the user interface for bentv.  It does the following:
#    Monitor the Raspberry Pi GPIO input 14 (physical pin 8) to see if it
#       is pulled low by a switch connected to ground (Pin 6).
#    Each time the switch is pressed, it changes the camera view position
#       preset number, moves the camera to the camera to the new preset
#       and writes a message to the bottom of the screen.
#    The camera is moved by sending the appropriate http GET command to the
#       relevant URL on the camera.  This is done using the httplib2 library.
#    Writing to the screen is achieved using the pygame library.
#    Note that this program does NOT display the video images - this is done
#       using omxplayer, which is started separately using the bentv.sh script.
#
##########################################################################
#
#import RPi.GPIO as GPIO 
import time
import os
import httplib2
import ConfigParser
import pygame

class bentv_ui:
    # Basic Configuration
    configFname = "config.ini"
    configSection = "bentv"
    debug = False

    # Initialise some instance variables.
    screen = None
    font = None
    presetNo = 1
    presetTxt = ['NULL','Behind Door', 'Corner', 'Chair', 'Bed']

    def __init__(self):
        print "bentv.__init__()"
        self.config = self.getConfigSectionMap(self.configFname, 
                                          self.configSection)
        print self.config
        self.debug = self.getConfigBool("debug")
        if (self.debug): print "Debug Mode"
        
        self.presetNo = 1
        self.initScreen()
        self.initGPIO()

    def initGPIO(self):
        ##########################################
        # Initialise the GPIO Pins
        # Set the mode of numbering the pins.
        pinNo = self.getConfigInt("gpiono")
        if (self.debug): print "gpioNo = %d" % pinNo
        if (not self.debug):
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pinNo, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # very long debounce time to prevent presses while camera is moving.
            GPIO.add_event_detect(pinNo,
                                  GPIO.RISING, 
                                  callback=self.moveCamera, 
                                  bouncetime=1000)
        else:
            print "debug - simulating camera move"
            self.moveCamera(1)

    def getConfigBool(self,configName):
        if (configName in self.config):
            try:
                retVal = bool(self.config[configName])
            except ValueError:
                print "configName is not a boolean"
                retVal = False
        else:
            print "key %s not found" % configName
            retVal = False
        return retVal

    def getConfigInt(self,configName):
        if (configName in self.config):
            try:
                retVal = int(self.config[configName])
            except ValueError:
                print "configName is not an integer!!!"
                retVal = -999
        else:
            print "key %s not found" % configName
            retVal = -999
        return retVal

    def getConfigFloat(self,configName):
        if (configName in self.config):
            try:
                retVal = float(self.config[configName])
            except ValueError:
                print "configName is not a float!!!"
                retVal = -999
        else:
            print "key %s not found" % configName
            retVal = -999
        return retVal

    def getConfigStr(self,configName):
        if (configName in self.config):
            retVal = self.config[configName]
        else:
            print "key %s not found" % configName
            retVal = "NULL"
        return retVal

    def getConfigSectionMap(self,configFname, section):
        '''Returns a dictionary containing the config file data in the section
        specified by the parameter 'section'.   
        configFname should be a string that is the path to a configuration file.'''
        dict1 = {}
        config = ConfigParser.ConfigParser()
        config.read(configFname)
        options = config.options(section)
        for option in options:
            try:
                dict1[option] = config.get(section, option)
                if dict1[option] == -1:
                    DebugPrint("skip: %s" % option)
            except:
                print("exception on %s!" % option)
                dict1[option] = None
        return dict1


    def display_text(self,line1,line2):
        txtImg = self.font.render(line1,
            True,(255,255,255))
        self.screen.fill((0, 0, 255))
        self.screen.blit(txtImg,(0,380))
        pygame.display.update()

    def initScreen(self):    
        drivers = ['x11', 'fbcon', 'svgalib']
        found = False
        disp_no = os.getenv("DISPLAY")
        if disp_no:
            print "I'm running under X display = {0}".format(disp_no)
        for driver in drivers:
            # Make sure that SDL_VIDEODRIVER is set
            if not os.getenv('SDL_VIDEODRIVER'):
                os.putenv('SDL_VIDEODRIVER', driver)
            try:
                pygame.display.init()
            except pygame.error:
                print 'Driver: {0} failed.'.format(driver)
                continue
            found = True
            break

        if not found:
            raise Exception('No suitable video driver found!')

        size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
        print "Framebuffer size: %d x %d" % (size[0], size[1])
        if (disp_no):
            self.screen = pygame.display.set_mode((640,480))
        else:
            self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
        self.screen.fill((0, 0, 255))        
        pygame.font.init()
        self.font = pygame.font.Font(None,30)
        self.display_text("BenTV_UI",None)

    ##########################################
    # Callback function when button is pressed
    def moveCamera(self,pinNo):
        print('moveCamera called by pin number %d. PresetNo=%d' % (pinNo,self.presetNo))
        h = httplib2.Http(".cache")
        h.add_credentials(self.getConfigStr('uname'), 
                          self.getConfigStr('passwd'))
        #resp, content = h.request("http://192.168.1.24/preset.cgi?-act=goto&-status=1&-number=%d" % self.presetNo,"GET")
        resp, content = h.request("%s/%s%d" % (self.getConfigStr('camaddr'),
                                               self.getConfigStr('cammoveurl'),
                                               self.presetNo),"GET")
        print "moved to preset %d - content=%s" % (self.presetNo,content)
        self.display_text("Moved to Position %d (%s)" % (self.presetNo, self.presetTxt[self.presetNo]),
                     None)
        self.presetNo += 1
        if (self.presetNo > 4): self.presetNo = 1

 
#############################################
# Main loop - does nothing useful!!!
if __name__ == "__main__":
    bentv = bentv_ui()
    #init_screen()
    print "starting main loop..."
    while 1: 
        #print "main loop..."
        time.sleep(1)

