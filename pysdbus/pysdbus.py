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
from functools import wraps as ft_wraps
import sys, os

from .llapi import *
from .header import *

class PropertyNotFound(Exception):
	def __init__(self, obj, intf, prop):
		self.obj = obj
		self.intf = intf
		self.prop = prop

class MethodNotFound(Exception):
	def __init__(self, obj, intf, method):
		self.obj = obj
		self.intf = intf
		self.method = method

class ElementNotFound(Exception):
	def __init__(self, obj, intf, element):
		self.obj = obj
		self.intf = intf
		self.method = element

class PeerNotFound(Exception):
	def __init__(self, obj):
		self.obj = obj

class DBusValue(object):
	def __init__(self, *args, **kwargs):
		self.signature = None

class BasicType(DBusValue):
	codes="ybnqiuxtdsog"
	
	@staticmethod
	def getClass(signature, offset):
		for c in [String, ObjectPath, Signature] + [Boolean] + number_types:
			if signature[offset] in c.codes:
				return c
	
	@staticmethod
	def getSignature(var):
		for c in [String, ObjectPath, Signature] + [Boolean] + number_types:
			sign = c.getSignature(var)
			if sign:
				return sign
	
	def init_from_msg(self, msg, signature, offset):
		if signature[offset] not in self.__class__.codes:
			raise Exception("invalid type", signature[offset], "for", self.__class__)
		
		self.signature = signature[offset]
		self.sign_idx_last = offset

class Boolean(int, BasicType):
	codes=["b"]
	c_type = ct.c_uint32
	
	@staticmethod
	def getSignature(var):
		if type(var) == bool:
			return "b"
	
	@classmethod
	def getObject(cls, msg, signature, offset):
		if msg:
			value = ct.c_int()
			sd_bus_message_read_basic(msg, signature[offset], ct.byref(value))
			
			value = (value.value == 1)
		else:
			value = False
		
		obj = cls(value)
		
		obj.signature = signature[offset]
		obj.sign_idx_last = offset
		
		return obj

class NumberClass(BasicType):
	def __init__(self, value):
		self.value = value
	
	def __int__(self):
		return self.value
	
	def __float__(self):
		return self.value
	
	def __repr__(self):
		return str(self.value)
	
	@classmethod
	def getObject(cls, msg, signature, offset):
		if msg:
			value = cls.c_type()
			sd_bus_message_read_basic(msg, signature[offset], ct.byref(value))
			value = value.value
		else:
			value = 0
		
		obj = cls(value)
		
		obj.signature = signature[offset]
		obj.sign_idx_last = offset
		
		return obj
	
	@staticmethod
	def getSignature(var):
		for c in number_types:
			if isinstance(var, c.py_type) and c.limits[0] <= var and var <= c.limits[1]:
				return c.codes

def get_number_limits(ctype):
	signed = ctype(-1).value < ctype(0).value
	size_in_bits = ct.sizeof(ctype) * 8
	signed_limit = 2 ** (size_in_bits - 1)
	if signed:
		return (-signed_limit, signed_limit - 1)
	else:
		return (0, 2 * signed_limit - 1)

number_types = []
number_to_type = [
	("Byte", "y", ct.c_uint8, int),
	("UInt16", "q", ct.c_uint16, int),
	("UInt32", "u", ct.c_uint32, int),
	("Uint64", "t", ct.c_uint64, int),

	("Int16", "n", ct.c_int16, int),
	("Int32", "i", ct.c_int32, int),
	("Int64", "x", ct.c_int64, int),

	("Double", "d", ct.c_double, float),
	]

for triple in number_to_type:
	c = type(triple[0], (NumberClass, ), {
		"codes": triple[1],
		"c_type": triple[2],
		"py_type": triple[3],
		"limits": get_number_limits(triple[2]),
		})
	setattr(sys.modules[__name__], triple[0], c)
	number_types.append(c)

class String(BasicType, str):
	codes=["s"]
	
	def __init__(self, s):
		str.__init__(self)
		BasicType.__init__(self)
	
	@staticmethod
	def getSignature(var):
		if isinstance(var, str):
			return "s"
	
	@classmethod
	def getObject(cls, msg, signature, offset):
		if msg:
			value = ct.c_char_p()
			sd_bus_message_read_basic(msg, signature[offset], ct.byref(value))
			
			if sys.version_info >= (3,):
				value = value.value.decode()
			else:
				value = value.value
		else:
			value = "dummy"
		
		obj = cls(value)
		
		obj.signature = signature[offset]
		obj.sign_idx_last = offset
		
		return obj

class ObjectPath(String):
	codes=["o"]

class Signature(String):
	codes=["g"]

class Struct(DBusValue, tuple):
	codes=["r", "("]
	
	@staticmethod
	def getSignature(var):
		if isinstance(var, tuple):
			s = guess_signature(var[0])
			
			return "("+s+")"
	
	@classmethod
	def getObject(cls, msg, signature, offset):
		if signature[offset] != "(":
			raise Exception("not a struct", signature[offset:])
		
		lvl = 1
		i = offset
		while lvl > 0:
			i += 1
			if i >= len(signature):
				raise Exception("no matching ) found", signature[offset:])
			if signature[i] == "(":
				lvl += 1
			elif signature[i] == ")":
				lvl -= 1
		
		body_signature = signature[offset+1:i]
		
		if msg:
			sd_bus_message_enter_container(msg, "r", body_signature)
			
			subobjs = parse_signature(msg, signature[:i], offset+1)
			obj = cls(subobjs)
			
			sd_bus_message_exit_container(msg)
		else:
			obj = cls()
		
		obj.signature = signature[offset:i+1]
		obj.body_signature = body_signature
		obj.sign_idx_last = i
		
		return obj

class Variant(DBusValue, list):
	codes=["v"]
	
	@classmethod
	def getObject(cls, msg, signature, offset):
		if msg:
			typ = ct.c_char()
			content_sign = ct.c_char_p()
			
			sd_bus_message_peek_type(msg, ct.byref(typ), ct.byref(content_sign))
			
			sd_bus_message_enter_container(msg, "v", content_sign)
			
			if sys.version_info >= (3,):
				s = content_sign.value.decode()
			else:
				s = content_sign.value
			
			if verbosity > 1:
				print("variant content signature:", s)
			
			objs = parse_signature(msg, s, 0)
			
			sd_bus_message_exit_container(msg)
			
			if len(objs) != 1:
				raise Exception("unexpected number of objects", len(objs), objs)
			
			objs[0].sign_idx_last += offset
			
			return objs[0]
		else:
			obj = cls()
			obj.append("dummy_value")
			obj.signature = signature[offset]
			obj.sign_idx_last = offset
			return obj

