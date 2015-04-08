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

import fcntl    # For flock()

import atexit

#We depend on the PythonVtunLib from http://sirius.limousin.fr.grpleg.com/gitlab/ains/pythonvtunlib
from pythonvtunlib import server_vtun_tunnel
from pythonvtunlib import client_vtun_tunnel

progname = os.path.basename(sys.argv[0])

tundev_manager = None

DBUS_NAME = 'com.legrandelectric.RemoteAccess.TundevManager'	# The name of bus we are creating in D-Bus
DBUS_OBJECT_ROOT = '/com/legrandelectric/RemoteAccess/TundevManager'	# The root under which we will create a D-Bus object with the username of the account for the tunnelling device for D-Bus communication, eg: /com/legrandelectric/RemoteAccess/TundevManager/1000 to communicate with a TundevBinding instance running for the UNIX account 1000 (/home/1000)
DBUS_SERVICE_INTERFACE = 'com.legrandelectric.RemoteAccess.TundevManager'	# The name of the D-Bus service under which we will perform input/output on D-Bus

def cleanup_at_exit():
    """
    Called when this program is terminated, to release the lock
    """
    
    global tundev_manager
    
    if tundev_manager:
        print(progname + ': Shutting down', file=sys.stderr)   # For debug
        tundev_manager.destroy()
        tundev_manager = None

# def signal_handler(signum, frame):
#     """
#     Called when receiving a UNIX signal
#     Will only terminate if receiving a SIGINT or SIGTERM, otherwise, just ignore the signal
#     """
#      
#     if signum == signal.SIGINT or signum == signal.SIGTERM:
#         cleanup_at_exit()
#     else:
#         #print(progname + ': Ignoring signal ' + str(signum), file=sys.stderr)
#         pass


class TundevVtun(object):
    """ Class representing a vtun serving a tunnelling device connected to the RDV server
    Among other, it will make sure the life cycle of the vtun tunnels are handled in a centralised way
    There should be only one instance of TundevVtun per username on the system (this is taken care for by class TundevManagerDBusService)
    """
    
    VTUND_EXEC = '/usr/local/sbin/vtund'
    
    def __init__(self, username):
        """ Create a new object to represent a tunnelling device from the vtun manager perspective
        
        \param username The username (account) of the tundev_shell that is object will be bound to
        """
        self.username = username
        self.vtun_server_tunnel = None
        
        if self.username == 'rpi1100' or self.username == 'rpi1002': # For our (only) onsite RPI (1002 is for debug)
            self.tundev_role = 'onsite'
        elif self.username == 'rpi1101' or self.username == 'rpi1003': # For our (only) master RPI (1003 is for debug)
            self.tundev_role = 'master'
        else:
            raise Exception('UnknownTundevAccount:' + str(self.username))

    def configure_service(self, mode, uplink_ip):
        """ Configure a tunnel server to handle connectivity with this tunnelling device
        
        \param mode A string or TunnelMode object describing the type of tunnel (L2, L3 etc...)
        \param uplink_ip The IP on the uplink interface of the tundev
        """
        
        vtun_tunnel_name = 'tundev' + self.username
        vtun_shared_secret = '_' + self.username
        if self.tundev_role == 'onsite':    # For our (only) onsite RPI
            self.vtun_server_tunnel = server_vtun_tunnel.ServerVtunTunnel(vtund_exec = TundevVtun.VTUND_EXEC, mode = mode, tunnel_ip_network = '192.168.100.0/30', tunnel_near_end_ip = '192.168.100.1', tunnel_far_end_ip = '192.168.100.2', vtun_server_tcp_port = 5000, vtun_tunnel_name = vtun_tunnel_name, vtun_shared_secret = vtun_shared_secret)
            self.vtun_server_tunnel.restrict_server_to_iface('lo')
        elif self.tundev_role == 'master':    # For our (only) master RPI
            self.vtun_server_tunnel = server_vtun_tunnel.ServerVtunTunnel(vtund_exec = TundevVtun.VTUND_EXEC, mode = mode, tunnel_ip_network = '192.168.101.0/30', tunnel_near_end_ip = '192.168.101.1', tunnel_far_end_ip = '192.168.101.2', vtun_server_tcp_port = 5001, vtun_tunnel_name = vtun_tunnel_name, vtun_shared_secret = vtun_shared_secret)
            self.vtun_server_tunnel.restrict_server_to_iface('lo')

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
        matching_client_tunnel = client_vtun_tunnel.ClientVtunTunnel(from_server = self.vtun_server_tunnel)
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
        result += ['tunnel_secret: ' + str(matching_client_tunnel.get_shared_secret())]
        return result
    
    def destroy(self):
        """ This is a destructor for this object... it makes sure we perform all the cleanup before this object is garbage collected
        
        This method will not raise exceptions
        """
        try:
            logger.warning('Deleting vtun serving username ' + self.username)
            self.vtun_server_tunnel.stop()
        except:
            pass

