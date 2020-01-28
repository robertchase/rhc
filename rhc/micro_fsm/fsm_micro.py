from fsm.FSM import STATE, EVENT, FSM
# pylint: skip-file
# flake8: noqa
# add_config
# add_config_server
# add_connection
# add_header
# add_method
# add_old_server
# add_optional
# add_required
# add_resource
# add_resource_header
# add_route
# add_server
# add_setup
# add_teardown
# add_user
# silent
def create(**actions):
  S_old_init=STATE('old_init',on_enter=actions['add_config_server'])
  S_old_server=STATE('old_server',on_enter=actions['add_old_server'])
  S_route=STATE('route',on_enter=actions['add_route'])
  S_init=STATE('init')
  S_server=STATE('server',on_enter=actions['add_server'])
  S_connection=STATE('connection',on_enter=actions['add_connection'])
  S_old_route=STATE('old_route',on_enter=actions['add_route'])
  S_resource=STATE('resource',on_enter=actions['add_resource'])
  S_old_init.set_events([EVENT('teardown',[actions['add_teardown']]),EVENT('setup',[actions['add_setup']]),EVENT('config',[actions['add_config']]),EVENT('config_server',[actions['add_config_server']]),EVENT('server',[], S_old_server),])
  S_old_server.set_events([EVENT('teardown',[actions['add_teardown']]),EVENT('route',[], S_old_route),EVENT('config',[actions['add_config']]),EVENT('setup',[actions['add_setup']]),EVENT('server',[actions['add_old_server']]),])
  S_route.set_events([EVENT('silent',[actions['silent']]),EVENT('get',[actions['add_method']]),EVENT('teardown',[actions['add_teardown']]),EVENT('route',[actions['add_route']]),EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('put',[actions['add_method']]),EVENT('post',[actions['add_method']]),EVENT('config',[actions['add_config']]),EVENT('setup',[actions['add_setup']]),EVENT('delete',[actions['add_method']]),])
  S_init.set_events([EVENT('teardown',[actions['add_teardown']]),EVENT('setup',[actions['add_setup']]),EVENT('config_server',[], S_old_init),EVENT('server',[], S_server),EVENT('connection',[], S_connection),EVENT('user',[actions['add_user']]),EVENT('config',[actions['add_config']]),])
  S_server.set_events([EVENT('teardown',[actions['add_teardown']]),EVENT('route',[], S_route),EVENT('server',[actions['add_server']]),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),EVENT('setup',[actions['add_setup']]),])
  S_connection.set_events([EVENT('resource',[], S_resource),EVENT('header',[actions['add_header']]),EVENT('connection',[actions['add_connection']]),EVENT('config',[actions['add_config']]),EVENT('server',[], S_server),])
  S_old_route.set_events([EVENT('silent',[actions['silent']]),EVENT('get',[actions['add_method']]),EVENT('teardown',[actions['add_teardown']]),EVENT('route',[actions['add_route']]),EVENT('server',[], S_old_server),EVENT('put',[actions['add_method']]),EVENT('post',[actions['add_method']]),EVENT('config',[actions['add_config']]),EVENT('setup',[actions['add_setup']]),EVENT('delete',[actions['add_method']]),])
  S_resource.set_events([EVENT('resource',[], S_resource),EVENT('teardown',[actions['add_teardown']]),EVENT('optional',[actions['add_optional']]),EVENT('setup',[actions['add_setup']]),EVENT('required',[actions['add_required']]),EVENT('server',[], S_server),EVENT('header',[actions['add_resource_header']]),EVENT('connection',[], S_connection),EVENT('config',[actions['add_config']]),])
  return FSM([S_old_init,S_old_server,S_route,S_init,S_server,S_connection,S_old_route,S_resource])