class DictItem(DBusValue, list):
	codes=["e", "{"]
	
	def init_from_msg(self, msg, signature, offset):
		if signature[offset] != "{":
			raise Exception("not a dict", signature[offset:])
		
		lvl = 1
		i = offset
		while lvl > 0:
			i += 1
			if i >= len(signature):
				raise Exception("no matching } found", signature[offset:])
			if signature[i] == "{":
				lvl += 1
			elif signature[i] == "}":
				lvl -= 1
		
		self.signature = signature[offset:i+1]
		self.body_signature = signature[offset+1:i]
		self.sign_idx_last = i
		
		if msg:
			sd_bus_message_enter_container(msg, "e", self.body_signature)
			
			subobjs = parse_signature(msg, signature[:i], offset+1)
			self.extend( subobjs )
			
			sd_bus_message_exit_container(msg)
		else:
			self.extend( parse_signature(None, signature[:i], offset+1) )

class BaseArray(DBusValue):
	codes=["a"]
	
	@staticmethod
	def getClass(signature, offset):
		if signature[offset] == "a" and signature[offset+1] == "{":
			return Dictionary
		else:
			return type("Array", (Array, list, ), {})
	
	@staticmethod
	def getSignature(var):
		if isinstance(var, list):
			return "av"
		if isinstance(var, dict):
			if len(var) > 0:
				s = guess_signature(var.keys()[0])
			else:
				s = "s"
			return "a{"+s+"v}"
	
	def init_from_msg(self, msg, signature, offset):
		if signature[offset] not in self.__class__.codes:
			raise Exception("not an array", signature, offset)
		
		subobjs = parse_signature(None, signature, offset+1, one_item=True)
		
		body_end = subobjs[-1].sign_idx_last+1
		self.body_signature = signature[offset+1:subobjs[-1].sign_idx_last+1]
		self.signature = "a"+self.body_signature
		self.sign_idx_last = subobjs[-1].sign_idx_last
		
		if isinstance(self, Dictionary):
			if len(subobjs) != 1:
				raise Exception("not a dict", self.signature, len(subobjs), subobjs)
			if len(subobjs[0]) != 2:
				raise Exception("not a dict", self.signature, len(subobjs[0]), subobjs[0])
			if not isinstance(subobjs[0][0], BasicType):
				raise Exception("not a dict", self.signature, subobjs[0])
		
		if msg:
			sd_bus_message_enter_container(msg, "a", self.body_signature)
			
			while True:
				r = sd_bus_message_at_end(msg, 0)
				if r == 1:
					break
				
				subobjs = parse_signature(msg, signature[:body_end], offset+1)
				
				if len(subobjs) > 0:
					if isinstance(self, Dictionary):
						self[subobjs[0][0]] = subobjs[0][1]
					else:
						self.append(subobjs[0])
				else:
					raise Exception("Unexpected number of objects", len(subobjs), subobjs)
			
			sd_bus_message_exit_container(msg)

class Array(list, BaseArray):
	def __init__(self, *args, **kwargs):
		if "signature" in kwargs:
			self.signature = kwargs["signature"]
			del kwargs["signature"]
		
		if len(args) == 0:
			args = ([], )
		
		super(Array, self).__init__(*args, **kwargs)
	

class Dictionary(dict, BaseArray):
	pass

def parse_signature(msg, signature, offset, one_item=False):
	if offset >= len(signature):
		return
	
	if verbosity > 1:
		print("parsing:", signature[offset], signature, msg)
	
	objs = tuple()
	while offset < len(signature):
		if verbosity > 2:
			print("parsing next:", signature[offset])
		o = None
		for c in [Array, BasicType, Variant, DictItem, Struct]:
			if signature[offset] in c.codes:
				if hasattr(c, "getClass"):
					c = c.getClass(signature, offset)
				
				if hasattr(c, "getObject"):
					o = c.getObject(msg, signature, offset)
				else:
					o = c()
					o.init_from_msg(msg, signature, offset)
				
				break
		
		if o is None:
			raise Exception("unknown type", signature[offset], signature)
		else:
			objs += (o,)
			offset = o.sign_idx_last + 1
		
		if one_item:
			break
	
	return objs

def guess_signature(*args):
	signature = ""
	
	for obj in args:
		for c in [Array, BasicType, Struct]:
			sign = c.getSignature(obj)
			if sign:
				signature += sign
	
	return signature

def python2dbus(signature, *values):
	if len(values) == 0 and (not signature or signature == ""):
		return
	
	skeleton = parse_signature(None, signature, 0)
	
	local_verbose = verbosity > 1
	if local_verbose:
		print("converting values", "\"%s\"" % signature, values)
	
	result = Struct()
	result.signature = signature
	
	i = 0
	for item in skeleton:
		#print(values, s, type(item), item.signature, item.body_signature if hasattr(item, "body_signature") else None)
		
		value = values[i]
		
		if isinstance(item, BaseArray):
			if local_verbose:
				if isinstance(item, list):
					print("\tadd array", item.body_signature)
				elif isinstance(item, dict):
					print("\tadd dict", item.body_signature)
			
			if isinstance(item, list):
				subresult = Array()
				for val in value:
					subresult.append( python2dbus(item.body_signature, val) )
			elif isinstance(item, dict):
				subresult = Array()
				for key in value:
					subresult.append( python2dbus(item.body_signature, (key, value[key])) )
			else:
				raise Exception("unexpected array type", type(item), item, item.signature)
			
			result += (subresult, )
		
		elif isinstance(item, DictItem):
			if local_verbose:
				print("\tadd dict item \"%s\": { %s, %s }" % (item.body_signature, str(value[0]), str(value[1])))
			
			key = python2dbus(item[0].signature, value[0])
			val = python2dbus(item[1].signature, value[1])
			
			result += tuple( (key, val) )
		
		elif isinstance(item, Variant):
			if isinstance(value, DBusValue):
				sign = value.signature
			else:
				sign = guess_signature(value)
			
			if local_verbose:
				print("\tadd variant", sign, "value:", value)
			
			result += tuple( python2dbus(sign, value) )
		
		elif isinstance(item, Struct):
			if local_verbose:
				print("\tadd struct", item.body_signature)
			
			subresult = tuple()
			
			j = 0
			for val in value:
				subresult += tuple( python2dbus(item.body_signature[j], val) )
				j+=1
			
			result += tuple( subresult )
		
		elif isinstance(item, BasicType):
			c = item.__class__
			if isinstance(item, NumberClass) or isinstance(item, Boolean):
				value = c.c_type(value)
				
				self.value_cache.append( value )
			
			if local_verbose:
				print("\tadd basic type", c, c.codes[0], value)
			
			#sd_bus_message_append(self.ct_msg, c.codes[0], value)
			
		else:
			raise Exception("unhandled type", type(item), item, item.signature)
		
		i += 1

