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
import os
import re


class Config (object):

    '''
      Class to manage 'key.name=value' style configuration records.

      A Config is first initialized, probably by a sub-class, using the _define
      method. The _define method specifies each valid configuration type by
      supplying a name, which is a sequence of dot (.) delimited tokens, along
      with an optional initial value and optional validation function. The
      _define method also accepts a counter parameter, which is described in the
      'Indexed Names' section below.

      User supplied configuration values, perhaps from a configuration file (see
      _load), are specified to the _set method, which accepts a name and a
      value. The name must match a name specified with the _define method, and
      the value will be run through the validation function specified with the
      _define method.

      The config object will yield values for defined names using a standard
      python object syntax. So, if a configuration item is defined with the
      name 'server.address', and the configuration object is assigned to
      the variable 'cfg', then the 'server.address' value is accessed with this
      syntax:

        cfg.server.address

      as though it were a hierachy of python objects.

      Indexed Names

        It is also possible to have items which are indexed by a final numerical
        value, as in the 'url.host' items below:

          url.count = 2
          url.host.1 = http://www.google.com
          url.host.2 = http://www.yahoo.com

        These items must be defined using the counter parameter, and this
        parameter must reference a previously defined integer value. For
        instance:

          _define ('url.count', 0, validate_int)
          _define ('url.host', counter='url.count')
          _define ('url.port', 80, validate_int, counter='url.count')

        In this case 'url.count' specifies the highest index value that
        'url.host' or 'url.port' can have. The index value must be between one
        and the specified counter value, inclusive. The syntax for referencing
        an indexed name is:

          cfg.url.host [1]
          cft.url.port [1]

      NOTES:

      1. Methods are prepended with '_' in order not to pollute the namespace
         used by the defined values.

      2. Valid names are composed of letters, digits, underscores and periods.
         No part of a valid name can be composed only of digits, except for the
         final part of an Indexed Name.

      3. The _load function ignores leading and trailing whitespace in the
         names and values.

      4. The _load function ignores anything including and following a '#'
         character, thus allowing for comments. To prevent a '#' value from
         starting a comment, escape it by preceeding it with a '\' character.

      5. The value parameter of the _define function is the initial value for
         the item, or the default value if the item is an Indexed Name.

      6. If the env parameter is specified on the _define function, and an
         env variable of this name is set, then the value of the env variable
         overrides the 'value' parameter and any parmemter read from the config
         file.

    '''

    def __init__(self):
        self.__values = ConfigItem()
        self.__direct = {}

    def __getattr__(self, name):
        return getattr(self.__values, name)

    def _define(self, name, value=None, validator=None, counter=None, env=None):
        item = self.__values
        for part in name.split('.'):
            if not isinstance(item._value, dict):
                raise AttributeError(
                    "Leaf node cannot be extended with '%s'" % part)
            if part not in item._value:
                item._value[part] = ConfigItem()
            item = item._value[part]
        if isinstance(item._value, dict) and len(item._value):
            raise AttributeError(
                "Non-leaf node '%s' cannot be assigned" % part)
        item._validator = validator
        item._env = os.getenv(env)
        if counter:
            if counter not in self.__direct:
                raise AttributeError(
                    "Counter parameter '%s' not defined" % counter)
            if not isinstance(self.__direct[counter]._value, int):
                raise AttributeError("Counter parameter '%s' must be an integer" %
                                     counter)
            item._counter = self.__direct[counter]
            item._default = value
        else:
            item._value = value
        self.__direct[name] = item

    def _set(self, name, value):
        if name in self.__direct:
            item = self.__direct[name]
            if item._validator:
                value = item._validator(value)
            item._value = value
        else:
            toks = name.split('.')
            try:
                count = int(toks[-1])
                countedname = '.'.join(toks[:-1])
                item = self.__direct[countedname]
                counter = item._counter._value
            except:
                raise AttributeError(
                    "'%s' is not a defined config parameter" % name)
            if count < 1 or count > counter:
                raise AttributeError("'%s' counter is out of range" % name)
            if item._validator:
                value = item._validator(value)
            item._value[str(count)] = value

    def _load(self, filename):
        for lineno, line in enumerate(open(filename), start=1):

            m = re.match(r'(.*?[^\\])?#', line)  # look for first non-escaped comment indicator ('#')
            if m:
                line = m.group(1) if m.group(1) is not None else ''  # grab everything before the '#' (could be None if full-line comment)
            line = line.replace('\#', '#')
            line = line.strip()
            if 0 == len(line):
                continue

            match = re.match(r'([\w\.]+?)\s*=\s*(.*)$', line)
            if match:
                try:
                    self._set(match.group(1), match.group(2))
                except Exception, e:
                    raise Exception('Error on line %d of %s: %s' % (lineno, filename, e))
            else:
                raise ValueError('Error on line %d of %s: invalid syntax' % (lineno, filename))


class ConfigItem (object):

    def __init__(self, name=None):
        self._value = {}
        self._validator = None
        self._counter = None
        self._default = None

    def __getattr__(self, name):
        if name in self._value:
            item = self._value[name]
            if item._counter or isinstance(item._value, dict):
                return item
            return item._env if item._env else item._value
        raise AttributeError("'%s' not found" % name)

    def __getitem__(self, key):
        key = str(key)
        if self._default:
            return self._value.setdefault(key, self._default)
        return self._value[key]


def validate_int(value):
    return int(value)


def validate_bool(value):
    if value in (True, False):
        return value
    return {'TRUE': True, 'FALSE': False}[value.upper()]


def validate_file(value):
    if os.path.isfile(value):
        return value
    raise Exception('%s not found' % value)


class Stub(object):

    '''
        Stub is a useful way to 'stub up' a Config-like object
        for test purposes. You can assign values to dot-separated
        attributes of a Stub, and it will automatically construct
        the appropriate object trees to handle it pythonically.
    '''

    def __init__(self, name='STUB'):
        self.__name = name
        self.__values = {}

    def __str__(self):
        return self.__name

    def __getattr__(self, name):
        return self.__values.setdefault(name, Stub(name))

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
