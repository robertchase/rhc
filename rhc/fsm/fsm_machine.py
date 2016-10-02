from FSM import STATE, EVENT, FSM
# action
# enter
# event
# exit
# state
def create(actions):
  S_init=STATE('init')
  S_error=STATE('error')
  S_state=STATE('state',enter=actions['state'])
  S_event=STATE('event',enter=actions['event'])
  S_init.set_events([EVENT('state',[], S_state),])
  S_error.set_events([])
  S_state.set_events([EVENT('state',[], S_state),EVENT('enter',[actions['enter']]),EVENT('exit',[actions['exit']]),EVENT('event',[], S_event),EVENT('error',[], S_error),])
  S_event.set_events([EVENT('action',[actions['action']]),EVENT('state',[], S_state),EVENT('event',[], S_event),EVENT('error',[], S_error),])
  return FSM([S_init,S_error,S_state,S_event])