class MessageProxy():
	def __init__(self, msg):
		self.ct_msg = msg
		
		self.value_cache = []
		
		if self.ct_msg:
			if sd_bus_message_is_method_error(self.ct_msg, None):
				self.error_msg = sd_bus_message_get_error(self.ct_msg).contents
				self.errno = sd_bus_message_get_errno(self.ct_msg)
				
				if verbosity > 0:
					print("received error message", self.error_msg.name, self.error_msg.message, self.errno)
			else:
				self.errno = 0
				self.error_msg = None
				if verbosity > 0:
					print("new msg: \"{self.sender}\" -> \"{self.destination}\" {self.path} {self.interface} {self.member}({self.signature})".format(self=self))
	
	def get_values(self, raw_result=False):
		s = sd_bus_message_get_signature(self.ct_msg, 1);
		
		if sys.version_info >= (3,):
			s = s.decode()
		
		result = parse_signature(self.ct_msg, s, 0)
		
		if result and len(result) == 1 and not raw_result:
			return result[0]
		else:
			return result
	
	def set_values(self, signature, *values):
		if len(values) == 0 and (not signature or signature == ""):
			return
		
		skeleton = parse_signature(None, signature, 0)
		
		local_verbose = verbosity > 1
		if local_verbose:
			print("setting values", "\"%s\"" % signature, values)
		
		i = 0
		for item in skeleton:
			#print(values, s, type(item), item.signature, item.body_signature if hasattr(item, "body_signature") else None)
			
			value = values[i]
			
			if isinstance(item, BaseArray):
				if local_verbose:
					if isinstance(item, list):
						print("\tadd array", item.body_signature)
					elif isinstance(item, dict):
						print("\tadd dict", item.body_signature)
				
				sd_bus_message_open_container(self.ct_msg, "a", item.body_signature)
				
				if isinstance(item, list):
					for val in value:
						self.set_values(item.body_signature, val)
				elif isinstance(item, dict):
					for key in value:
						self.set_values(item.body_signature, (key, value[key]))
				else:
					raise Exception("unexpected array type", type(item), item, item.signature)
				
				sd_bus_message_close_container(self.ct_msg)
			
			elif isinstance(item, DictItem):
				if local_verbose:
					print("\tadd dict item \"%s\": { %s, %s }" % (item.body_signature, str(value[0]), str(value[1])))
				
				sd_bus_message_open_container(self.ct_msg, "e", item.body_signature)
				
				self.set_values(item[0].signature, value[0])
				self.set_values(item[1].signature, value[1])
				
				sd_bus_message_close_container(self.ct_msg)
			
			elif isinstance(item, Variant):
				if isinstance(value, DBusValue):
					signature = value.signature
				elif len(values[i:]) == 1:
					signature = guess_signature(value)
				elif isinstance(value, tuple):
					signature = guess_signature(value)
				elif isinstance(value, str):
					signature = value
					i+=1
					value = values[i]
				else:
					raise Exception("cannot determine signature of variant", value, type(value))
				
				if local_verbose:
					print("\tadd variant", signature, "value:", value)
				
				sd_bus_message_open_container(self.ct_msg, "v", signature)
				
				self.set_values(signature, value)
				
				sd_bus_message_close_container(self.ct_msg)
			
			elif isinstance(item, Struct):
				if local_verbose:
					print("\tadd struct", item.body_signature)
				sd_bus_message_open_container(self.ct_msg, "r", item.body_signature)
				
				j = 0
				for val in value:
					self.set_values(item.body_signature[j], val)
					j+=1
				
				sd_bus_message_close_container(self.ct_msg)
			
			elif isinstance(item, BasicType):
				c = item.__class__
				if isinstance(item, NumberClass) or isinstance(item, Boolean):
					value = c.c_type(value)
					
					self.value_cache.append( value )
				
				if local_verbose:
					print("\tadd basic type", c, c.codes[0], value)
				
				sd_bus_message_append(self.ct_msg, c.codes[0], value)
				
			else:
				raise Exception("unhandled type", type(item), item, item.signature)
			
			i += 1
	
	def __getattr__(self, item):
		if item in ["sender", "destination", "signature", "path", "interface", "member",
					"type", "cookie", "reply_cookie", "priority",
			]:
			fct = getattr(sys.modules[__name__], "sd_bus_message_get_"+item, None)
			if fct:
				if item == "signature":
					return sd_bus_message_get_signature(self.ct_msg, 1)
				else:
					result = fct(self.ct_msg)
					if result is None:
						return ""
					else:
						return result
		
		if item == "values":
			self.values = self.get_values(raw_result=True)
			return self.values
		
		return object.__getattribute__(self, item)
	
	def dump(self, with_values=True):
		print("\"{self.sender}\" -> \"{self.destination}\" {self.path} {self.interface} {self.member}({self.signature}):".format(self=self), self.get_values() if with_values else "")
		
		sd_bus_message_rewind(self.ct_msg, 1)

