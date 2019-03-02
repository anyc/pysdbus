#! /usr/bin/env python
#
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
import pysdbus

def show_iface(obj, iface, signatures=None):
	if signatures is None:
		signatures = obj.getSignatures()
	
	if iface in signatures:
		for item in signatures[iface]:
			entry = signatures[iface][item]
			if entry["type"] in ["method", "signal"]:
				out_sign = entry.get("out", "")
				in_sign = entry.get("in", "")
				
				print("\t", item+"("+in_sign+")"+" = "+out_sign+"")
			else:
				print("\t", item+" \""+entry["signature"]+"\" "+entry["access"])

if __name__ == '__main__':
	from argparse import ArgumentParser, REMAINDER
	
	ap = ArgumentParser()
	ap.add_argument("--remote")
	ap.add_argument("--system", action="store_true")
	ap.add_argument("-d", "--debug", action="store_true")
	
	ap.add_argument('argv', nargs=REMAINDER)
	args = ap.parse_args()
	
	if args.debug:
		pysdbus.llapi.debug = True
	
	if args.remote:
		bus = pysdbus.RemoteSystemBus(args.remote)
	elif args.system:
		bus = pysdbus.SystemBus()
	else:
		try:
			bus = pysdbus.UserBus()
		except Exception as e:
			if e.errno == -2:
				bus = pysdbus.SystemBus()
			else:
				raise
	
	argv = [sys.argv[0]] + args.argv
	
	if len(argv) == 1:
		obj = bus.getObject("org.freedesktop.DBus", "/org/freedesktop/DBus")
		
		iface = obj.getInterface("org.freedesktop.DBus")
		
		reply = iface.ListNames()
		
		dbus_obj = bus.getObject("org.freedesktop.DBus", "/org/freedesktop/DBus")
		dbus_iface = dbus_obj.getInterface("org.freedesktop.DBus")
		
		dic = {}
		for name in reply:
			pid = dbus_iface.GetConnectionUnixProcessID(name)
			if pid not in dic:
				dic[pid] = []
			dic[pid].append(name)
		
		print("ProcessID | Services")
		for pid in sorted(dic.keys()):
			services = sorted(dic[pid])
			print(pid, "|", " ".join(services))
		
		sys.exit(0)
	
	if len(argv) >= 2:
		service = argv[1]
	
	if len(argv) >= 3:
		path = argv[2]
		
		obj = bus.getObject(service, path)
	else:
		def print_obj_tree(obj_path):
			obj = bus.getObject(service, obj_path)
			
			intro_proxy = obj.getIntrospectProxy()
			intro_proxy.parse()
			
			for node in intro_proxy.root.findall("node"):
				name = obj_path.rstrip("/")+"/"+node.attrib["name"]
				
				print(name)
				
				print_obj_tree(name)
		
		print_obj_tree("/")
		
		sys.exit(0)
	
	if len(argv) >= 4:
		iface = argv[3]
	else:
		signatures = obj.getSignatures()
		
		for iface in sorted(signatures.keys()):
			print(iface)
			
			show_iface(obj, iface, signatures)
		
		sys.exit(0)
	
	if len(argv) >= 5:
		item = argv[4]
	else:
		show_iface(obj, iface)
		sys.exit(0)
	
	if len(argv) >= 6:
		prop_iface = obj.getInterface(pysdbus.dbus_properties_interface)
		
		prop_iface.Set(iface, item, "s", argv[5], signature="ssv")
	else:
		prop_iface = obj.getInterface(pysdbus.dbus_properties_interface)
		
		try:
			value = prop_iface.Get(iface, item)
			found = True
		except Exception as e:
			if isinstance(e, OSError) and e.errno == -53:
				found = False
			else:
				raise
		
		if found:
			print(iface, item, value)
			sys.exit(0)
		
		obj_iface = obj.getInterface(iface)
		
		mp = pysdbus.MethodProxy(obj_iface, item)
		
		print(mp.call())
