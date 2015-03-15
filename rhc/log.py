'''
The MIT License (MIT)

Copyright (c) 2013-2015 Robert H Chase

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
import sys
import syslog
import time
from messagehandler import MessageHandler


class Log(object):

    def __init__(self):
        self.syslog = True  # turn syslog on/off
        self.logmsg = lambda x, y: None

    def setup(self, messagefile=[], name='LOG', facility=syslog.LOG_LOCAL4, verbose=False, stdout=False, silent=False):
        if not silent:
            handler = MessageHandler(messagefile, self, verbose, stdout)
            self.logmsg = handler.logmsg
            if stdout:
                self.syslog = False
            else:
                syslog.openlog(name, 0, facility)

    def stdout(self, message):
        print time.strftime('%Y%m%d-%H:%M:%S', time.localtime()),
        print message
        sys.stdout.flush()

    def __log(self, priority, message, header=None):
        if self.syslog:
            try:
                if header:
                    message = '%s %s' % (header, message)
                syslog.syslog(priority, message)
            except Exception:
                pass

    def debug(self, message):
        self.__log(syslog.LOG_DEBUG, message, '<G>')

    def info(self, message):
        self.__log(syslog.LOG_INFO, message, '<I>')

    def notice(self, message):
        self.__log(syslog.LOG_NOTICE, message, '<N>')

    def warning(self, message):
        self.__log(syslog.LOG_WARNING, message, '<W>')

    def danger(self, message):
        self.__log(syslog.LOG_ERR, message, '<E>')

    def critical(self, message):
        self.__log(syslog.LOG_CRIT, message, '<C>')


def logmsg(id, *args):
    LOG.logmsg(id, args)

LOG = Log()