class IntrospectionProxy():
	def __init__(self, *args):
		self.dbus_object = None
		self.introspect_iface = None
		self.xml = None
		self.root = None
		self.interfaces = None
		
		if len(args) > 0:
			if isinstance(args[0], ObjectProxy):
				self.dbus_object = args[0]
			elif isinstance(args[0], str):
				self.xml = args[0]
			else:
				raise Exception("unexpected arg", args)
	
	def getXML(self, no_cache=False):
		if self.xml is None or no_cache:
			if self.dbus_object is None:
				raise Exception("no DBus object and no XML string")
			
			if self.introspect_iface is None:
				self.introspect_iface = self.dbus_object.getInterface(dbus_introspectable_interface)
			
			self.xml = self.introspect_iface.Introspect()
		
		return self.xml
	
	def parse(self, no_cache=False):
		if self.root is None or no_cache:
			import xml.etree.ElementTree as et
			
			if self.xml is None:
				self.getXML(no_cache=no_cache)
			
			self.root = et.fromstring(self.xml)
	
	def getXMLRoot(self, no_cache=False):
		self.parse(no_cache=no_cache)
		
		return self.root
	
	def getInterfaces(self, no_cache=False):
		if self.root is None:
			self.parse(no_cache=no_cache)
		
		if self.interfaces is None or no_cache:
			self.interfaces = {}
			
			for interface in self.root.findall("interface"):
				self.interfaces[interface.attrib["name"]] = {}
				iface_dict = self.interfaces[interface.attrib["name"]]
				for method in interface.findall("method"):
					iface_dict[method.attrib["name"]] = { "type": "method", "in": "", "out": "" }
					method_dict = iface_dict[method.attrib["name"]]
					for arg in method.findall("arg"):
						method_dict[arg.attrib["direction"]] += arg.attrib["type"]
				
				for signal in interface.findall("signal"):
					iface_dict[signal.attrib["name"]] = { "type": "signal", "out": "" }
					signal_dict = iface_dict[signal.attrib["name"]]
					for arg in signal.findall("arg"):
						signal_dict["out"] = arg.attrib["type"]
				
				for prop in interface.findall("property"):
					iface_dict[prop.attrib["name"]] = { "type": "property",
										"signature": prop.attrib["type"],
										"access": prop.attrib["access"],
										}
		
		return self.interfaces
	
	def getSignatures(self, interface, member, no_cache=False):
		if self.interfaces is None or no_cache:
			self.get_interfaces(no_cache=no_cache)
		
		return (self.interfaces[interface][member]["in"], self.interfaces[interface][member]["out"])

class AsyncCall():
	def __init__(self, iface_proxy, method_name,
			  args, kwargs,
			  async_callback,
			  reply_callback,
			  error_callback,
		):
		
		self.iface_proxy = iface_proxy
		self.method_name = method_name
		self.object_proxy = iface_proxy.object_proxy
		self.async_callback = async_callback
		self.reply_callback = reply_callback
		self.error_callback = error_callback
		
		if "query_signature" in kwargs:
			(self.signature, _) = self.object_proxy.getSignatures(self.iface_proxy.iface_name, method_name)
		else:
			if len(args) == 0:
				self.signature = ""
			elif "signature" in kwargs:
				self.signature = kwargs["signature"]
			else:
				self.signature = guess_signature(*args)
		
		if verbosity > 0:
			print("async calling", self.object_proxy.service, self.object_proxy.path, self.iface_proxy.iface_name, self.method_name, self.signature, args)
		
		self.ct_callback = sd_bus_message_handler_t(self.callback_wrapper)
		
		self.ct_slot = ct.POINTER(sd_bus_slot)()
		self.ct_msg = ct.POINTER(sd_bus_message)()
		
		sd_bus_message_new_method_call(
			self.object_proxy.bus.bus,
			ct.byref(self.ct_msg),
			self.object_proxy.service,
			self.object_proxy.path,
			self.iface_proxy.iface_name,
			self.method_name
			)
		
		mp = MessageProxy(self.ct_msg)
		mp.set_values(self.signature, *args)
		
		sd_bus_call_async(
			self.object_proxy.bus.bus,
			ct.byref(self.ct_slot),
			self.ct_msg,
			self.ct_callback, None,
			-1
			)
	
	def callback_wrapper(self, ct_msg, userdata, ret_error):
		if self.async_callback:
			self.async_callback(ct_msg, userdata, ret_error)
		
		if self.reply_callback or self.error_callback:
			mp = MessageProxy(ct_msg)
			
			if mp.errno != 0 and self.error_callback:
				self.error_callback(mp.errno, mp.error_msg.name, mp.error_msg.message)
			elif self.reply_callback:
				values = mp.get_values(raw_result=True)
				if values is None:
					values = tuple()
				self.reply_callback(*values)
		
		self.iface_proxy.async_calls.remove(self)
		
		return 0

class MethodProxy():
	def __init__(self, iface_proxy, method_name):
		self.method_name = method_name
		self.iface_proxy = iface_proxy
		self.object_proxy = self.iface_proxy.object_proxy
	
	def init_call(self):
		msg = ct.POINTER(sd_bus_message)()
		
		sd_bus_message_new_method_call(
			self.object_proxy.bus.bus,
			ct.byref(msg),
			self.object_proxy.service,
			self.object_proxy.path,
			self.iface_proxy.iface_name,
			self.method_name
			)
		
		mp = MessageProxy(msg)
		
		return mp
	
	def send_call(self, mp):
		error = sd_bus_error()
		reply = ct.POINTER(sd_bus_message)()
		
		try:
			sd_bus_call(
				self.object_proxy.bus.bus,
				mp.ct_msg,
				-1,
				ct.byref(error),
				ct.byref(reply)
				)
		except OSError as e:
			# TODO check if there can be other cases with the same error code
			if e.errno == -53:
				raise MethodNotFound(self.object_proxy, self.iface_proxy, self.method_name)
			elif e.errno == -113:
				raise PeerNotFound(self.object_proxy)
			else:
				raise
		
		reply = MessageProxy(reply)
		
		if verbosity > 1:
			reply.dump()
		
		return reply.get_values()
	
	def call(self, *args, **kwargs):
		mp = self.init_call()
		
		if "query_signature" in kwargs:
			(sign, _) = self.object_proxy.getSignatures(self.iface_proxy.iface_name, self.method_name)
		else:
			if len(args) == 0:
				sign = ""
			elif "signature" in kwargs:
				sign = kwargs["signature"]
			else:
				sign = guess_signature(*args)
		
		if verbosity > 0:
			print("calling", self.object_proxy.service, self.object_proxy.path, self.iface_proxy.iface_name, self.method_name, sign, args)
		
		mp.set_values(sign, *args)
		
		return self.send_call(mp)
	
	def async_call(self, *args, **kwargs):
		ac = AsyncCall(self.iface_proxy, self.method_name, args, kwargs,
				 async_callback=kwargs.get("async_callback", None),
				 reply_callback=kwargs.get("reply_callback", None),
				 error_callback=kwargs.get("error_callback", None))
		
		# keep reference to avoid a release by the garbage collector
		self.iface_proxy.async_calls.append(ac)
		return ac
	
	def __call__(self, *args, **kwargs):
		if "async_callback" in kwargs or "reply_callback" in kwargs or "error_callback" in kwargs:
			return self.async_call(*args, **kwargs)
		else:
			return self.call(*args, **kwargs)

