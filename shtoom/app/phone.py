# Copyright (C) 2004 Anthony Baxter

# The Phone app.

import os, sys, threading

from twisted.internet import defer, protocol
from twisted.python import log, threadable

from shtoom.app.interfaces import Application
from shtoom.app.base import BaseApplication
from shtoom.exceptions import CallFailed
from shtoom.sdp import SDP, MediaDescription
from shtoom.ui import findUserInterface
from shtoom.opts import buildOptions
from shtoom.Options import OptionGroup, StringOption, ChoiceOption, OptionDict, BooleanOption

from shtoom.rtp.formats import PT_PCMU, PT_GSM, PT_SPEEX, PT_DVI4

class Phone(BaseApplication):
    __implements__ = ( Application, )

    _startReactor = True

    def __init__(self, ui=None, audio=None):
        # Mapping from callcookies to rtp object
        self._rtp = {}
        # Mapping from callcookies to call objects
        self._calls = {}
        self._pendingRTP = {}
        self._audio = audio
        self.ui = ui
        self._currentCall = None
        self._muted = False
        self._rtpProtocolClass = None
        self._debugrev = 10

    def find_resource_file(self, fname):
        """ Return the fully-qualified path to the desired resource file that came bundled with Shtoom.  On failure, it returns fname.
        fname must be relative to the appropriate directory for storing this kind of file.
        Currently this works on Mac OS X and Linux.
        """
        if 'linux' in sys.platform.lower():
            shtoomdir = self.getPref('shtoomdir')
            if not shtoomdir:
                shtoomdir='.'
            return os.path.join(shtoomdir, 'share', 'shtoom', 'audio', fname)
        elif sys.platform == 'darwin':
            try:
                import ShtoomAppDelegate
                whereami = ShtoomAppDelegate.__file__
                return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(whereami))), fname)
            except:
                return fname
        else:
            return fname

    def play_wav_file(self, soundconfigurename):
        fname = self.getPref(soundconfigurename)
        if fname:
            fullfname = self.find_resource_file(fname)
            self._audio.play_wave_file(fullfname)

    def needsThreadedUI(self):
        return self.ui.threadedUI

    def boot(self, options=None, args=None):
        from shtoom.credcache import CredCache
        if options is None:
            options = buildOptions(self)
        self.initOptions(options, args)
        self.creds = CredCache(self)
        saved = self.getPref('credentials')
        if saved:
            self.creds.loadCreds(saved)
        if self.ui is None:
            self.ui = findUserInterface(self, self.getPref('ui'))
        l = self.getPref('logfile')
        if l:
            log.startLogging(open(l, 'aU'))
        BaseApplication.boot(self)

    def register(self):
        register_uri = self.getPref('register_uri')
        if register_uri is not None:
            return self.sip.register()

    def start(self):
        "Start the application."
        self.register()
        if not self._startReactor:
            log.msg("Not starting reactor - test mode?")
            return
        if self.needsThreadedUI():
            threadable.init(1)
            from twisted.internet import reactor
            t = threading.Thread(target=reactor.run, kwargs={
                                'installSignalHandlers':0} )
            t.start()
            self.ui.startUI()
        else:
            from twisted.internet import reactor
            if not hasattr(reactor,'running') or not reactor.running:
                reactor.run()

    def ringBack(self):
        self.play_wav_file('ring_back_file')

    def acceptCall(self, call):
        log.msg("dialog is %r"%(call.dialog))
        cookie = self.getCookie()
        self._calls[cookie] = call
        calltype = call.dialog.getDirection()
        if calltype == 'inbound':
            self.statusMessage('Incoming call')
            self.play_wav_file('incoming_ring_file')

            uidef = self.ui.incomingCall(call.dialog.getCaller(), cookie)
            uidef.addCallback(lambda x: self._createRTP(x,
                                        call.getLocalSIPAddress()[0],
                                        call.getSTUNState()))
            return uidef
        elif calltype == 'outbound':
            return self._createRTP(cookie, call.getLocalSIPAddress()[0],
                                           call.getSTUNState())
        else:
            raise ValueError, "unknown call type %s"%(calltype)
        return d

    def _createRTP(self, cookie, localIP, withSTUN):
        from shtoom.rtp.protocol import RTPProtocol
        from shtoom.exceptions import CallFailed
        if isinstance(cookie, CallFailed):
            del self._calls[cookie.cookie]
            return defer.succeed(cookie)

        self.ui.callStarted(cookie)
        if self._rtpProtocolClass is None:
            rtp = RTPProtocol(self, cookie)
        else:
            rtp = self._rtpProtocolClass(self, cookie)
        self._rtp[cookie] = rtp
        d = rtp.createRTPSocket(localIP,withSTUN)
        return d

    def selectDefaultFormat(self, callcookie, sdp, format=None):
        oldmediahandler = (self._audio and self._audio.codecker 
                                       and self._audio.codecker.handler)
        self._audio.close()
        if not sdp:
            self._audio.selectDefaultFormat([format,])
            return
        md = sdp.getMediaDescription('audio')
        rtpmap = md.rtpmap
        ptlist = [ x[1] for x in  rtpmap.values() ]
        self._audio.selectDefaultFormat(ptlist)
        if oldmediahandler:
            self._audio.reopen(oldmediahandler)

    def getSDP(self, callcookie, othersdp=None):
        rtp = self._rtp[callcookie]
        sdp = rtp.getSDP(othersdp)
        return sdp

    def startCall(self, callcookie, remoteSDP, cb):
        log.msg("startCall reopening %r %r"%(self._currentCall, self._audio))
        md = remoteSDP.getMediaDescription('audio')
        ipaddr = md.ipaddr or remoteSDP.ipaddr
        remoteAddr = (ipaddr, md.port)
        log.msg("call Start %r %r"%(callcookie, remoteAddr))
        self._currentCall = callcookie
        self._rtp[callcookie].start(remoteAddr)
        mediahandler = lambda x,c=callcookie: self.outgoingRTP(c, x)
        self.openAudioDevice([PT_PCMU,], mediahandler)
        log.msg("startCall opened %r %r"%(self._currentCall, self._audio))
        cb(callcookie)

    def outgoingRTP(self, cookie, sample):
        # XXX should the mute/nonmute be in the audio layer?
        if not self._muted:
            self._rtp[cookie].handle_media_sample(sample)

    def endCall(self, callcookie, reason=''):
        rtp = self._rtp.get(callcookie)
        log.msg("endCall clearing %r"%(callcookie))
        self._currentCall = None
        if rtp:
            rtp = self._rtp[callcookie]
            rtp.stopSendingAndReceiving()
            del self._rtp[callcookie]
            if self._calls.get(callcookie):
                del self._calls[callcookie]
            self.closeAudioDevice()
        self.ui.callDisconnected(callcookie, reason)

    def openAudioDevice(self, fmts=[PT_PCMU,], mediahandler=None):
        assert isinstance(fmts, (list, tuple,)), fmts
        assert self._audio
        self._audio.close()
        self._audio.selectDefaultFormat(fmts)
        self._audio.reopen(mediahandler)

    def closeAudioDevice(self):
        self._audio.close()

    def incomingRTP(self, callcookie, packet):
        from shtoom.rtp.formats import PT_NTE
        if packet.header.ct == PT_NTE:
            return None
        if self._currentCall != callcookie:
            return None
        try:
            self._audio.write(packet)
        except IOError:
            pass

    def placeCall(self, sipURL):
        return self.sip.placeCall(sipURL)

    def dropCall(self, cookie):
        call = self._calls.get(cookie)
        if call:
            d = call.dropCall()
        # xxx Add callback.
        #else:
        #    self.ui.callDisconnected(None, "no call")

    def startDTMF(self, cookie, digit):
        rtp = self._rtp[cookie]
        rtp.startDTMF(digit)

    def stopDTMF(self, cookie, digit):
        rtp = self._rtp[cookie]
        rtp.stopDTMF(digit)

    def statusMessage(self, message):
        self.ui.statusMessage(message)

    def debugMessage(self, message):
        self.ui.debugMessage(message)

    def appSpecificOptions(self, opts):
        app = OptionGroup('shtoom', 'Shtoom')
        app.add(ChoiceOption('ui',_('use UI for interface'), 
                            choices=['qt','gnome','wx', 'tk', 'text']))
        app.add(ChoiceOption('audio',_('use AUDIO for interface'), 
                    choices=['oss', 'fast', 'port', 'alsa', 'echo', 'file']))
        app.add(StringOption('audio_device',_('use this audio device')))
        # XXX TOFIX: This next option Must Die.
        app.add(StringOption('shtoomdir',_('root dir of shtoom installation')))
        app.add(StringOption('incoming_ring_file',
                                _('play this wav file when a call comes in'),
                                    'ring.wav'))
        app.add(StringOption('ring_back_file',
                    _('play this wav file when remote phone is ringing'),
                                    'ringback.wav'))


        app.add(StringOption('logfile',_('log to this file')))
        opts.add(app)
        creds = OptionDict('credentials', _('cached credentials'), gui=False)
        opts.add(creds)
        opts.setOptsFile('.shtoomrc')

    def authCred(self, method, uri, realm='unknown', retry=False):
        "Place holder for now"
        user = self.getPref('register_authuser')
        passwd = self.getPref('register_authpasswd')
        cachedcreds = self.creds.getCred(realm)
        print "checking for cached creds for %s: %r (retry %s)"%(realm, cachedcreds, retry)
        if user is not None and passwd is not None and retry is False:
            # for upgrades of people using the old option.
            if not self.creds.getCred(realm):
                self.creds.addCred(realm, user, pw, True)
            return defer.succeed((self.getPref('register_authuser'),
                                 self.getPref('register_authpasswd')))
        elif retry is False and cachedcreds:
            return defer.succeed(cachedcreds)
        # Not all user interfaces can prompt for auth yet
        elif hasattr(self.ui, 'getAuth'):
            def processAuth(res, realm=realm):
                if not res:
                    # No auth provided
                    return res
                if len(res) == 2:
                    # user, password
                    self.creds.addCred(realm, res[0], res[1], False)
                    return res
                elif len(res) == 3:
                    # user, password, save (bool)
                    user,pw,saveok = res
                    self.creds.addCred(realm, user, pw, saveok)
                    # XXX TOFIX save the credentials
                    return user, pw
            d = self.ui.getAuth(method, realm)
            d.addCallback(processAuth)
            return d
        else:
            return defer.fail(CallFailed("No auth available"))

    def muteCall(self, callcookie):
        if self._currentCall is not callcookie:
            raise ValueError("call %s is current call, not %s"%(
                                    self._currentCall, callcookie))
        else:
            self._muted = True

    def unmuteCall(self, callcookie):
        if self._currentCall is not callcookie:
            raise ValueError("call %s is current call, not %s"%(
                                    self._currentCall, callcookie))
        else:
            self._muted = False

    def switchCallAudio(self, callcookie):
        self._currentCall = callcookie
