#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys

import threading

import gobject
import dbus
import dbus.service
import dbus.mainloop.glib

import argparse

import logging

import lockfile

#We depend on the PythonVtunLib from http://sirius.limousin.fr.grpleg.com/gitlab/ains/pythonvtunlib
from pythonvtunlib import vtun_tunnel

progname = os.path.basename(sys.argv[0])

tundev_manager = None

DBUS_NAME = 'com.legrandelectric.RemoteAccess.TundevManager'	# The name of bus we are creating in D-Bus
DBUS_OBJECT_ROOT = '/com/legrandelectric/RemoteAccess/TundevManager'	# The root under which we will create a D-Bus object with the username of the account for the tunnelling device for D-Bus communication, eg: /com/legrandelectric/RemoteAccess/TundevManager/1000 to communicate with a TundevBinding instance running for the UNIX account 1000 (/home/1000)
DBUS_SERVICE_INTERFACE = 'com.legrandelectric.RemoteAccess.TundevManager'	# The name of the D-Bus service under which we will perform input/output on D-Bus

class TundevBinding(object):
    """ Class representing a tunnelling dev connected to the RDV server
    Among other, it will make sure the life cycle of the vtun tunnels are handled in a centralised way
    There should be only one instance of TundevBinding per username on the system (this is taken care for by class TundevManagerDBusService)
    """
    
    def __init__(self, username, shell_alive_lock_fn = None):
        """ Create a new object to represent a tunnelling device from the vtun manager perspective
        \param username The username (account) of the tundev_shell that is object will be bound to
        \param shell_alive_lock_fn A filename on which the shell has grabbed an exclusive lock. The tundev_shell will keep this filesystem lock as long as it requires the vtun tunnel to be kept up.
        """
        self.username = username
        self.shell_lock_fn = shell_alive_lock_fn    # Fixme: start a thread that will try to grab this lock and perform tunnel cleanup if it does, or do it in configure_service()
        self.vtun_server_tunnel = None
        
        if self.username == '1000':    # For our (only) onsite RPI
            self.tundev_role = 'onsite'
        elif self.username == '1001':    # For our (only) master RPI
            self.tundev_role = 'master'
        else:
            raise Exception('UnknownTundevAccount:' + str(self.username))

    def configure_service(self, mode):
        """ Configure a tunnel server to handle connectivity with this tunnelling device
        
        \param mode A string or TunnelMode object describing the type of tunnel (L2, L3 etc...)
        """
        
        if self.tundev_role == 'onsite':    # For our (only) onsite RPI
            self.vtun_server_tunnel = vtun_tunnel.ServerVtunTunnel(mode = mode, tunnel_ip_network = '192.168.100.0/30', tunnel_near_end_ip = '192.168.100.1', tunnel_far_end_ip = '192.168.100.2', vtun_server_tcp_port = 5000)
            self.vtun_server_tunnel.restrict_server_to_iface('lo')
            self.vtun_server_tunnel.set_shared_secret(self.username)
            self.vtun_server_tunnel.set_tunnel_name('tundev' + self.username)
        elif self.tundev_role == 'master':    # For our (only) master RPI
            self.vtun_server_tunnel = vtun_tunnel.ServerVtunTunnel(mode = mode, tunnel_ip_network = '192.168.101.0/30', tunnel_near_end_ip = '192.168.101.1', tunnel_far_end_ip = '192.168.101.2', vtun_server_tcp_port = 5001)
            self.vtun_server_tunnel.restrict_server_to_iface('lo')
            self.vtun_server_tunnel.set_shared_secret(self.username)
            self.vtun_server_tunnel.set_tunnel_name('tundev' + self.username)

    def start_vtun_server(self):
        """ Start a vtund server to handle connectivity with this tunnelling device
        """
        if not self.vtun_server_tunnel is None:
            self.vtun_server_tunnel.start()
        else:
            raise Exception('VtunServerCannotBeStarted:NotConfigured')

    def stop_vtun_server(self):
        """ Stop the vtund server that is handling connectivity with this tunnelling device
        """
        if not self.vtun_server_tunnel is None:
            self.vtun_server_tunnel.stop()
        else:
            raise Exception('VtunServerCannotBeStopped:NotConfigured')

    def to_corresponding_client_tundev_shell_config(self):
        """ Generate the tundev shell output string for a client tunnel corresponding to this configured vtun server
        
        This has the same format as the tundev shell command get_vtun_parameters
        
        \return A list of strings containing in each entry, a line for the tundev shell output
        """
        matching_client_tunnel = vtun_tunnel.ClientVtunTunnel(from_server = self.vtun_server_tunnel)
        # In shell output, we actually do not specify the vtun_server_hostname, because it is assumed to be tunnelled inside ssh (it is thus localhost)
        result = []
        result += ['tunnel_ip_network: ' + str(matching_client_tunnel.tunnel_ip_network.network)]
        result += ['tunnel_ip_prefix: /' + str(matching_client_tunnel.tunnel_ip_network.prefixlen)]
        result += ['tunnel_ip_netmask: ' + str(matching_client_tunnel.tunnel_ip_network.netmask)]
        result += ['tunnelling_dev_ip_address: ' + str(matching_client_tunnel.tunnel_near_end_ip)]
        result += ['rdv_server_ip_address: ' + str(matching_client_tunnel.tunnel_far_end_ip)]
        if matching_client_tunnel.vtun_server_tcp_port is None:
            raise Exception('TcpPortCannotBeNone')
        else:
            result += ['rdv_server_vtun_tcp_port: ' + str(matching_client_tunnel.vtun_server_tcp_port)]
        result += ['tunnel_secret: ' + str(matching_client_tunnel.tunnel_key)]
        return result
    
    def destroy(self):
        """ This is a destructor for this object... it makes sure we perform all the cleanup before this object is garbage collected
        
        This method will not rasie exceptions
        """
        try:
            logger.warning('Deleting binding for username ' + self.username)
            self.vtun_server_tunnel.stop()
        except:
            pass