class InterfaceProxy(object):
	def __init__(self, object_proxy, iface_name):
		self.object_proxy = object_proxy
		self.iface_name = iface_name
		self.async_calls = []
	
	def __getattr__(self, item):
		if item in self.__dict__:
			return self.__dict__[item]
		
		if item not in ["__str__"]:
			return MethodProxy(self, item)
		else:
			return object.__getattr__(item)
	
	def add_match(self, member, callback, userdata=None, raw_callback=False, msg_proxy_callback=False):
		match_string = "type='signal'"
		match_string += ",interface='"+self.iface_name+"'"
		match_string += ",sender='"+self.object_proxy.service+"'"
		match_string += ",path='"+self.object_proxy.path+"'"
		if member != "*":
			match_string += ",member='"+member+"'"
		
		return self.object_proxy.bus.add_match(match_string, callback, userdata, raw_callback=raw_callback, msg_proxy_callback=msg_proxy_callback)
	
	def on_property_changed_cb(self, mp, udata):
		values = mp.get_values()
		if not isinstance(values, tuple):
			raise Exception("unexpected data received", values)
		if values[0] != self.iface_name:
			# this is not an error
			return
		
		if udata.element in values[1]:
			udata.callback(values[1][udata.element])
		elif udata.element in values[2]:
			udata.callback(None)
		else:
			# this is not an error
			return
	
	def addPropertyChangedCallback(self, element, callback):
		if not self.object_proxy.props_iface:
			self.object_proxy.props_iface = self.object_proxy.getInterface(dbus_properties_interface)
		
		udata = lambda: None
		udata.element = element
		udata.callback = callback
		
		return self.object_proxy.props_iface.add_match("PropertiesChanged", self.on_property_changed_cb, udata, msg_proxy_callback=True)
	
	def getSignatures(self, member=None):
		interfaces = self.object_proxy.introspection_proxy.getInterfaces()
		
		if member:
			return interfaces[self.iface_name][member]
		else:
			return interfaces[self.iface_name]
	
	def getProperty(self, prop):
		dbus_prop_iface = self.object_proxy.getInterface(dbus_properties_interface)
		
		try:
			rv = dbus_prop_iface.Get(self.iface_name, prop)
		except OSError as e:
			# TODO check if there can be other cases with the same error code
			if e.errno == -22:
				raise PropertyNotFound(self.object_proxy, self, prop)
			else:
				raise
		
		return rv
	
	def setProperty(self, prop, *values, **kwargs):
		#error = sd_bus_error()
		
		if "signature" not in kwargs:
			signature = guess_signature(*values)
		else:
			signature = kwargs["signature"]
		
		if verbosity > 1:
			print("setProp", self.iface_name, prop, signature, values)
		
		dbus_prop_iface = self.object_proxy.getInterface(dbus_properties_interface)
		set_method_proxy = dbus_prop_iface.Set
		
		mp = set_method_proxy.init_call()
		
		mp.set_values("ssv", self.iface_name, prop, signature, *values)
		
		return set_method_proxy.send_call(mp)
	
	def is_signal(self, element):
		signatures = self.getSignatures()
		
		if element in signatures:
			entry = signatures[element]
			
			return entry["type"] == "signal"
		else:
			raise ElementNotFound(self.object_proxy, self.iface_name, element)
	
	def is_method(self, element):
		signatures = self.getSignatures()
		
		if element in signatures:
			entry = signatures[element]
			
			return entry["type"] == "method"
		else:
			raise ElementNotFound(self.object_proxy, self.iface_name, element)
	
	def is_property(self, element):
		signatures = self.getSignatures()
		
		if element in signatures:
			entry = signatures[element]
			
			return entry["type"] not in ["method", "signal"]
		else:
			raise ElementNotFound(self.object_proxy, self.iface_name, element)

class ObjectProxy():
	def __init__(self, bus, service, path):
		self.bus = bus
		self.service = service
		self.path = path
		
		self.props_iface = None
		self._introspection_proxy = None
	
	def getInterface(self, interface):
		return InterfaceProxy(self, interface)
	
	@property
	def introspection_proxy(self):
		if self._introspection_proxy is None:
			self._introspection_proxy = IntrospectionProxy(self)
		
		return self._introspection_proxy
	
	def getSignatures(self, interface=None, member=None):
		interfaces = self.introspection_proxy.getInterfaces()
		
		if interface and member:
			return (interfaces[interface][member]["in"],
				interfaces[interface][member]["out"])
		else:
			return interfaces
	
	def getChildObjectPaths(self):
		root = self.introspection_proxy.getXMLRoot()
		
		for node in root.findall("node"):
			yield node.attrib["name"]
	
	def getProperty(self, interface, prop_name=None):
		if not prop_name:
			# expect the property name at the end of the interface string
			
			idx = interface.rfind(".")
			
			prop_name = interface[idx+1:]
			interface = interface[:idx]
		
		if not self.props_iface:
			self.props_iface = self.getInterface(dbus_properties_interface)
		
		return self.props_iface.Get(interface, prop_name)
	
	def setProperty(self, interface, prop_name, *args, **kwargs):
		if not self.props_iface:
			self.props_iface = self.getInterface(dbus_properties_interface)
		
		self.props_iface.Set(interface, prop_name, *args, **kwargs)
	
	def addPropertiesChangedCallback(self, *args, **kwargs):
		if not self.props_iface:
			self.props_iface = self.getInterface(dbus_properties_interface)
		
		return self.props_iface.add_match("PropertiesChanged", *args, **kwargs)

class Match():
	# if raw_callback==True, expects a callback with the low-level sd-bus signature
	# if raw_callback==False, expects a callback with function parameters matching the values in the sd-bus message
	# if msg_proxy_callback==True, expects a callback that receives a MessageProxy object a single argument
	def __init__(self, bus, match_string, callback, userdata, msg_proxy_callback=False, raw_callback=False):
		self.bus = bus
		self.match_string = match_string
		
		self.callback = callback
		self.userdata = userdata
		
		if raw_callback:
			self.ct_callback = sd_bus_message_handler_t(self.callback)
		elif msg_proxy_callback:
			self.ct_callback = sd_bus_message_handler_t(self.mp_callback_wrapper)
		else:
			self.ct_callback = sd_bus_message_handler_t(self.values_callback_wrapper)
		self.ct_userdata = ct.py_object(userdata)
		
		self.ct_slot = ct.POINTER(sd_bus_slot)()
	
	def values_callback_wrapper(self, ct_msg, userdata, ret_error):
		mp = MessageProxy(ct_msg)
		
		values = mp.get_values(raw_result=True)
		
		if values is None:
			values = ()
		
		rv = self.callback(*values)
		if rv is None:
			rv = 1
		return rv
	
	def mp_callback_wrapper(self, ct_msg, userdata, ret_error):
		mp = MessageProxy(ct_msg)
		
		if userdata is not None:
			rv = self.callback(mp, userdata)
		else:
			rv = self.callback(mp)
		if rv is None:
			rv = 1
		return rv
	
	def remove(self):
		self.bus.del_match(self)

