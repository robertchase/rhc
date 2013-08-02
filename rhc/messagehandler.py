'''
The MIT License (MIT)

Copyright (c) 2013 Robert H Chase

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
import os, re, sys, time

class MessageHandler (object):
  '''
    MessageHandler - manage messages in an external file
    
    A MessageHandler separates message text, message severity and message
    display from the logic of a program. By changing attributes of the message
    in the message file, or by supplying an alternative set of display
    functions, the message characteristics can be controlled without
    changing program code.
    
    To display a message, a program supplies the message id and any
    substitution values:
    
      handler.logmsg (message_id, (sub1, sub2...))
      
    The text of the message, the log level of the message, and whether or not
    the message is even displayed, are all specified externally to the logmsg
    call.
    
    Parameters:
    
      filename   - a message file, or list of message files, formatted to
                   be read by the loadfile function (see below)
      display_fn - an object specifying display functions (see MessageDisplay
                   below)
      verbose    - True if verbose messages are to be displayed
      stdout     - True if messages are to be displayed using stdout (supplied
                   by display_fn)
  '''
  def __init__ (self, filename, display_fn, verbose=False, stdout=False):
    self.verbose = verbose
    self.stdout = stdout
    self.__messages = {}
    if not isinstance (filename, list):
      filename = [filename]
    for f in filename:
      self.__messages = loadfile (f, self.__messages)
    self.__functions = display_fn
    
  def logmsg (self, id, args=None):
    '''
      Format (substitute) and display a message identified by id
    '''
    msg = self.__messages [str (id)]
    msg.display (args, self.__functions, self.verbose, self.stdout)

class Message (object):
  '''
    Message attribute container and display handler.
  '''
  def __init__ (self, id, text,
      log='INFO',
      always=True, verbose=True, envvar=None):
    self.id = id
    self.text = text
    self.log = log
    self.display_always = always
    self.display_verbose = verbose
    self.display_when_envvar = envvar
    
  def format (self, args):
    if args:
      return self.text % args
    return self.text
    
  def display (self, args, fn, verbose=False, stdout=False):

    env = False
    if self.display_when_envvar:
      if os.getenv (self.display_when_envvar):
        env = True
        
    if self.display_always or (self.display_verbose and verbose) or env:
      msg = self.format (args)
      for m in msg.splitlines ():
        if 'DEBUG' == self.log: fn.debug (m)
        elif 'INFO' == self.log: fn.info (m)
        elif 'NOTICE' == self.log: fn.notice (m)
        elif 'WARNING' == self.log: fn.warning (m)
        elif 'DANGER' == self.log: fn.danger (m)
        elif 'CRITICAL' == self.log: fn.critical (m)
      if stdout:
        for m in msg.splitlines ():
          fn.stdout (m)
      
def loadfile (filename, set={}):
  '''
    Generate a dictionary of Message objects indexed by message.id, from a
    file.
    
    The file contains the following records for each message:
    
      MESSAGE id
      LOG     DEBUG|INFO|NOTICE|WARNING|DANGER|CRITICAL
      DISPLAY ALWAYS|VERBOSE|ENV=varname
      TEXT message text
      
    The MESSAGE and TEXT records are required. LOG defaults to INFO and
    DISPLAY defaults to ALWAYS.
      
    NOTES:
      
      1. All records following a MESSAGE record belong to that message id
         until a new MESSAGE record is encountered, or until end of file.
         
      2. Multiple TEXT records produce a multi-line message.
      
      3. The DISPLAY attribute 'ENV=' indicates that the message will only be
         displayed if the specified environment variable is set. The variable
         can be set to anything.
         
      4. Duplicate MESSAGE records are allowed, the latest message 'wins'.
         Multiple files can be processed by calling this function for each
         file and passing the result to subsequent calls. Duplicate messages
         found in later files will replace those found in earlier files.
         
      5. Duplicate LOG or DISPLAY records are allowed for a single message,
         the latter overrides the former.
         
      6. Anything including and following a '#' character is ignored, thus
         allowing for comments.
  '''
  set = set
  id = text = None

  for lineno, line in enumerate (open (filename), start=1):
  
    line = line.split('#', 1)[0].strip()
    if len (line) == 0: continue

    match = re.match (r'MESSAGE\s+(\w+)$', line)
    if match:
      if id and text:
        set [id] = Message (id, text, log, always, verbose, envvar)
      id = match.group (1)
      text = None
      log = 'INFO'
      always = True
      verbose = True
      envvar = None
      continue
        
    match = re.match (r'LOG\s+((DEBUG)|(INFO)|(NOTICE)|(WARNING)|(DANGER)|(CRITICAL))$', line)
    if match:
      log = match.group (1)
      continue

    match = re.match (r'DISPLAY\s+((ALWAYS)|(VERBOSE)|(ENV=\w+))$', line)
    if match:
      token = match.group (1)
      if 'ENV=' == token [:4]:
        always = verbose = False
        envvar = token [4:]
      elif 'VERBOSE' == token:
        always = False
        verbose = True
      else:
        always = verbose = True
      continue
        
    match = re.match (r'TEXT\s(.*)$', line)
    if match:
      if text:
        text += '\n' + match.group (1)
      else:
        text = match.group (1)
      continue
      
    raise Exception ('Line %d of %s is invalid' % (lineno, filename))
    
  if id and text:
    set [id] = Message (id, text, log, always, verbose, envvar)
    
  return set
        
class MessageDisplay (object):
  '''
    Very limited-function MessageDisplay object demonstrating the methods that
    must be specified for full MessageHandler operation.
  '''

  def stdout (self, msg):
    print time.strftime ('%Y%m%d-%H:%M:%S', time.localtime ()),
    print msg
    sys.stdout.flush ()

  def debug (self, msg):
    self.stdout (msg)
  def info (self, msg):
    self.stdout (msg)
  def notice (self, msg):
    self.stdout (msg)
  def warning (self, msg):
    self.stdout (msg)
  def danger (self, msg):
    self.stdout (msg)
  def critical (self, msg):
    self.stdout (msg)

if '__main__' == __name__:
  h = MessageHandler ('MessageHandler.msg', MessageDisplay ())
  h.logmsg (100, (1, 10, 'yepper'))