class TundevBindingDBusService(TundevBinding, dbus.service.Object):
    """ Class allowing to send/receive D-Bus requests to a TundevBinding object
    """
    def __init__(self, conn, username, dbus_object_path, shell_alive_lock_fn = None, **kwargs):
        """ Instanciate a new TundevBindingDBusService handling the user account \p username
        \param conn A D-Bus connection object
        \param dbus_loop A main loop to use to process D-Bus request/signals
        \param dbus_object_path The path of the object to handle on D-Bus
        \param username Inherited from TundevBinding.__init__()
        \param shell_alive_lock_fn  Inherited from TundevBinding.__init__()
        """
        # Note: **kwargs is here to make this contructor more generic (it will however force args to be named, but this is anyway good practice) and is a step towards efficient mutliple-inheritance with Python new-style-classes
        if username is None:
            raise Exception('MissingUsername')
        
        dbus.service.Object.__init__(self, conn = conn, object_path = dbus_object_path)
        TundevBinding.__init__(self, username = username, shell_alive_lock_fn = shell_alive_lock_fn)
        
        logger.debug('Registered binding with D-Bus object PATH: ' + str(dbus_object_path))
    
    # D-Bus-related methods
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='s', out_signature='')
    def ConfigureService(self, mode):
        """ Configure a tunnel server to handle connectivity with this tunnelling device
        
        \param mode A string or TunnelMode object describing the type of tunnel (L2, L3 etc...)
        """
        logger.debug('/' + self.username + ' Got ConfigureService(' + str(mode) + ') D-Bus request')
        self.configure_service(mode)
        
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='')
    def StartTunnelServer(self):
        """ Start a vtund server to handle connectivity with this tunnelling device
        """
        
        logger.debug('/' + self.username + ' Got StartTunnelServer() D-Bus request')
        self.start_vtun_server()
    
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='')
    def StopTunnelServer(self):
        """ Stop a vtund server to handle connectivity with this tunnelling device
        """
        
        logger.debug('/' + self.username + ' Got StopTunnelServer() D-Bus request')
        self.stop_vtun_server()
    
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='as')
    def GetAssociatedClientTundevShellConfig(self):
        """ Generate the tundev shell output string for a client tunnel corresponding to this configured vtun server
        
        This has the same format as the tundev shell command get_vtun_parameters
        
        \return A list of strings containing in each entry, a line for the tundev shell output
        """
        
        logger.debug('/' + self.username + ' Got GetAssociatedClientTundevShellConfig() D-Bus request')
        return self.to_corresponding_client_tundev_shell_config()
    
    def destroy(self):
        self.remove_from_connection()   # Unregister this object
        TundevBinding.destroy(self) # Call TundevBinding's destroy