class Bus():
	def __init__(self, *args, **kwargs):
		self.bus = ct.POINTER(sd_bus)()
		
		#if "nonblocking" in kwargs and kwargs["nonblocking"]:
			#self.nonblocking = True
		#else:
			#self.nonblocking = False
		
		self.matches = []
		self.fd = -1
		self.evloop_data = None
		self.no_implicit_root_object = kwargs.get("no_implicit_root_object", False)
		self.root_object = None
	
	def setup(self):
		if not self.no_implicit_root_object:
			self.root_object = Object("/", bus=self, add_object_manager=True)
	
	def become_monitor(self, rules=None, flags=None):
		### this function just sets a flag that will cause some sdbus functions
		### to become a no-op
		#sd_bus_set_monitor(self.bus, mode)
		
		obj = self.getObject("org.freedesktop.DBus", "/org/freedesktop/DBus")
		
		iface = obj.getInterface("org.freedesktop.DBus.Monitoring")
		
		if rules is None:
			rules = []
		if flags is None:
			flags = UInt32(0)
		if not isinstance(flags, UInt32):
			flags = UInt32(flags)
		
		iface.BecomeMonitor(rules, flags, signature="asu")
	
	def add_filter(self, callback, userdata=None, msg_proxy_callback=False, raw_callback=False):
		m = Match(self, None, callback, userdata, msg_proxy_callback, raw_callback)
		self.matches.append(m)
		
		if verbosity > 1:
			print("new filter")
		
		sd_bus_add_filter(self.bus, ct.byref(m.ct_slot), m.ct_callback, m.ct_userdata)
		
		return m
	
	def add_match(self, match_string, callback, userdata=None, msg_proxy_callback=False, raw_callback=False):
		m = Match(self, match_string, callback, userdata, msg_proxy_callback, raw_callback)
		self.matches.append(m)
		
		if verbosity > 1:
			print("new match: ", m.match_string)
		
		sd_bus_add_match(self.bus, ct.byref(m.ct_slot), m.match_string, m.ct_callback, m.ct_userdata)
		
		return m
	
	def del_match(self, match_obj):
		self.matches.remove(match_obj)
		
		sd_bus_slot_unref(match_obj.ct_slot)
	
	def processEvents(self, msg=None):
		return sd_bus_process(self.bus, msg)
	
	def getObject(self, service, path):
		return ObjectProxy(self, service, path)
	
	def addTrigger(self, peer, appeared_cb=None, disappeared_cb=None):
		t = Trigger(self, peer, appeared_cb, disappeared_cb)
		
		return t

class UserBus(Bus):
	def __init__(self, shared=True):
		Bus.__init__(self)
		
		self.shared = shared
		if self.shared:
			sd_bus_default_user(ct.byref(self.bus))
		else:
			sd_bus_open_user(ct.byref(self.bus))
		
		self.setup()

class SystemBus(Bus):
	def __init__(self, shared=True):
		Bus.__init__(self)
		
		self.shared = shared
		if self.shared:
			sd_bus_default_system(ct.byref(self.bus))
		else:
			sd_bus_open_system(ct.byref(self.bus))
		
		#bus_addr = "unix:path=/run/dbus/system_bus_socket"
		#if "DBUS_SYSTEM_BUS_ADDRESS" in os.environ:
			#bus_addr = os.environ["DBUS_SYSTEM_BUS_ADDRESS"]
		
		#sd_bus_new(ct.byref(self.bus))
		#sd_bus_set_monitor(self.bus, 1)
		#sd_bus_negotiate_creds(self.bus, 1, SD_BUS_CREDS_ALL)
		#sd_bus_negotiate_timestamp(self.bus, 1)
		#sd_bus_negotiate_fds(self.bus, 1)
		#sd_bus_set_address(self.bus, bus_addr)
		#sd_bus_set_bus_client(self.bus, 1)
		#sd_bus_start(self.bus)
		
		self.setup()

class RemoteSystemBus(Bus):
	def __init__(self, remote_login):
		Bus.__init__(self)
		
		sd_bus_open_system_remote(ct.byref(self.bus), remote_login)
		
		self.setup()

class EventLoop():
	def __init__(self, *buses):
		self.buses = []
		self.fd2bus = {}
		
		for bus in buses:
			self.addBus(bus)
	
	def addBus(self, bus):
		self.buses.append(bus)
		
		bus.fd = sd_bus_get_fd(bus.bus)
		
		self.fd2bus[bus.fd] = bus
	
	def poll2epoll(self, poll_events):
		from select import EPOLLIN, EPOLLOUT, EPOLLPRI, POLLIN, POLLOUT, POLLPRI
		
		epoll_events = 0
		if poll_events & POLLIN:
			epoll_events |= EPOLLIN
		if poll_events & POLLOUT:
			epoll_events |= EPOLLOUT
		if poll_events & POLLPRI:
			epoll_events |= EPOLLPRI
		
		return epoll_events
	
	def loop_single_bus(self, timeout_us=-1):
		while not self._stop:
			self.buses[0].processEvents()
			
			# timeout in microseconds
			sd_bus_wait(self.buses[0].bus, ct.c_uint64(timeout_us))
	
	def loop_multiple_buses(self, timeout_us=-1):
		from select import epoll, EPOLLIN, EPOLLOUT, EPOLLERR
		from sys import maxsize as sys_maxsize
		
		self.epoll = epoll()
		
		while not self._stop:
			epoll_timeout_us = timeout_us
			
			# determine epoll event flags and the next timeout for each bus
			for bus in self.buses:
				# call processEvents() at least once before calling sd_bus_get_events()
				if bus.evloop_data is None:
					bus.processEvents()
					
				events = sd_bus_get_events(bus.bus)
				
				if bus.evloop_data is None:
					self.epoll.register(bus.fd, self.poll2epoll(events))
				elif self.poll2epoll(events) != bus.evloop_data:
					self.epoll.modify(bus.fd, self.poll2epoll(events))
				
				bus.evloop_data = self.poll2epoll(events)
				
				sdbus_timeout_us = ct.c_uint64(0)
				err = sd_bus_get_timeout(bus.bus, ct.byref(sdbus_timeout_us))
				if err < 0:
					print("sd_bus_get_timeout() failed with", err, file=sys.stderr)
				
				sdbus_timeout_us = sdbus_timeout_us.value
				
				if epoll_timeout_us == -1:
					epoll_timeout_us = sdbus_timeout_us
				elif sdbus_timeout_us < epoll_timeout_us:
					epoll_timeout_us = sdbus_timeout_us
			
			# epoll expects the timeout in seconds as float
			if epoll_timeout_us > -1:
				epoll_timeout_us = epoll_timeout_us / 1000000.0
				if epoll_timeout_us > sys_maxsize:
					epoll_timeout_us = -1;
			
			events = self.epoll.poll(epoll_timeout_us)
			
			for fd, event in events:
				if fd not in self.fd2bus:
					continue
				
				bus = self.fd2bus[fd]
				bus.processEvents()
	
	def loop(self, timeout_us=-1):
		self._stop = False
		
		if len(self.buses) <= 1:
			self.loop_single_bus(timeout_us)
		else:
			self.loop_multiple_buses(timeout_us)
	
	def stop(self):
		self._stop = True

