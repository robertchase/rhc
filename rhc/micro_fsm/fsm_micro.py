from rhc.fsm.FSM import STATE, EVENT, FSM
# add_config
# add_connection
# add_header
# add_method
# add_optional
# add_required
# add_resource
# add_route
# add_server
def create(**actions):
  S_connection=STATE('connection',enter=actions['add_connection'])
  S_init=STATE('init')
  S_resource=STATE('resource',enter=actions['add_resource'])
  S_route=STATE('route',enter=actions['add_route'])
  S_server=STATE('server',enter=actions['add_server'])
  S_connection.set_events([EVENT('resource',[], S_resource),EVENT('header',[actions['add_header']]),EVENT('connection',[actions['add_connection']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),])
  S_init.set_events([EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),])
  S_resource.set_events([EVENT('config',[actions['add_config']]),EVENT('connection',[], S_connection),EVENT('required',[actions['add_required']]),EVENT('optional',[actions['add_optional']]),EVENT('server',[], S_server),])
  S_route.set_events([EVENT('get',[actions['add_method']]),EVENT('route',[actions['add_route']]),EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('put',[actions['add_method']]),EVENT('post',[actions['add_method']]),EVENT('config',[actions['add_config']]),EVENT('delete',[actions['add_method']]),])
  S_server.set_events([EVENT('route',[], S_route),EVENT('config',[actions['add_config']]),EVENT('connection',[], S_connection),EVENT('server',[actions['add_server']]),])
  return FSM([S_connection,S_init,S_resource,S_route,S_server])
