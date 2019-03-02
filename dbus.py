# pysdbus
#
# Copyright (C) 2019 Mario Kicherer (dev@kicherer.org)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#

from __future__ import print_function
import sys

from llapi import *
from header import *
import pysdbus

class MessageProxy(pysdbus.MessageProxy):
	pass

class ObjectProxy(pysdbus.ObjectProxy):
	pass

class Interface(pysdbus.InterfaceProxy):
	def connect_to_signal(self, signal_name, handler, *args, **kwargs):
		return self.object_proxy.bus.add_signal_receiver(handler, signal_name,
						dbus_interface=self.iface_name,
						bus_name=self.object_proxy.service,
						path=self.object_proxy.path,
						*args,
						**kwargs)

class SignalMatch():
	def __init__(self, match_obj=None):
		self.match_obj = match_obj
	
	def remove(self):
		self.match_obj.remove()
	
	def pysdbus_callback(self, msg, userdata, ret_error):
		mp = MessageProxy(msg)
		
		self.user_callback(sender=mp.sender, destination=mp.destination,
						path=mp.path, interface=mp.interface, member=mp.member)
		
		return 0

class Bus():
	def __init__(self):
		mainloop.addBus(self)
	
	def get_object(self, service, path):
		return ObjectProxy(self, service, path)
	
	def add_signal_receiver(self, callback, signal_name=None,
							dbus_interface=None, bus_name=None, path=None):
		
		match_string = "type='signal'"
		if dbus_interface:
			match_string += ",interface='"+dbus_interface+"'"
		if bus_name:
			match_string += ",sender='"+bus_name+"'"
		if path:
			match_string += ",path='"+path+"'"
		if signal_name:
			match_string += ",member='"+signal_name+"'"
		
		sm = SignalMatch()
		
		sm.user_callback = callback
		sm.match_obj = self.add_match(match_string, sm.pysdbus_callback, raw_callback=True)
		
		return sm

class SessionBus(pysdbus.UserBus, Bus):
	def __init__(self):
		pysdbus.UserBus.__init__(self)
		Bus.__init__(self)

class SystemBus(pysdbus.SystemBus, Bus):
	def __init__(self):
		pysdbus.SystemBus.__init__(self)
		Bus.__init__(self)

class DBusMainLoop(pysdbus.EventLoop):
	def run(self):
		self.loop()
	
	def quit(self):
		self.stop()

def MainLoop():
	return mainloop

mainloop = DBusMainLoop()

if __name__ == '__main__':
	import os
	
	if "VERBOSITY" in os.environ:
		verbosity = int(os.environ["VERBOSITY"])
	
	ml = MainLoop()
	
	bus = SystemBus()
	
	dbus_obj = bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
	
	iface = Interface(dbus_obj, "org.freedesktop.DBus")
	
	reply = iface.ListNames()
	
	print(reply)
	
	def prop_changed_cb(sender, destination, path, interface, member):
		print("new signal: ", sender, destination, path, interface, member)
	
	bus.add_signal_receiver(prop_changed_cb)
	
	def nameowner_changed_cb(sender, destination, path, interface, member):
		print("nameowner changed: ", sender, destination, path, interface, member)
	
	iface.connect_to_signal("NameOwnerChanged", nameowner_changed_cb)
	
	ml.run()
	