class Object(object):
	def __init__(self, path, bus=None, add_object_manager=False):
		self.path = path
		self.bus = bus
		self.slot = ct.POINTER(sd_bus_slot)()
		
		if self.bus:
			self.add2Bus()
		
		if add_object_manager:
			sd_bus_add_object_manager(self.bus.bus, self.slot, self.path)
	
	def publish(self):
		sd_bus_emit_object_added(self.bus.bus, self.path)
	
	def refresh(self, iface=None, prop=None):
		for iface in self.dbus_properties:
			if prop in self.dbus_properties[iface]:
				#print(self.bus.bus, self.path, iface, prop)
				sd_bus_emit_properties_changed(self.bus.bus, self.path, iface, prop, None)
	
	@staticmethod
	def method(interface, args_signature=None, return_signature=None):
		def outer_wrapper_method(func):
			@ft_wraps(func)
			def wrapper_method(*args, **kwargs):
				return func(*args, **kwargs)
			
			wrapper_method.is_public_method = True
			wrapper_method.interface = interface
			wrapper_method.args_signature = args_signature
			wrapper_method.return_signature = return_signature
			wrapper_method.func = func
			
			return wrapper_method
		
		return outer_wrapper_method
	
	def add2Bus(self):
		from inspect import ismethod
		
		self.vtables = {}
		self.callbacks = {}
		
		if not hasattr(self, "dbus_properties"):
			if hasattr(self.__class__, "dbus_properties"):
				self.dbus_properties = self.__class__.dbus_properties.copy()
			else:
				self.dbus_properties = {}
		
		for prop_name in dir(self):
			prop = getattr(self, prop_name, None)
			
			if prop and ismethod(prop) and getattr(prop, "is_public_method", False):
				if prop.interface not in self.dbus_properties:
					self.dbus_properties[prop.interface] = {}
				self.dbus_properties[prop.interface][prop_name] = prop
		
		def get_prop_cb(bus, path, interface, prop_name, reply_msg, userdata, ret_error):
			prop_dict = self.dbus_properties[interface][prop_name]
			if not hasattr(self, prop_name) and "default" in prop_dict:
				retval = prop_dict["default"]
			else:
				retval = getattr(self, prop_name)
			
			mp = MessageProxy(reply_msg)
			
			mp.set_values(prop_dict["signature"], retval)
			
			return 1
		
		def set_prop_cb(bus, path, interface, prop_name, value_msg, userdata, ret_error):
			# the message we receive has already been queried until the
			# actual value, hence we cannot use MessageProxy for parsing
			
			typ = ct.c_char()
			content_sign = ct.c_char_p()
			
			sd_bus_message_peek_type(value_msg, ct.byref(typ), ct.byref(content_sign))
			
			if sys.version_info >= (3,):
				typ = typ.value.decode()
			else:
				typ = typ.value
			
			values = parse_signature(value_msg, typ, 0, one_item=True)
			
			prop_dict = self.dbus_properties[interface][prop_name]
			
			if "write_cb" in prop_dict:
				getattr(self, prop_dict["write_cb"])(interface, prop_name, values[0])
			else:
				setattr(self, prop_name, values[0])
			
			return 1
		
		get_prop_cb_ct = sd_bus_property_get_t(get_prop_cb)
		set_prop_cb_ct = sd_bus_property_set_t(set_prop_cb)
		
		for interface, iface_dict in self.dbus_properties.items():
			vtable_type = (len(iface_dict) + 2) * sd_bus_vtable
			self.vtables[interface] = vtable_type()
			
			if verbosity > 1:
				print("exporting:", self.path, interface)
			
			if interface not in self.callbacks:
				self.callbacks[interface] = {}
			
			sd_bus_vtable_fill_start(self.vtables[interface][0], 0)
			i=1
			for name, item in iface_dict.items():
				if ismethod(item) or ismethod(getattr(self, name, None)):
					fname = name
					if ismethod(item):
						func = item
						args_sign = func.args_signature
						return_sign = func.return_signature
					else:
						func = getattr(self, name)
						args_sign = item["args_signature"]
						return_sign = item["return_signature"]
						
					
					def cb(msg, userdata, error):
						values = MessageProxy(msg).get_values()
						
						retval = func(*values)
						
						return sd_bus_reply_method_return(msg, return_sign, retval);
					
					self.callbacks[interface][fname] = sd_bus_message_handler_t(cb)
					
					if verbosity > 1:
						print("\t", fname, args_sign, return_sign)
					
					sd_bus_vtable_fill_method(self.vtables[interface][i], to_bytes(fname), to_bytes(args_sign),
									to_bytes(return_sign), self.callbacks[interface][fname], 0, SD_BUS_VTABLE_UNPRIVILEGED)
					i += 1
				else:
					prop_name = name
					prop_dict = item
					
					self.callbacks[interface][prop_name] = {}
					self.callbacks[interface][prop_name]["get"] = get_prop_cb_ct
					self.callbacks[interface][prop_name]["set"] = set_prop_cb_ct
					
					if verbosity > 1:
						print("\t", prop_name, prop_dict["signature"], prop_dict["writable"])
					
					sd_bus_vtable_fill_property(self.vtables[interface][i], to_bytes(prop_name),
									to_bytes(prop_dict["signature"]),
									self.callbacks[interface][prop_name]["get"],
									self.callbacks[interface][prop_name]["set"],
									0, # offset
									SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE, # flags
									writable=prop_dict["writable"])
					i += 1
			sd_bus_vtable_fill_end(self.vtables[interface][i])
			
			sd_bus_add_object_vtable(self.bus.bus,
										ct.byref(self.slot),
										self.path,
										interface,
										self.vtables[interface],
										None)
	
	def add_property(self, interface, name, signature, writable=False, **kwargs):
		if not hasattr(self, "dbus_properties"):
			if hasattr(self.__class__, "dbus_properties"):
				self.dbus_properties = self.__class__.dbus_properties.copy()
			else:
				self.dbus_properties = {}
		
		if interface not in self.dbus_properties:
			self.dbus_properties[interface] = {}
		
		self.dbus_properties[interface][name] = {
				"signature": signature, "writable": writable
			}
		
		if "default" in kwargs:
			self.dbus_properties[interface][name]["default"] = kwargs["default"]
	
	#def __setattr__(self, attr, obj):
		#object.__setattr__(self, attr, obj)
		#print("set", attr, obj)
		
		#if hasattr(self, "dbus_properties"):
			#for iface in self.dbus_properties:
				#if attr in self.dbus_properties[iface]:
					#print(self.bus.bus, self.path, iface, attr, obj, None)
					#sd_bus_emit_properties_changed(self.bus.bus, self.path, iface, attr, None)