class TundevVtunDBusService(TundevVtun, dbus.service.Object):
    """ Class allowing to send/receive D-Bus requests to a TundevVtun object
    """
    def __init__(self, conn, username, dbus_object_path, **kwargs):
        """ Instanciate a new TundevVtunDBusService handling the user account \p username
        \param conn A D-Bus connection object
        \param dbus_loop A main loop to use to process D-Bus request/signals
        \param dbus_object_path The path of the object to handle on D-Bus
        \param username Inherited from TundevBinding.__init__()
        """
        # Note: **kwargs is here to make this contructor more generic (it will however force args to be named, but this is anyway good practice) and is a step towards efficient mutliple-inheritance with Python new-style-classes
        if username is None:
            raise Exception('MissingUsername')
        
        dbus.service.Object.__init__(self, conn = conn, object_path = dbus_object_path)
        TundevVtun.__init__(self, username = username)
        
        logger.debug('Registered binding with D-Bus object PATH: ' + str(dbus_object_path))
    
    # D-Bus-related methods
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='ss', out_signature='')
    def ConfigureService(self, mode, uplink_ip):
        """ Configure a tunnel server to handle connectivity with this tunnelling device
        \param mode A string or TunnelMode object describing the type of tunnel (L2, L3 etc...)
    \param uplink_ip The IP on the uplink interface of the tundev
        """
        logger.debug('/' + self.username + ' Got ConfigureService(' + str(mode) +','+ str(uplink_ip) + ') D-Bus request')
        self.configure_service(mode, uplink_ip)
        
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
    
    
    @dbus.service.signal(dbus_interface = DBUS_SERVICE_INTERFACE)
    def VtunAllowedSignal(self):
         # The signal is emitted when this method exits
         # You can have code here if you wish
        pass
    
    #FIXME: To remove later as it is on a method to emit the unblocking signal for onsitedevshell
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='s')
    def EmitWaitVtunSignal(self):
        self.VtunAllowedSignal()
        return "Signal emitted"
    
    def destroy(self):
        self.remove_from_connection()   # Unregister this object
        TundevVtun.destroy(self) # Call TundevBinding's destroy

class TunDevShellWatchdog(object):
    """ Class allowing to monitor a filesystem lock and invoke a callback when the lock goes away
    
    This is a watchdog on a tundev shell process. When/if the tundev shell process dies, it will release a filesystem lock that we will detect here
    The callback method to be called is provided using method set_unlock_callback() below
    """
    
    def __init__(self, shell_alive_lock_fn):
        self.lock_fn = shell_alive_lock_fn
        self._lock_fn_watchdog_thread = threading.Thread(target = self._check_lock_fn)
        self._lock_fn_watchdog_thread.setDaemon(True) # D-Bus loop should be forced to terminate when main program exits
        self._lock_fn_watchdog_thread.start()
        self._unlock_callback = None

    def set_unlock_callback(self, unlock_callback):
        """ Set the function that will be called when the watchdog triggers
        
        \param unlock_callback The function to call
        """
        if hasattr(unlock_callback, '__call__'):
            self._unlock_callback = unlock_callback
        else:
            raise Exception('WrongCallback')
    
    def _check_lock_fn(self):
        """ Block on the file flocked() by the shell
        
        This method will perform the actual watchdog function (it is blocking and thus must be run inide a separate thread).
        It will only finish if the lock is lost, we will then call the callback function set with set_unlock_callback()
        """
        logger.debug('Starting shell alive watchdog on file "' + self.lock_fn + '"')
        shell_lockfile_fd = open(self.lock_fn, 'r')
        fcntl.flock(shell_lockfile_fd, fcntl.LOCK_EX)
        # Lionel: FIXME: the watchdog is not triggered immediately... this is probably because of the glib's mainloop
        # We only get the notification for the watchdog at the next D-Bus request...
        logger.warning('Tundev shell exitted (lock file "' + self.lock_fn + '" was released')
        # When we get here, it means the lock was released, that is the tundev shell process exitted
        if self._unlock_callback is None:
            logger.debug('Watchdog triggered but will be ignored because no unlock callback was setup')
        else:
            logger.debug('Watchdog triggered. Invoking unlock callback ' + str(self._unlock_callback))
            self._unlock_callback()
            
    def destroy(self):
        """ This is a destructor for this object... it makes sure we perform all the cleanup before this object is garbage collected
        
        This method will not raise exceptions
        """
        try:
            self._unlock_callback = None    # Disable the callback
        except:
            pass
        
    