class TundevManagerDBusService(dbus.service.Object):
    """ Class allowing to send D-Bus requests to a TundevManager object
    """
    
    def __init__(self, conn, dbus_object_path = DBUS_OBJECT_ROOT, **kwargs):
        """ Constructor a new TundevManagerDBusService handling D-Bus requests from tundev shells
        
        Initialise with an empty TunDevBindingDBusService dict
        
        \param conn A D-Bus connection object
        \param dbus_object_path The object path to handle on D-Bus
        """
        # Note: **kwargs is here to make this contructor more generic (it will however force args to be named, but this is anyway good practice) and is a step towards efficient mutliple-inheritance with Python new-style-classes
        self._conn = conn   # Store the connection object... we will pass it to bindings we generate
        dbus.service.Object.__init__(self, conn = self._conn, object_path = dbus_object_path)
        
        self._tundev_dict = {}    # Initialise with an empty TunDevBinding dict
        self._tundev_dict_mutex = threading.Lock() # This mutex protects writes and reads to the _tundev_dict attribute

    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='sss', out_signature='s')
    def RegisterTundevBinding(self, username, mode, shell_alive_lock_fn):
        """ Register a new tunnelling device to the TundevManager
        
        \param username Username of the account used by the tunnelling device
        \param mode A string containing the tunnel mode (L2, L3 etc...)
        \param shell_alive_lock_fn Lock filename to check that tundev shell process is alive (will be passed to the generated binding's constructor as is)

        \return We will return the newly instanciated TundevBindingDBusService object path
        """
        
        new_binding_object_path = DBUS_OBJECT_ROOT + '/' + username
        
        with self._tundev_dict_mutex:
            logger.debug('Registering binding for username ' + str(username))
            old_binding = self._tundev_dict.pop(username, None)
            if not old_binding is None:
                logger.warning('Duplicate username ' + str(username) + '. First deleting previous binding')
                old_binding.destroy()
            
            new_binding = TundevBindingDBusService(conn = self._conn, username = username, shell_alive_lock_fn = shell_alive_lock_fn, dbus_object_path = new_binding_object_path)
                
            self._tundev_dict[username] = new_binding
        
        self._tundev_dict[username].configure_service(mode)
        
        return new_binding_object_path  # Reply the full D-Bus object path of the newly generated biding to the caller
    
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='as')
    def DumpTundevBindings(self):
        """ Dump all TundevBindingDBusService objects registerd
        
        \return We will return an array of instanciated TundevBindingDBusService object paths
        """
        
        with self._tundev_dict_mutex:
            tundev_bindings_username_list = self._tundev_dict.keys()
        
        return map( lambda p: DBUS_OBJECT_ROOT + '/' + p, tundev_bindings_username_list)


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True) # Use Glib's mainloop as the default loop for all subsequent code

if __name__ == '__main__':
    #atexit.register(cleanupAtExit)
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="This program launches a vtun manager daemon. \
It will handle tunnel creation/destruction on behalf of tundev_shell processes, via D-Bus methods and signal. \
It will also connects onsite to master tunnels to create an end-to-end session", prog=progname)
    parser.add_argument('-d', '--debug', action='store_true', help='display debug info', default=False)
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig()
    
    logger = logging.getLogger(__name__)
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(asctime)s %(name)s():%(lineno)d %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    
    logger.debug(progname + ": Starting")

    # Prepare D-Bus environment
    system_bus = dbus.SystemBus(private=True)
# Probably not required
#    gobject.threads_init() # Allow the mainloop to run as an independent thread
#    dbus.mainloop.glib.threads_init()
    name = dbus.service.BusName(DBUS_NAME, system_bus) # Publish the name to the D-Bus so that clients can see us
    #signal.signal(signal.SIGINT, signalHandler) # Install a cleanup handler on SIGINT and SIGTERM
    #signal.signal(signal.SIGTERM, signalHandler)
    dbus_loop = gobject.MainLoop()
    
    # Instanciate a TundevManagerDBusService
    tundev_manager = TundevManagerDBusService(conn = system_bus, dbus_loop = dbus_loop)
    
    # Loop
    dbus_loop.run()

