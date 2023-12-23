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
import os, sys
import ctypes as ct

from .header import *

class sd_bus(ct.Structure):
	pass

class sd_bus_error(ct.Structure):
	_fields_ = [
		('name', ct.c_char_p),
		('message', ct.c_char_p),
		('need_free', ct.c_int)
		]

class sd_bus_message(ct.Structure):
	pass

class sd_bus_slot(ct.Structure):
	pass

class sd_bus_track(ct.Structure):
	pass

sd_bus_message_handler_t = ct.CFUNCTYPE(ct.c_int, ct.POINTER(sd_bus_message), ct.py_object, ct.POINTER(sd_bus_error))
sd_bus_property_get_t = ct.CFUNCTYPE(ct.c_int, ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.POINTER(sd_bus_message), ct.c_void_p, ct.POINTER(sd_bus_error));
sd_bus_property_set_t = ct.CFUNCTYPE(ct.c_int, ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.POINTER(sd_bus_message), ct.c_void_p, ct.POINTER(sd_bus_error));
sd_bus_object_find_t = ct.CFUNCTYPE(ct.c_int, ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p, ct.py_object, ct.POINTER(ct.c_void_p), ct.POINTER(sd_bus_error));
sd_bus_node_enumerator_t = ct.CFUNCTYPE(ct.c_int, ct.POINTER(sd_bus), ct.c_char_p, ct.py_object, ct.POINTER(ct.POINTER(ct.c_char_p)), ct.POINTER(sd_bus_error));
sd_bus_track_handler_t = ct.CFUNCTYPE(ct.c_int, ct.POINTER(sd_bus_track), ct.py_object);

class sd_bus_vtable_start(ct.Structure):
	_fields_ = [
		('element_size', ct.c_size_t),
		]

class sd_bus_vtable_method(ct.Structure):
	_fields_ = [
		('member', ct.c_char_p),
		('signature', ct.c_char_p),
		('result', ct.c_char_p),
		('handler', sd_bus_message_handler_t),
		('offset', ct.c_size_t),
		]

class sd_bus_vtable_signal(ct.Structure):
	_fields_ = [
		('member', ct.c_char_p),
		('signature', ct.c_char_p),
		]

class sd_bus_vtable_property(ct.Structure):
	_fields_ = [
		('member', ct.c_char_p),
		('signature', ct.c_char_p),
		('get', sd_bus_property_get_t),
		('set', sd_bus_property_set_t),
		('offset', ct.c_size_t),
		]

class sd_bus_vtable_x(ct.Union):
	_fields_ = [
		('start', sd_bus_vtable_start),
		('method', sd_bus_vtable_method),
		('signal', sd_bus_vtable_signal),
		('property', sd_bus_vtable_property),
		]

from platform import architecture
if architecture()[0] == "32bit":
	# for some reason, on armhf the size of sd_bus_vtable structure is 32 bytes
	# while ctypes thinks it are 20 + 8 = 28 bytes.
	# On AMD64, both agree on 40 + 8 bytes
	class sd_bus_vtable(ct.Structure):
		_fields_ = [
			('type', ct.c_uint8, 8),
			('flags', ct.c_uint64, 56),
			('x', sd_bus_vtable_x),
			('padding', ct.c_uint8, 4),
			]
else:
	class sd_bus_vtable(ct.Structure):
		_fields_ = [
			('type', ct.c_uint8, 8),
			('flags', ct.c_uint64, 56),
			('x', sd_bus_vtable_x),
			]

_SD_BUS_VTABLE_START             = ord('<')
_SD_BUS_VTABLE_END               = ord('>')
_SD_BUS_VTABLE_METHOD            = ord('M')
_SD_BUS_VTABLE_SIGNAL            = ord('S')
_SD_BUS_VTABLE_PROPERTY          = ord('P')
_SD_BUS_VTABLE_WRITABLE_PROPERTY = ord('W')

