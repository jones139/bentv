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
import time
import os
import httplib2                     # Needed to communicate with camera
import pygame                       # Needed to drive display
import socket, fcntl, struct        # Needed to get IP address
from config_utils import ConfigUtil

class bentv_ui:
    # Basic Configuration
    configFname = "config.ini"
    configSection = "bentv"
    debug = False

    # Initialise some instance variables.
    screen = None
    font = None
    textLine1 = "BenTV_UI"
    textLine2 = "Waiting for Button Press to move camera"
    presetNo = 1
    presetTxt = ['NULL','Behind Door', 'Corner', 'Chair', 'Bed']

    def __init__(self):
        """Initialise the bentv_ui class - reads the configuration file
        and initialises the screen and GPIO monitor"""
        print "bentv.__init__()"
        configPath = "%s/%s" % (os.path.dirname(os.path.realpath(__file__)),
                                self.configFname)
        print configPath
        self.cfg = ConfigUtil(configPath,self.configSection)

        self.debug = self.cfg.getConfigBool("debug")
        if (self.debug): print "Debug Mode"
        
        self.hostname, self.ipaddr = self.getHostName()
        print self.hostname, self.ipaddr
        self.presetNo = 1
        self.initScreen()
        self.initGPIO()

    def getIpAddr(self,ifname):
        """Return the IP Address of the given interface (e.g 'wlan0')
        from http://raspberrypi.stackexchange.com/questions/6714/how-to-get-the-raspberry-pis-ip-address-for-ssh.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])

    def getHostName(self):
        """Returns the hostname and IP address of the wireless interface as a tuple.
        """
        hostname = socket.gethostname()
        ipaddr = self.getIpAddr("wlan0")
        return (hostname,ipaddr)

    def initGPIO(self):
        """Initialise the GPIO pins - not we use GPIO pin numbers, not physical
        pin numbers on rpi."""
        haveGPIO = True
        try:
            import RPi.GPIO as GPIO 
        except:
            print "failed to import RPi.GPIO"
            haveGPIO = False
        pinNo = self.cfg.getConfigInt("gpiono")
        if (self.debug): print "gpioNo = %d" % pinNo
        if (haveGPIO):
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pinNo, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # very long debounce time to prevent presses while camera is moving.
            GPIO.add_event_detect(pinNo,
                                  GPIO.RISING, 
                                  callback=self.moveCamera, 
                                  bouncetime=1000)
        else:
            print "no GPIO - simulating camera move"
            self.moveCamera(1)


    def display_text(self):
        """ Write the given text onto the display area of the screen"""
        # Clear screen
        self.screen.fill((0, 0, 255))
        # Line 1 text
        txtImg = self.font.render(self.textLine1,
            True,(255,255,255))
        self.screen.blit(txtImg,(0,380))
        # Line 1 time
        tnow = time.localtime(time.time())
        txtStr = "%02d:%02d:%02d " % (tnow[3],tnow[4],tnow[5])
        w = self.font.size(txtStr)[0]
        txtImg = self.font.render(txtStr,
            True,(255,255,255))
        self.screen.blit(txtImg,(self.fbSize[0]-w,380))
        # Line 2 text
        txtImg = self.smallFont.render(self.textLine2,
            True,(255,255,255))
        self.screen.blit(txtImg,(0,400))
        # Line 2 network info
        txtStr = "Host: %s, IP: %s  " % (self.hostname, self.ipaddr)
        w = self.smallFont.size(txtStr)[0]
        txtImg = self.smallFont.render(txtStr,
                                       True,
                                       (255,255,255))
        
        self.screen.blit(txtImg,(self.fbSize[0]-w,400))
        pygame.display.update()

    def initScreen(self):    
        """Initialise the display using the pygame library"""
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

        self.fbSize = (pygame.display.Info().current_w, pygame.display.Info().current_h)
        print "Framebuffer size: %d x %d" % self.fbSize
        if (disp_no):
            winSize = (640,480)
            self.screen = pygame.display.set_mode(winSize)
            self.fbSize = winSize
        else:
            self.screen = pygame.display.set_mode(self.fbSize, pygame.FULLSCREEN)
        self.screen.fill((0, 0, 255))        
        pygame.font.init()
        self.font = pygame.font.Font(None,30)
        self.smallFont = pygame.font.Font(None,16)
        self.display_text()

    def moveCamera(self,pinNo):
        """Callback function when button is pressed"""
        print('moveCamera called by pin number %d. PresetNo=%d' % (pinNo,self.presetNo))
        h = httplib2.Http(".cache")
        h.add_credentials(self.cfg.getConfigStr('uname'), 
                          self.cfg.getConfigStr('passwd'))
        #resp, content = h.request("http://192.168.1.24/preset.cgi?-act=goto&-status=1&-number=%d" % self.presetNo,"GET")
        resp, content = h.request("%s/%s%d" % (self.cfg.getConfigStr('camaddr'),
                                               self.cfg.getConfigStr('cammoveurl'),
                                               self.presetNo),"GET")
        print "moved to preset %d - content=%s" % (self.presetNo,content)
        self.textLine1 = "Camera Position %d (%s)" % (self.presetNo, 
                                                       self.presetTxt[self.presetNo])
        self.presetNo += 1
        if (self.presetNo > 4): self.presetNo = 1

 
#############################################
# Main loop - initialise the user inteface,
# then loop forever.
if __name__ == "__main__":
    bentv = bentv_ui()
    #init_screen()
    print "starting main loop..."
    while 1: 
        #print "main loop..."
        bentv.display_text()
        time.sleep(1)