class TundevShellBinding(object):
    """ Class used to pack together a TundevBindingDBusService object and the corresponding filesystem lock watchdog
    
    Objects of this class only have attributes (there are no method): 
    """
    def __init__(self):
        self.vtunService = None
        self.shellAliveWatchdog = None
        
    def destroy(self):
        """ This is a destructor for this object... it makes sure we perform all the cleanup before this object is garbage collected
        
        This method will not raise exceptions
        """
        try:
            if not self.shellAliveWatchdog is None:
                self.shellAliveWatchdog.destroy()
            if not self.vtunService is None:
                self.vtunService.destroy()
        except:
            pass

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

    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='ssss', out_signature='s')
    def RegisterTundevBinding(self, username, mode, uplink_ip, shell_alive_lock_fn):
        """ Register a new tunnelling device to the TundevManagerDBusService
        
        \param username Username of the account used by the tunnelling device
        \param mode A string containing the tunnel mode (L2, L3 etc...)
    \param uplink_ip The IP on the uplink interface of the tundev
        \param shell_alive_lock_fn Lock filename to check that the tundev shell process that depends on this binding is still alive. This is a filename on which the shell has grabbed an exclusive OS-level lock (flock()). The tundev_shell will keep this filesystem lock as long as it requires the vtun tunnel to be kept up.
        \return We will return the D-Bus object path for the newly instanciated binding
        """
        
        new_binding_object_path = DBUS_OBJECT_ROOT + '/' + username
        
        with self._tundev_dict_mutex:
            logger.debug('Registering binding for username ' + str(username))
            old_binding = self._tundev_dict.pop(username, None)
            if not old_binding is None:
                logger.warning('Duplicate username ' + str(username) + '. First deleting previous binding')
                old_binding.destroy()
            
            new_binding = TundevShellBinding()
            new_binding.vtunService = TundevVtunDBusService(conn = self._conn, username = username, dbus_object_path = new_binding_object_path)
            new_binding.shellAliveWatchdog = TunDevShellWatchdog(shell_alive_lock_fn)
            new_binding.shellAliveWatchdog.set_unlock_callback(new_binding.vtunService.destroy)
                
            self._tundev_dict[username] = new_binding
        
        self._tundev_dict[username].vtunService.configure_service(mode, uplink_ip)
        
        return new_binding_object_path  # Reply the full D-Bus object path of the newly generated biding to the caller
        
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='s', out_signature='')
    def UnregisterTundevBinding(self, username):
        """ Register a new tunnelling device to the TundevManagerDBusService
        
        \param username Username of the account used by the tunnelling device
        """
        
        with self._tundev_dict_mutex:
            logger.debug('Unregistering binding for username ' + str(username))
            try:
                del self._tundev_dict[username]
            except:
                pass
    
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='as')
    def DumpTundevBindings(self):
        """ Dump all TundevBindingDBusService objects registerd
        
        \return We will return an array of instanciated TundevBindingDBusService object paths
        """
        
        with self._tundev_dict_mutex:
            tundev_bindings_username_list = self._tundev_dict.keys()
        
        return map( lambda p: DBUS_OBJECT_ROOT + '/' + p, tundev_bindings_username_list)

    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='as')
    def GetOnlineOnsiteDevs(self):
        """ List all online onsite devices ids
        
        \return We will return an array of online onsite devices ids
        """
        
        online_onsite_devs_list = []
        with self._tundev_dict_mutex:
            for dev in self._tundev_dict.values():
                if dev.vtunService.tundev_role == 'onsite':
                    online_onsite_devs_list += [dev.vtunService.username]
        return online_onsite_devs_list

    def destroy(self):
        """ This is a destructor for this object... it makes sure we perform all the cleanup before this object is garbage collected
        
        This method will not raise exceptions
        """
        try:
            logger.warning('Deleting all bindings')
            with self._tundev_dict_mutex:
                for (key, val) in self._tundev_dict.iteritems():
                    logger.warning('Deleting binding for username ' + str(key))
                    val.destroy()   # Destroy all bindings
                self._tundev_dict.clear() # Wipe out the content of the dict
        except:
            pass


# Main program
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True) # Use Glib's mainloop as the default loop for all subsequent code

if __name__ == '__main__':
    atexit.register(cleanup_at_exit)
    
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
    
    name = dbus.service.BusName(DBUS_NAME, system_bus) # Publish the name to the D-Bus so that clients can see us
    #signal.signal(signal.SIGINT, signal_handler) # Install a cleanup handler on SIGINT and SIGTERM
    #signal.signal(signal.SIGTERM, signal_handler)
    
    # Allow secondary threads to run during the mainloop (required for class TunDevShellWatchdog to trigger the watchdog immediately)
    gobject.threads_init() # Allow the mainloop to run as an independent thread
    dbus.mainloop.glib.threads_init()
    
    dbus_loop = gobject.MainLoop()
    
    # Instanciate a TundevManagerDBusService
    tundev_manager = TundevManagerDBusService(conn = system_bus, dbus_loop = dbus_loop)
    
    # Loop
    dbus_loop.run()