def sd_bus_vtable_fill_start(vtable_entry, flags):
	vtable_entry.type = _SD_BUS_VTABLE_START
	vtable_entry.flags = flags
	vtable_entry.x.start.element_size = ct.sizeof(sd_bus_vtable)

SD_BUS_VTABLE_DEPRECATED                   = 1 << 0
SD_BUS_VTABLE_HIDDEN                       = 1 << 1
SD_BUS_VTABLE_UNPRIVILEGED                 = 1 << 2
SD_BUS_VTABLE_METHOD_NO_REPLY              = 1 << 3
SD_BUS_VTABLE_PROPERTY_CONST               = 1 << 4
SD_BUS_VTABLE_PROPERTY_EMITS_CHANGE        = 1 << 5
SD_BUS_VTABLE_PROPERTY_EMITS_INVALIDATION  = 1 << 6
SD_BUS_VTABLE_PROPERTY_EXPLICIT            = 1 << 7
_SD_BUS_VTABLE_CAPABILITY_MASK = 0xFFFF << 40

SD_BUS_CREDS_ALL               = (1 << 34) -1

def sd_bus_vtable_fill_method(vtable_entry, member, signature, result, handler, offset, flags):
	vtable_entry.type = _SD_BUS_VTABLE_METHOD
	vtable_entry.flags = flags
	vtable_entry.x.method.member = member
	vtable_entry.x.method.signature = signature
	vtable_entry.x.method.result = result
	vtable_entry.x.method.handler = handler
	vtable_entry.x.method.offset = offset

def sd_bus_vtable_fill_property(vtable_entry, member, signature, get_cb, set_cb, offset, flags, writable=False):
	if writable:
		vtable_entry.type = _SD_BUS_VTABLE_WRITABLE_PROPERTY
		vtable_entry.x.property.set = set_cb
	else:
		vtable_entry.type = _SD_BUS_VTABLE_PROPERTY
		vtable_entry.x.property.set = ct.cast(None, sd_bus_property_set_t)
	
	vtable_entry.flags = flags
	vtable_entry.x.property.member = member
	vtable_entry.x.property.signature = signature
	vtable_entry.x.property.get = get_cb
	vtable_entry.x.method.offset = offset

def sd_bus_vtable_fill_end(vtable_entry):
	vtable_entry.type = _SD_BUS_VTABLE_END
	vtable_entry.flags = 0