class Trigger():
	trigger_template="type='signal',sender='org.freedesktop.DBus',path='/org/freedesktop/DBus'," \
		"interface='org.freedesktop.DBus',member='NameOwnerChanged',arg0='%s'"
	
	def __init__(self, bus, peer, appeared_cb=None, disappeared_cb=None):
		self.bus = bus
		self.peer = peer
		self.appeared = appeared_cb
		self.disappeared = disappeared_cb
		
		self.match = self.bus.add_match(self.__class__.trigger_template % peer, self.callback, msg_proxy_callback=True)
	
	def __del__(self):
		self.bus.del_match(self)
	
	def callback(self, mp):
		peer, old, new = mp.get_values(raw_result=True)
		
		if peer != self.peer:
			print("error, unexpected peer", peer, "!=", self.peer)
			return
		
		if not old and new:
			self.appeared(peer, new)
		elif old and not new:
			self.disappeared(peer, old)

if __name__ == '__main__':
	import os
	
	if "VERBOSITY" in os.environ:
		verbosity = int(os.environ["VERBOSITY"])
	
	for t in ["as", "ass", "assas", "aay", "a{oa{sv}}", "aa{sv}", "a{sv}as", "sa{sv}as", "a(ii)"]:
		objs = parse_signature(None, t, 0)
		s = ""
		for o in objs:
			s += o.signature
		if s != t:
			raise Exception("signature check", s, "!=", t)
	
	try:
		bus = UserBus()
	except Exception as e:
		if e.errno == -2:
			bus = SystemBus()
		else:
			raise
	
	dbus_obj = ObjectProxy(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus")
	
	iface = dbus_obj.getInterface("org.freedesktop.DBus")
	
	reply = iface.ListNames()
	
	print(reply)
	
	
	
	def reply_cb(list_of_names):
		print("async reply:", list_of_names)
	
	iface.ListNames(reply_callback=reply_cb)
	
	
	
	
	def reply_cb(list_of_names):
		raise Exception("should not be called")
	
	def error_cb(errno, error_type, error_description):
		if errno == 53:
			pass
		else:
			print("unexpected async error %s: %s (%d)" % (error_type, error_description, errno))
	
	iface.MethodThatDoesNotExist(reply_callback=reply_cb, error_callback=error_cb)
	
	
	
	
	def prop_changed_cb_raw(msg, userdata, ret_error):
		print(userdata, end="");
		MessageProxy(msg).dump()
		return 0
	
	bus.add_match("type='signal'", prop_changed_cb_raw, "Raw signal: ", raw_callback=True)
	
	def prop_changed_cb(*args):
		print("signal:", args)
		return 0
	
	bus.add_match("type='signal'", prop_changed_cb)
	
	class test(Object):
		dbus_properties={
			"foo.bar": {
				"prop_ro": { "signature": "s", "writable": False, "default": "prop_ro_value" },
				"prop_string": { "signature": "s", "writable": True, "default": "str1", "write_cb": "write_string" },
				"prop_array": { "signature": "as", "writable": False, "default": ["val1", "val2"] },
				"prop_dict": { "signature": "a{sv}", "writable": False, "default": {"key1": "val1", "key2": {"key2a": "val2a"} } },
				"prop_struct": { "signature": "a(id)", "writable": False, "default": [ (1, 2.3), (3, 4.5) ], },
				"prop_aqay": { "signature": "a{qay}", "writable": False, "default": { 123: [1, 2, 3] }, },
				"prop_aqv": { "signature": "a{qv}", "writable": False, "default": { 123: Array([1, 2, 3], signature="ay") }, },
				"beef": { "args_signature": "ss", "return_signature": "i" },
				},
			}
		
		def write_string(self, interface, prop, value):
			print("setting", interface, prop, value)
			setattr(self, prop, value)
		
		def __init__(self, path, bus=None):
			self.add_property("foo.bar2", "prop_rw", "s", writable=True, default="prop_rw_value")
			
			Object.__init__(self, path, bus)
			
			print(self.__class__.dbus_properties)
		
		@Object.method("foo.bar", args_signature="ss", return_signature="i")
		def beef(self, s1, s2):
			print("arguments:", s1, s2)
			return 1234
	
	t = test("/foo/bar", bus)
	
	msg = ct.POINTER(sd_bus_message)()
	sd_bus_message_new_method_call(bus.bus, msg, "foo.bar", "/foo/bar", "foo.bar", "foobar");
	
	mp = MessageProxy(msg)
	mp.set_values("as", ["foo", "bar"])
	
	mp = MessageProxy(msg)
	mp.set_values("a{sv}", { "foo": "bar", "toast": True })
	
	mp = MessageProxy(msg)
	mp.set_values("a{qv}", { 123: Array([1, 2, 3], signature="ay") })
	
	a = Array(["a", "b"], signature="s")
	print("array:", a)
	
	s = String("test")
	print("string:", s)
	
	d = Dictionary({ "foo": True })
	print("dict:", d)
	
	eloop = EventLoop(bus)
	try:
		eloop.loop()
	except KeyboardInterrupt:
		eloop.stop()
	
	print(t)
