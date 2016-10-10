from rhc.fsm.fsm_machine import create as create_machine


class Parser(object):

    def __init__(self):
        self.error = None
        self.states = {}
        self.state = None
        self.event = None
        self.actions = {}
        self.fsm = create_machine(
            action=self.act_action,
            enter=self.act_enter,
            event=self.act_event,
            exit=self.act_exit,
            state=self.act_state,
        )
        self.fsm.state = 'init'

    def __str__(self):
        states = self.states
        d = 'from rhc.fsm.FSM import STATE, EVENT, FSM\n'
        d += '\n'.join('# ' + a for a in sorted(self.actions))
        d += '\ndef create(**actions):\n'
        d += '\n'.join(self.define(s) for s in states.values())
        d += '\n' + '\n'.join(self.set_events(s) for s in states.values())
        d += '\n  return FSM([' + ','.join('S_' + s for s in states) + '])'
        return d

    @classmethod
    def parse(cls, data):
        parser = cls()
        for num, line in enumerate(data, start=1):
            line = line.split('#', 1)[0].strip()
            if len(line):
                line = line.split(' ', 1)
                if len(line) == 1:
                    raise Exception('too few tokens, line=%d' % num)

                event, parser.line = line
                if not parser.fsm.handle(event.lower()):
                    raise Exception("Unexpected directive '%s', line=%d" % (event, num))
                if parser.error:
                    raise Exception('%s, line=%d' % (parser.error, num))
        return parser

    @staticmethod
    def define(state):
        s = "  S_%s=STATE('%s'" % (state['name'], state['name'])
        if state['enter']:
            s += ",enter=actions['%s']" % state['enter']
        if state['exit']:
            s += ",exit=actions['%s']" % state['exit']
        return s + ')'

    @staticmethod
    def set_events(state):
        s = "  S_%s.set_events([" % state['name']
        for e in state['events'].values():
            s += "EVENT('%s',[" % e['name']
            s += ','.join("actions['%s']" % a for a in e['actions'])
            s += ']'
            if e['next']:
                s += ', S_%s' % e['next']
            s += "),"
        s += '])'
        return s

    def act_state(self):
        if len(self.line.split()) != 1:
            self.error = 'STATE name must be a single token'
            return 'error'
        name = self.line.strip()
        if name in self.states.keys():
            self.error = 'duplicate STATE name'
            return 'error'
        self.state = dict(name=name, enter=None, exit=None, events={})
        self.states[name] = self.state

    def act_enter(self):
        if len(self.line.split()) != 1:
            self.error = 'ENTER action must be a single token'
            return 'error'
        name = self.line.strip()
        if self.state['enter'] is not None:
            self.error = 'only one ENTER action allowed'
            return 'error'
        self.state['enter'] = name
        self.actions[name] = True

    def act_exit(self):
        if len(self.line.split()) != 1:
            self.error = 'EXIT action must be a single token'
            return 'error'
        name = self.line.strip()
        if self.state['exit'] is not None:
            self.error = 'only one EXIT action allowed'
            return 'error'
        self.state['exit'] = name
        self.actions[name] = True

    def act_event(self):
        if len(self.line.split()) == 2:
            name, next_state = self.line.strip().split()
        elif len(self.line.split()) != 1:
            self.error = 'EVENT can only have one or two tokens'
            return 'error'
        else:
            name = self.line.strip()
            next_state = None
        self.event = dict(name=name, actions=[], next=next_state)
        self.state['events'][name] = self.event

    def act_action(self):
        if len(self.line.split()) != 1:
            self.error = 'ACTION can only have one token'
            return 'error'
        name = self.line.strip()
        if name in self.event['actions']:
            self.error = 'duplicate ACTION name'
            return 'error'
        self.event['actions'].append(name)
        self.actions[name] = True


if __name__ == '__main__':
    import sys

    f = open(sys.argv[1]) if len(sys.argv) > 1 else sys.stdin
    fsm = Parser.parse(f.readlines())
    print fsm
