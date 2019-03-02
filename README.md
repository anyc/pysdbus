
pysdbus
=======

pysdbus is a Python wrapper library for DBus inter-process communication. It
uses Python's ctypes module to communicate directly with the sd-bus C API of the
systemd library. Hence, pysdbus only depends on the presence of the
libsystemd.so library and a functional Python interpreter in version 2 or 3.

pysdbus offers three APIs:
 * `pysdbus.llapi` is the low-level API and a thin ctypes wrapper around
   libsystemd's C API
 * `pysdbus` is the main API of this library and provides additional convenience
   around the low-level API
 * `pysdbus.dbus` aims to provide a programming interface similar to the
   well-known dbus-python project

Status
------

This library is still in an early stage. Many features are still missing but
calling and offering APIs with methods, signals and properties is already
implemented.

pysdbus example
---------------

```
import pysdbus

bus = pysdbus.RemoteSystemBus("root@homegear")

obj = bus.getObject("org.freedesktop.DBus", "/org/freedesktop/DBus")

iface = obj.getInterface("org.freedesktop.DBus")

reply = iface.ListNames()

for service in reply:
        print(service)
```

pysdbus.dbus example
--------------------

```
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
```