library_functions = [
	{ "name": "sd_bus_new", "args": [ct.POINTER(ct.POINTER(sd_bus))] },
	{ "name": "sd_bus_default", "args": [ct.POINTER(ct.POINTER(sd_bus))] },
	{ "name": "sd_bus_default_user", "args": [ct.POINTER(ct.POINTER(sd_bus))] },
	{ "name": "sd_bus_default_system", "args": [ct.POINTER(ct.POINTER(sd_bus))] },
	{ "name": "sd_bus_open", "args": [ct.POINTER(ct.POINTER(sd_bus))] },
	{ "name": "sd_bus_open_user", "args": [ct.POINTER(ct.POINTER(sd_bus))] },
	{ "name": "sd_bus_open_system", "args": [ct.POINTER(ct.POINTER(sd_bus))] },
	{ "name": "sd_bus_open_system_remote", "args": [ct.POINTER(ct.POINTER(sd_bus)), ct.c_char_p] },
	{ "name": "sd_bus_open_system_machine", "args": [ct.POINTER(ct.POINTER(sd_bus)), ct.c_char_p] },
	
	{ "name": "sd_bus_is_open", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_is_ready", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_can_send", "args": [ct.POINTER(sd_bus), ct.c_char] },
	
	{ "name": "sd_bus_negotiate_creds", "args": [ct.POINTER(sd_bus), ct.c_int, ct.c_uint64] },
	{ "name": "sd_bus_negotiate_timestamp", "args": [ct.POINTER(sd_bus), ct.c_int] },
	{ "name": "sd_bus_negotiate_fds", "args": [ct.POINTER(sd_bus), ct.c_int] },
	
	{ "name": "sd_bus_set_address", "args": [ct.POINTER(sd_bus), ct.c_char_p] },
	{ "name": "sd_bus_get_address", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.c_char_p)] },
	{ "name": "sd_bus_set_bus_client", "args": [ct.POINTER(sd_bus), ct.c_int] },
	{ "name": "sd_bus_is_bus_client", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_set_monitor", "args": [ct.POINTER(sd_bus), ct.c_int] },
	{ "name": "sd_bus_is_monitor", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_start", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_try_close", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_close", "args": [ct.POINTER(sd_bus)], "restype": None },
	
	{ "name": "sd_bus_call_method", "args": [
				ct.POINTER(sd_bus),
				ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p,
				ct.POINTER(sd_bus_error),
				ct.POINTER(ct.POINTER(sd_bus_message)),
				ct.c_char_p ], },
	{ "name": "sd_bus_call_method_async", "args": [
				ct.POINTER(sd_bus),
				ct.POINTER(ct.POINTER(sd_bus_slot)),
				ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p,
				sd_bus_message_handler_t, ct.py_object,
				ct.c_char_p ], },
	{ "name": "sd_bus_message_read", "args": [ct.POINTER(sd_bus_message), ct.c_char_p], },
	{ "name": "sd_bus_message_read_array", "args": [
						ct.POINTER(sd_bus_message),
						ct.c_char_p,
						ct.POINTER(ct.c_void_p),
						ct.POINTER(ct.c_size_t),
						] },
	{ "name": "sd_bus_message_read_basic", "args": [ct.POINTER(sd_bus_message), ct.c_char, ct.c_void_p] },
	{ "name": "sd_bus_message_enter_container", "args": [ct.POINTER(sd_bus_message), ct.c_char, ct.c_char_p] },
	{ "name": "sd_bus_message_exit_container", "args": [ct.POINTER(sd_bus_message)] },
	{ "name": "sd_bus_message_peek_type", "args": [ct.POINTER(sd_bus_message), ct.c_char_p, ct.POINTER(ct.c_char_p)] },
	{ "name": "sd_bus_message_verify_type", "args": [ct.POINTER(sd_bus_message), ct.c_char, ct.c_char_p] },
	{ "name": "sd_bus_message_at_end", "args": [ct.POINTER(sd_bus_message), ct.c_int] },
	{ "name": "sd_bus_message_rewind", "args": [ct.POINTER(sd_bus_message), ct.c_int] },
	
	{ "name": "sd_bus_message_open_container", "args": [ct.POINTER(sd_bus_message), ct.c_char, ct.c_void_p] },
	{ "name": "sd_bus_message_close_container", "args": [ct.POINTER(sd_bus_message)] },
	
	{ "name": "sd_bus_send", "args": [ct.POINTER(sd_bus), ct.POINTER(sd_bus_message), ct.POINTER(ct.c_uint64)] },
	{ "name": "sd_bus_send_to", "args": [ct.POINTER(sd_bus), ct.POINTER(sd_bus_message), ct.c_char_p, ct.POINTER(ct.c_uint64)] },
	{ "name": "sd_bus_call", "args": [ct.POINTER(sd_bus), ct.POINTER(sd_bus_message), ct.c_uint64, ct.POINTER(sd_bus_error), ct.POINTER(ct.POINTER(sd_bus_message))] },
	{ "name": "sd_bus_call_async", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)), ct.POINTER(sd_bus_message), sd_bus_message_handler_t, ct.py_object, ct.c_uint64] },

	
	{ "name": "sd_bus_get_fd", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_get_events", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_get_timeout", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.c_uint64)] },
	{ "name": "sd_bus_process", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_message))] },
	{ "name": "sd_bus_process_priority", "args": [ct.POINTER(sd_bus), ct.c_int64, ct.POINTER(ct.POINTER(sd_bus_message))] },
	{ "name": "sd_bus_wait", "args": [ct.POINTER(sd_bus), ct.c_uint64] },
	{ "name": "sd_bus_flush", "args": [ct.POINTER(sd_bus)] },
	
	{ "name": "sd_bus_get_property", "args": [
				ct.POINTER(sd_bus),
				ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p,
				ct.POINTER(sd_bus_error),
				ct.POINTER(ct.POINTER(sd_bus_message)),
				ct.c_char_p]
			},
	{ "name": "sd_bus_set_property", "args": [
				ct.POINTER(sd_bus),
				ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p,
				ct.POINTER(sd_bus_error),
				ct.c_char_p]
			},
	{ "name": "sd_bus_request_name", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.POINTER(ct.c_uint64)] },
	
	{ "name": "sd_bus_message_get_signature", "args": [ct.POINTER(sd_bus_message), ct.c_int], "restype": ct.c_char_p },
	{ "name": "sd_bus_message_get_path", "args": [ct.POINTER(sd_bus_message)], "restype": ct.c_char_p },
	{ "name": "sd_bus_message_get_interface", "args": [ct.POINTER(sd_bus_message)], "restype": ct.c_char_p },
	{ "name": "sd_bus_message_get_member", "args": [ct.POINTER(sd_bus_message)], "restype": ct.c_char_p },
	{ "name": "sd_bus_message_get_destination", "args": [ct.POINTER(sd_bus_message)], "restype": ct.c_char_p },
	{ "name": "sd_bus_message_get_sender", "args": [ct.POINTER(sd_bus_message)], "restype": ct.c_char_p },
	{ "name": "sd_bus_message_get_error", "args": [ct.POINTER(sd_bus_message)], "restype": ct.POINTER(sd_bus_error) },
	{ "name": "sd_bus_message_get_errno", "args": [ct.POINTER(sd_bus_message)] },
	
	{ "name": "sd_bus_message_get_type", "args": [ct.POINTER(sd_bus_message), ct.POINTER(ct.c_uint8)] },
	{ "name": "sd_bus_message_get_cookie", "args": [ct.POINTER(sd_bus_message), ct.POINTER(ct.c_uint64)] },
	{ "name": "sd_bus_message_get_reply_cookie", "args": [ct.POINTER(sd_bus_message), ct.POINTER(ct.c_uint64)] },
	{ "name": "sd_bus_message_get_priority", "args": [ct.POINTER(sd_bus_message), ct.POINTER(ct.c_int64)] },
	
	{ "name": "sd_bus_add_filter", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)),
										sd_bus_message_handler_t, ct.py_object]},
	{ "name": "sd_bus_add_match", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)),
										ct.c_char_p, sd_bus_message_handler_t, ct.py_object]},
	{ "name": "sd_bus_add_match_async", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)),
											  ct.c_char_p, sd_bus_message_handler_t,
											  sd_bus_message_handler_t, ct.py_object]},
	{ "name": "sd_bus_add_object_vtable", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)),
												ct.c_char_p, ct.c_char_p, ct.POINTER(sd_bus_vtable), ct.py_object] },
	{ "name": "sd_bus_add_fallback_vtable", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)), ct.c_char_p, ct.c_char_p, ct.POINTER(sd_bus_vtable), sd_bus_object_find_t, ct.py_object] },
	{ "name": "sd_bus_add_node_enumerator", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)), ct.c_char_p, sd_bus_node_enumerator_t, ct.py_object] },
	{ "name": "sd_bus_add_object_manager", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)), ct.c_char_p] },
	
	{ "name": "sd_bus_message_new_method_call", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_message)),
													 ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p] },
	
	{ "name": "sd_bus_message_append", "args": [ct.POINTER(sd_bus_message), ct.c_char_p] },
	#{ "name": "sd_bus_message_appendv", "args": [ct.POINTER(sd_bus_message), ct.c_char_p, va_list ap] },
	{ "name": "sd_bus_message_append_basic", "args": [ct.POINTER(sd_bus_message), ct.c_char, ct.c_void_p] },
	{ "name": "sd_bus_message_append_array", "args": [ct.POINTER(sd_bus_message), ct.c_char, ct.c_void_p, ct.c_size_t] },
	
	{ "name": "sd_bus_ref", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_unref", "args": [ct.POINTER(sd_bus)] },
	{ "name": "sd_bus_flush_close_unref", "args": [ct.POINTER(sd_bus)] },
	
	{ "name": "sd_bus_message_ref", "args": [ct.POINTER(sd_bus_message)], "restype": ct.POINTER(sd_bus_message) },
	{ "name": "sd_bus_message_unref", "args": [ct.POINTER(sd_bus_message)], "restype": ct.POINTER(sd_bus_message) },
	
	{ "name": "sd_bus_slot_ref", "args": [ct.POINTER(sd_bus_slot)], "restype": ct.POINTER(sd_bus_slot) },
	{ "name": "sd_bus_slot_unref", "args": [ct.POINTER(sd_bus_slot)], "restype": ct.POINTER(sd_bus_slot) },
	
	{ "name": "sd_bus_reply_method_return", "args": [ct.POINTER(sd_bus_message), ct.c_char_p] },
	
	{ "name": "sd_bus_emit_signal", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p] },

	{ "name": "sd_bus_emit_properties_changed_strv", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p, ct.POINTER(ct.c_char_p)] },
	{ "name": "sd_bus_emit_properties_changed", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p, ct.c_char_p] },

	{ "name": "sd_bus_emit_object_added", "args": [ct.POINTER(sd_bus), ct.c_char_p] },
	{ "name": "sd_bus_emit_object_removed", "args": [ct.POINTER(sd_bus), ct.c_char_p] },
	{ "name": "sd_bus_emit_interfaces_added_strv", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.POINTER(ct.c_char_p)] },
	{ "name": "sd_bus_emit_interfaces_added", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p] },
	{ "name": "sd_bus_emit_interfaces_removed_strv", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.POINTER(ct.c_char_p)] },
	{ "name": "sd_bus_emit_interfaces_removed", "args": [ct.POINTER(sd_bus), ct.c_char_p, ct.c_char_p] },
	
	{ "name": "sd_bus_match_signal", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)),
										   ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p,
										   sd_bus_message_handler_t, ct.py_object]},
	{ "name": "sd_bus_match_signal_async", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_slot)),
												 ct.c_char_p, ct.c_char_p, ct.c_char_p, ct.c_char_p,
												 sd_bus_message_handler_t,
												 sd_bus_message_handler_t, ct.py_object]},
	
	{ "name": "sd_bus_message_is_signal", "args": [ct.POINTER(sd_bus_message), ct.c_char_p, ct.c_char_p] },
	{ "name": "sd_bus_message_is_method_call", "args": [ct.POINTER(sd_bus_message), ct.c_char_p, ct.c_char_p] },
	{ "name": "sd_bus_message_is_method_error", "args": [ct.POINTER(sd_bus_message), ct.c_char_p] },
	{ "name": "sd_bus_message_is_empty", "args": [ct.POINTER(sd_bus_message)] },
	{ "name": "sd_bus_message_has_signature", "args": [ct.POINTER(sd_bus_message), ct.c_char_p] },
	
	{ "name": "sd_bus_track_new", "args": [ct.POINTER(sd_bus), ct.POINTER(ct.POINTER(sd_bus_track)), sd_bus_track_handler_t, ct.c_void_p] },
	{ "name": "sd_bus_track_ref", "args": [ct.POINTER(sd_bus_track)], "restype": ct.POINTER(sd_bus_track) },
	{ "name": "sd_bus_track_unref", "args": [ct.POINTER(sd_bus_track)], "restype": ct.POINTER(sd_bus_track) },
	
	{ "name": "sd_bus_track_get_userdata", "args": [ct.POINTER(sd_bus_track)], "restype": ct.c_void_p },
	{ "name": "sd_bus_track_set_userdata", "args": [ct.POINTER(sd_bus_track), ct.c_void_p], "restype": ct.c_void_p },
	
	{ "name": "sd_bus_track_add_sender", "args": [ct.POINTER(sd_bus_track), ct.POINTER(sd_bus_message)] },
	{ "name": "sd_bus_track_remove_sender", "args": [ct.POINTER(sd_bus_track), ct.POINTER(sd_bus_message)] },
	{ "name": "sd_bus_track_add_name", "args": [ct.POINTER(sd_bus_track), ct.c_char_p] },
	{ "name": "sd_bus_track_remove_name", "args": [ct.POINTER(sd_bus_track), ct.c_char_p] },
	]

