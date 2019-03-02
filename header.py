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

from os import environ

dbus_object_manager_interface="org.freedesktop.DBus.ObjectManager"
dbus_properties_interface="org.freedesktop.DBus.Properties"
dbus_introspectable_interface="org.freedesktop.DBus.Introspectable"

if "PYSDBUS_VERBOSITY" in environ:
	verbosity = int(environ["PYSDBUS_VERBOSITY"])
else:
	verbosity = 0