libsystemd = ct.CDLL('libsystemd.so.0')

for f in library_functions:
	if getattr(libsystemd, f["name"], None) is None:
		if verbosity > 0:
			print(f["name"], "not found in library")
		continue
	
	def function_factory(f=f):
		def dyn_fct(*nargs, **kwargs):
			if "args" in f:
				args = f["args"]
			else:
				args = None
			if "restype" in f:
				restype = f["restype"]
			else:
				restype = ct.c_int
			
			return ct_call(f["name"], *nargs, args=args, restype=restype)
		return dyn_fct
	
	if hasattr(sys.modules[__name__], f["name"]):
		print("duplicate function", f["name"], file=sys.stderr)
	
	setattr(sys.modules[__name__], f["name"], function_factory(f))

if sys.version_info < (3,):
	def to_bytes(x):
		return x
else:
	def to_bytes(s):
		if isinstance(s, str):
			return s.encode()
		else:
			return s

def ct_call(*nargs, **kwargs):
	call = nargs[0]
	
	if "args" in kwargs:
		args = kwargs["args"]
	else:
		args = None
	if "check" in kwargs:
		check = kwargs["check"]
	else:
		check = None
	
	nargs = nargs[1:]
	
	func = getattr(libsystemd, call)
	if args:
		func.argtypes = args
	if "restype" in kwargs:
		func.restype = kwargs["restype"]
	
	newargs = tuple()
	for i in range(len(nargs)):
		newargs += (to_bytes(nargs[i]), )
	
	#print(call, newargs)
	res = func(*newargs)
	
	if verbosity > 1:
		print(call, newargs, "=", res)
	
	if (check is None or check) and func.restype in [ct.c_long, ct.c_int] and res < 0:
		raise OSError(res, call+" failed with: "+os.strerror(-res)+" ("+str(-res)+")")
	if check and isinstance(func.restype, ct.POINTER) and res == None:
		raise OSError(res, call+" returned NULL")
	
	return res

def print_next_type(msg):
	typ = ct.c_char()
	content_sign = ct.c_char_p()
	
	sd_bus_message_peek_type(msg, ct.byref(typ), ct.byref(content_sign))
	print("next", typ.value, content_sign.value)

if __name__ == "__main__":
	bus = ct.POINTER(sd_bus)()
	sd_bus_default_system(ct.byref(bus))
	
	error = sd_bus_error()
	reply = ct.POINTER(sd_bus_message)()
	try:
		sd_bus_call_method(
			bus,
			b'org.freedesktop.systemd1',
			b'/org/freedesktop/systemd1',
			b'org.freedesktop.systemd1.Manager',
			b'Dump',
			ct.byref(error),
			ct.byref(reply),
			b'')
		
		dump_string = ct.c_char_p()
		sd_bus_message_read(reply, b's', ct.byref(dump_string))
		
		print(dump_string.value.decode())
	finally:
		sd_bus_flush_close_unref(bus)
