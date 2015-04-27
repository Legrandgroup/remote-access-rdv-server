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
from pythonvtunlib import tunnel_mode 

import subprocess
import ipaddr

progname = os.path.basename(sys.argv[0])

tundev_manager = None

DBUS_NAME = 'com.legrandelectric.RemoteAccess.TundevManager'	# The name of bus we are creating in D-Bus
DBUS_OBJECT_ROOT = '/com/legrandelectric/RemoteAccess/TundevManager'	# The root under which we will create a D-Bus object with the username of the account for the tunnelling device for D-Bus communication, eg: /com/legrandelectric/RemoteAccess/TundevManager/1000 to communicate with a TundevBinding instance running for the UNIX account 1000 (/home/1000)
DBUS_SERVICE_INTERFACE = 'com.legrandelectric.RemoteAccess.TundevManager'	# The name of the D-Bus service under which we will perform input/output on D-Bus

setForwardPolicyToAcceptAtExit = False

def cleanup_at_exit():
    """
    Called when this program is terminated, to release the lock
    """
    
    global tundev_manager
    
    if tundev_manager:
        print(progname + ': Shutting down', file=sys.stderr)   # For debug
        tundev_manager.destroy()
        tundev_manager = None
        
    #Set FORWARD policy to ACCEPT if it was to accept when the manage was launch
    if setForwardPolicyToAcceptAtExit:
        os.system('iptables -P FORWARD ACCEPT  > /dev/null 2>&1')

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
            #We set up the interface name to the corresponding devshell
            iface_name = ''
            if self.vtun_server_tunnel.tunnel_mode.get_mode() == 'L2':
                iface_name += 'tap'
            if self.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3':
                iface_name += 'tun'
            if self.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3_multi':
                iface_name += 'tunM'
                    
            iface_name += "_to_"
            iface_name += self.username
            self.vtun_server_tunnel.set_interface_name(iface_name)
            
            #We set up the up & down block commands (basically dbus method call to notify the interface status change
            #dbus-send --system --print-reply --dest=com.legrandelectric.RemoteAccess.TundevManager /com/legrandelectric/RemoteAccess/TundevManager com.legrandelectric.RemoteAccess.TundevManager.TunnelInterfaceStatusUpdate string:'rpi1101' string:'tun_to_rpi1101' string:'up'
            #Command should be provided with full path
            #Also, parameters are between doubles quotes "
            def generate_dbus_call_for_status(status):
                command =  '/usr/bin/dbus-send '
                command += '"--system --print-reply'
                command += ' --dest=' + DBUS_SERVICE_INTERFACE + ' '
                command += DBUS_OBJECT_ROOT + ' '
                command += DBUS_SERVICE_INTERFACE +'.TunnelInterfaceStatusUpdate '
                command += ' string:' + self.username 
                command += ' string:' + iface_name
                command += ' string:' + str(status)
                command += '"'
                return command
            
            #For Up Block
            up_command = generate_dbus_call_for_status('up')
            self.vtun_server_tunnel.add_up_command(up_command)
            #For Down Block
            down_command = generate_dbus_call_for_status('down')
            self.vtun_server_tunnel.add_down_command(down_command)
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

    def set_unlock_callback(self, unlock_callback, arg):
        """ Set the function that will be called when the watchdog triggers
        
        \param unlock_callback The function to call
        \param username The username parameter for the  callback
        """
        if hasattr(unlock_callback, '__call__'):
            self._unlock_callback = unlock_callback
            self._arg = arg
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
            self._unlock_callback(self._arg)
            
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
    def __init__(self, uplink_ip):
        self.vtunService = None
        self.shellAliveWatchdog = None
        
        self.lan_ip = ipaddr.IPv4Network(str(uplink_ip))
        
    def destroy(self):
        """ This is a destructor for this object... it makes sure we perform all the cleanup before this object is garbage collected
        
        This method will not raise exceptions
        """
        username = self.vtunService.username
        try:
            #FIXME: Race condition if watchdog triggers while we are executing this method
            if not self.shellAliveWatchdog is None:
                #We set attribute to None in order to execute this piece of code only one
                copy = self.shellAliveWatchdog
                self.shellAliveWatchdog = None
                copy.destroy()
            if not self.vtunService is None:
                #We set attribute to None in order to execute this piece of code only one
                copy = self.vtunService
                self.vtunService = None
                copy.destroy()
        except:
            pass

class Session:
    def __init__(self, master_dev_id, onsite_dev_id):
        self.master_dev_id = master_dev_id
        self.onsite_dev_id = onsite_dev_id
        self.master_dev_iface = None
        self.onsite_dev_iface = None
        
    def __eq__(self, other):
        if (self.master_dev_id == other.master_dev_id 
            and self.onsite_dev_id == other.onsite_dev_id
            and self.master_dev_iface == other.master_dev_iface 
            and self.onsite_dev_iface == other.onsite_dev_iface):
            return True
        else:
            return False
    
    def __str__(self):
        if not self.onsite_dev_iface is None and not self.master_dev_iface is None:
            return '(' + str(self.master_dev_id) + ', ' + str(self.onsite_dev_id) + '): [M]' + self.master_dev_iface + ' <-> [O]' + self.onsite_dev_iface 
        else:
            return '(' + str(self.master_dev_id) + ', ' + str(self.onsite_dev_id) + ')'
    
    def get_status(self):
        """Provides the status of this session (aka , up, odnw of in-progress)
        \return The status of this session
        """
        if self.master_dev_iface is None and self.onsite_dev_iface is None:
            return 'down'
        elif not self.master_dev_iface is None and not self.onsite_dev_iface is None: 
            return 'up'
        elif not self.master_dev_iface is None or not self.onsite_dev_iface is None:
            return 'in-progress'
        
        
        raise Exception('InvalidSessionStatus')

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
        
        self._session_pool = []    # Initialise with an empty Session array
        self._session_pool_mutex = threading.Lock() # This mutex protects writes and reads to the _session_pool attribute

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
            logger.debug('Registering binding for username ' + str(username) + '(' + username + ', ' + mode + ', ' + uplink_ip + ')')
            old_binding = self._tundev_dict.pop(username, None)
            if not old_binding is None:
                logger.warning('Duplicate username ' + str(username) + '. First deleting previous binding')
                old_binding.destroy()
            
            new_binding = TundevShellBinding(uplink_ip)
            new_binding.vtunService = TundevVtunDBusService(conn = self._conn, username = username, dbus_object_path = new_binding_object_path)
            new_binding.shellAliveWatchdog = TunDevShellWatchdog(shell_alive_lock_fn)
            new_binding.shellAliveWatchdog.set_unlock_callback(self.UnregisterTundevBinding, username)
            
            self._tundev_dict[username] = new_binding
        
        self._tundev_dict[username].vtunService.configure_service(mode, uplink_ip)
        
        return new_binding_object_path  # Reply the full D-Bus object path of the newly generated biding to the caller
        
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='s', out_signature='')
    def UnregisterTundevBinding(self, username):
        """ Register a new tunnelling device to the TundevManagerDBusService
        
        \param username Username of the account used by the tunnelling device
        """
        with self._tundev_dict_mutex:
            #Unregistering the device
            logger.debug('Unregistering binding for username ' + str(username))
            tundev_binding = None
            try:
                #Destroy the TundevBinding
                tundev_binding = self._tundev_dict[username]
                tundev_binding.destroy()
                #Clean the dictionary of registered devices
                del self._tundev_dict[username]
            except KeyError:
                pass

            if not tundev_binding is None:        
                #Clean the registered sessions that include the unregistered device
                with self._session_pool_mutex:
                    def isPartOfSession(session, username):
                        if session.onsite_dev_id == username or session.master_dev_id == username:
                            return True
                        else:
                            return False
                    
                    def getOtherMember(session, username):
                        if session.onsite_dev_id == username:
                            return session.master_dev_id
                        else:
                            return session.onsite_dev_id
                      
                    #Looking for its session partner name
                    to_remove = None
                    for session in self._session_pool:
                        if isPartOfSession(session, username):
                            to_remove = getOtherMember(session, username)
                            break
                        
                    
                    
                    
                    #We only keep the session that don't have the unregistered username as a member (either master or onsite)
                    self._session_pool = [s for s in self._session_pool if not isPartOfSession(s, username)]
                    
                    #We set down the other session partner
                    if not to_remove is None:
                        #logger.debug('to_remove is not None')
                        if self._tundev_dict[to_remove]:
                            #logger.debug('to_remove is in dict')
                            if not self._tundev_dict[to_remove].vtunService.vtun_server_tunnel is None:
                                #logger.debug('to_remove vtun server tunnel is not None')
                                self._tundev_dict[to_remove].vtunService.vtun_server_tunnel.stop()
                                
                    logger.debug('Sessions pool after unregister ' + str(self._session_pool))
            
    
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
        
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='ss', out_signature='')
    def ConnectMasterDevToOnsiteDev(self, master_dev_id, onsite_dev_id):
        """ Connect a master device to an onsite device.
        \param master_dev_id The master device identifier
        \param onsite_dev_id The onsite device identifier
        """
        with self._tundev_dict_mutex:
            with self._session_pool_mutex:
                try:
                    self._tundev_dict[master_dev_id]
                except:
                    raise Exception('MasterDeviceIsNotRegistered')
                    
                try:
                    self._tundev_dict[onsite_dev_id]
                except:
                    raise Exception('OnsiteDeviceIsNotRegistered')
                
                toConnect = Session(master_dev_id, onsite_dev_id)
                for session in self._session_pool:
                    print(session == toConnect)
                    if session == toConnect:
                        raise Exception('DevicesAlreadyConnected')
                
                self._session_pool += [toConnect]
                #Set the onsite tunnel level to the one requested by the master
                mode = self._tundev_dict[master_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode()
                self._tundev_dict[onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.set_mode(mode)
                #Allow the client to obtain its vtun configuration
                self._tundev_dict[onsite_dev_id].vtunService.VtunAllowedSignal()
        
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='sss', out_signature='')
    def TunnelInterfaceStatusUpdate(self, device_id, iface_name, status):
        """ Update status (up/down) of a tunnel interface.
        \param device_id The device identifier
        \param iface_name The tunnel interface name
        \param status The status of the interface (up or down) 
        """
        try:
            self._tundev_dict[str(device_id)]
        except:
            raise Exception('Unknow device')
        
        if str(status).lower() != 'up' and str(status).lower() != 'down':
            raise Exception('InvalidInterfaceStatus')
        
        with self._tundev_dict_mutex:
            with self._session_pool_mutex:
                for session in self._session_pool:
                    previous_status = session.get_status()
                    session_tunnel_mode = None
                    if (self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3'  and 
                        self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3'):
                        session_tunnel_mode = 'L3'
                    elif (self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L2'  and 
                        self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L2'):
                        session_tunnel_mode = 'L2'
                    else:
                        session_tunnel_mode = 'invalid'
                    
                    logger.debug('Session tunnel mode is ' + str(session_tunnel_mode))
                    
                    if session.master_dev_id == device_id:
                        if status == 'up':
                            session.master_dev_iface = iface_name
                        if status == 'down':
                            session.master_dev_iface = None
                    if session.onsite_dev_id == device_id:
                        if status == 'up':
                            session.onsite_dev_iface = iface_name
                        if status == 'down':
                            session.onsite_dev_iface = None
                    logger.debug('DBusCall: TunnelInterfaceStatusUpdate -> ' + iface_name + ' to communicate with ' + device_id + ' is now ' + status)
                    #print('Previous status of session ' + str(session) + ': ' + previous_status)
                    #print('Current status of session ' + str(session) + ': ' + session.get_status())
                    if previous_status == 'in-progress' and session.get_status() == 'up':
                        #print('Making the glue for session ' + str(session))
                        if session_tunnel_mode == 'L3':
                            #Make the glue between tunnels here
                            #1 Check if the kernel is routing at IP level
                            p = subprocess.Popen('sysctl net.ipv4.ip_forward', shell=True, stdout=subprocess.PIPE) 
                            out = p.communicate()[0]
                            #out = subprocess.check_output('sysctl net.ipv4.ip_forward', shell=True)
                            routingEnabled = False
                            if str(out).split(' = ')[1] == '1':
                                routingEnabled = True
                            #2 If not, activate this feature
                            if not routingEnabled: #Routing not enabled in kernel
                                os.system('sysctl net.ipv4.ip_forward=1 > /dev/null 2>&1') #Enabling routing in kernel
                            #3 Add a rule to allow trafic from master interface to onsite interface
                            rule = 'iptables -A FORWARD -i <in> -o <out> -j ACCEPT'
                            os.system(rule.replace('<in>', str(session.master_dev_iface)).replace('<out>', str(session.onsite_dev_iface)))
                            #4 Add a rule to allow trafic from onsite interface to master interface
                            os.system(rule.replace('<in>', str(session.onsite_dev_iface)).replace('<out>', str(session.master_dev_iface)))
                            
                            #Make the route
                            commands = []
                            #from tun_to_rpi1100 to tun_to_rpi1101
                            gateway = str(self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_near_end_ip)
                            commandAddRoute = '/sbin/ip route add table 1 dev ' + str(session.onsite_dev_iface) + ' default via ' + gateway
                            commands += [commandAddRoute]
                            commandAddRule = '/sbin/ip rule add unicast iif ' + str(session.master_dev_iface) + ' table 1'
                            commands += [commandAddRule]
                            #from tun_to_rpi1101 to tun_to_rpi1100
                            gateway = str(self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_near_end_ip)
                            commandAddRoute = '/sbin/ip route add table 2 dev ' + str(session.master_dev_iface) + ' default via ' + gateway 
                            commands += [commandAddRoute]
                            commandAddRule = '/sbin/ip rule add unicast iif ' + str(session.onsite_dev_iface) + ' table 2'
                            commands += [commandAddRule]
                            for command in commands:
                                os.system(str(command))# + ' > /dev/null 2>&1')
                        if session_tunnel_mode == 'L2':
                            commandCreateBridge = '/sbin/brctl addbr br0'
                            commandAddUplinkIfaceToBridge = '/sbin/brctl addif br0 ' + str(session.onsite_dev_iface) 
                            commandAddTunnelIfaceToBridge = '/sbin/brctl addif br0 ' + str(session.master_dev_iface)
                            commandSetBridgeUp = '/sbin/ip link set br0 up'
                            os.system(commandCreateBridge)
                            os.system(commandAddUplinkIfaceToBridge)
                            os.system(commandAddTunnelIfaceToBridge)
                            os.system(commandSetBridgeUp)
                            
                            rule = 'iptables -A FORWARD -i br0 -j ACCEPT'
                            os.system(rule)
                            
                    if previous_status == 'up' and session.get_status() == 'in-progress':
                        #print('Breaking the glue for session ' + str(session))
                        master_dev_iface = session.master_dev_iface
                        onsite_dev_iface = session.onsite_dev_iface
                        if master_dev_iface is None:
                            master_dev_iface = iface_name
                        if onsite_dev_iface is None:
                            onsite_dev_iface = iface_name
                        if session_tunnel_mode == 'L3':
                            #Break the glue between the tunnels here
                            #1 Remove iptables rule to allow trafic from master interface to onsite interface
                            rule = 'iptables -D FORWARD -i <in> -o <out> -j ACCEPT  > /dev/null 2>&1'
                            
                            os.system(rule.replace('<in>', str(master_dev_iface)).replace('<out>', str(onsite_dev_iface)))
                            #2 Remove iptables rule to allow trafic from onsite interface to master interface
                            os.system(rule.replace('<in>', str(onsite_dev_iface)).replace('<out>', str(master_dev_iface)))
                            #3 If there is no more sessions, disable routing in kernel
                            disableRouting = True
                            for session in self._session_pool:
                                #print('Session ' + str(session) + ' status is ' + session.get_status())
                                if session.get_status() == 'up':
                                    disableRouting = False
                            if disableRouting:
                                #print('Disabling routing')
                                os.system('sysctl net.ipv4.ip_forward=0  > /dev/null 2>&1') #Disabling routing in kernel
                                
                            #Delete the route
                            #from tun_to_rpi1100 to tun_to_rpi1101
                            commands = []
                            gateway = str(self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_near_end_ip)
                            commandAddRoute = '/sbin/ip route del table 1 dev ' + str(onsite_dev_iface) + ' default via ' + gateway
                            commands += [commandAddRoute]
                            commandAddRule = '/sbin/ip rule del unicast iif ' + str(master_dev_iface) + ' table 1'
                            commands += [commandAddRule]
                            #from tun_to_rpi1101 to tun_to_rpi1100
                            gateway = str(self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_near_end_ip)
                            commandAddRoute = '/sbin/ip route del table 2 dev ' + str(master_dev_iface) + ' default via ' + gateway
                            commands += [commandAddRoute]
                            commandAddRule = '/sbin/ip rule del unicast iif ' + str(onsite_dev_iface) + ' table 2'
                            commands += [commandAddRule]
                            for command in commands:
                                os.system(str(command))# + ' > /dev/null 2>&1')
                        
                        if session_tunnel_mode == 'L2':
                            rule = 'iptables -D FORWARD -i br0 -j ACCEPT'
                            os.system(rule)
                            commandSetBridgeDown = '/sbin/ifconfig br0 down'
                            commandRemoveTunnelIfaceFromBridge = '/sbin/brctl delif br0 ' + str(master_dev_iface)
                            commandRemoveUplinkIfaceFromBridge = '/sbin/brctl delif br0 ' + str(onsite_dev_iface)
                            commandDeleteBridge = '/sbin/brctl delbr br0'
                            os.system(commandSetBridgeDown)
                            os.system(commandRemoveTunnelIfaceFromBridge)
                            os.system(commandRemoveUplinkIfaceFromBridge)
                            os.system(commandDeleteBridge)
                        
                        #When we lost one of the tunnels, we should stop the other tunnel too.
                        logger.debug(device_id + ' goes down, stopp vtun for other device')
                        if session.onsite_dev_id == device_id:
                            #The onsite fall, so we end the master as well
                            #print(device_id + 'is onsite, stopping master ' + session.master_dev_id)
                            self._tundev_dict[session.master_dev_id].vtunService.StopTunnelServer()
                            #print('...done')
                            
                        if session.master_dev_id == device_id:
                            #The master fall, so we end the onsite as well
                            #print(device_id + 'is master, stopping onsite ' + session.onsite_dev_id)
                            self._tundev_dict[session.onsite_dev_id].vtunService.StopTunnelServer()
                            #print('...done')
                            
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='', out_signature='as')
    def DumpSessions(self):
        """ Dump all TundevBindingDBusService objects registerd
        
        \return We will return an array of instanciated TundevBindingDBusService object paths
        """
                
        return map( lambda p: str(p), self._session_pool)
    
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='s', out_signature='as')
    def GetClientSideUpBlockCommands(self, username):
        """ List all command sthe should be put in the up block of this client vtun configuration file
        
        \return We will return an array of commands
        """
        
        try:
            self._tundev_dict[username]
        except:
            raise Exception('InvalidDeviceId')
        
        commands = []
        with self._tundev_dict_mutex:
            with self._session_pool_mutex:
                for session in self._session_pool:
                        if session.onsite_dev_id == username:
                            if self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3':
                                gateway = str(self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_far_end_ip)
                                commandAddRoute = '/sbin/ip "route add table 1 dev %% default via ' + gateway + '"'
                                commands += [commandAddRoute]
                                commandAddRule = '/sbin/ip "rule add unicast iif eth0 table 1"'
                                commands += [commandAddRule]
                                #We activate routing
                                commandActivateRouting = '/sbin/sysctl "net.ipv4.ip_forward=1"'
                                commands += [commandActivateRouting]
                                #Adding the nat rule for iptables
                                network = str(self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_ip_network)
                                commandMasquerade = '/sbin/iptables "-t nat -A POSTROUTING -o eth0 -j MASQUERADE"'
                                commands += [commandMasquerade]
                            elif self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L2':
                                commandCreateBridge = '/sbin/brctl "addbr br0"'
                                commands += [commandCreateBridge]
                                commandAddUplinkIfaceToBridge = '/sbin/brctl "addif br0 eth0"'
                                commands += [commandAddUplinkIfaceToBridge]
                                commandAddTunnelIfaceToBridge = '/sbin/brctl "addif br0 tap0"'
                                commands += [commandAddTunnelIfaceToBridge]
                                commandSetBridgeUp = '/sbin/ip "link set br0 up"'
                                commands += [commandSetBridgeUp]
                                
                            
                        elif session.master_dev_id == username:
                            if self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3':
                                #from eth0 to tun0
                                gateway = str(self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_far_end_ip)
                                commandAddRoute = '/sbin/ip "route add table 1 dev %% default via ' + gateway + '"'
                                commands += [commandAddRoute]
                                commandAddRule = '/sbin/ip "rule add unicast iif eth0 table 1"'
                                commands += [commandAddRule]
                                commandActivateRouting = '/sbin/sysctl "net.ipv4.ip_forward=1"'
                                commands += [commandActivateRouting]
                                #FIXME: will have to consider eth1 there and route from tun0 to eth1
                                #no need to do this with eth0 since it's configured by dhcp
                            elif self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L2':
                                commandCreateBridge = '/sbin/brctl "addbr br0"'
                                commands += [commandCreateBridge]
                                commandAddUplinkIfaceToBridge = '/sbin/brctl "addif br0 eth1"'
                                commands += [commandAddUplinkIfaceToBridge]
                                commandAddTunnelIfaceToBridge = '/sbin/brctl "addif br0 tap0"'
                                commands += [commandAddTunnelIfaceToBridge]
                                commandSetBridgeUp = '/sbin/ip "link set br0 up"'
                                commands += [commandSetBridgeUp]
                                
        return commands
    
    @dbus.service.method(dbus_interface = DBUS_SERVICE_INTERFACE, in_signature='s', out_signature='as')
    def GetClientSideDownBlockCommands(self, username):
        """ List all command sthe should be put in the down block of this client vtun configuration file
        
        \return We will return an array of commands
        """
        
        commands = []
        with self._tundev_dict_mutex:
            with self._session_pool_mutex:
                for session in self._session_pool:
                    if session.onsite_dev_id == username:
                        if self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3':
                            #Removing nat rule for iptables
                            network = str(self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_ip_network)
                            commandMasquerade = '/sbin/iptables "-t nat -D POSTROUTING -o eth0 -j MASQUERADE"'
                            commands += [commandMasquerade]
                            #We deactivate routing
                            commandDeactivateRouting = '/sbin/sysctl "net.ipv4.ip_forward=0"'
                            commands += [commandDeactivateRouting]
                            commandAddRule = '/sbin/ip "rule del unicast iif eth0 table 1"'
                            commands += [commandAddRule]
                            gateway = str(self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_far_end_ip)
                            commandAddRoute = '/sbin/ip "route del table 1 dev %% default via ' + gateway + '"'
                            commands += [commandAddRoute]
                        elif self._tundev_dict[session.onsite_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L2':
                            commandSetBridgeDown = '/sbin/ip "link set br0 down"'
                            commands += [commandSetBridgeDown]
                            commandRemoveTunnelIfaceFromBridge = '/sbin/brctl "delif br0 tap0"'
                            commands += [commandRemoveTunnelIfaceFromBridge]
                            commandRemoveUplinkIfaceFromBridge = '/sbin/brctl "delif br0 eth0"'
                            commands += [commandRemoveUplinkIfaceFromBridge]
                            commandUnloadModule = '/sbin/modprobe "-r bridge"'
                            commands += [commandUnloadModule]
                            commandLoadModule = '/sbin/modprobe "bridge"'
                            commands += [commandLoadModule]
                        
                    elif session.master_dev_id == username:
                        if self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L3':
                            #from eth0 to tun0
                            commandActivateRouting = '/sbin/sysctl "net.ipv4.ip_forward=0"'
                            commands += [commandActivateRouting]
                            commandAddRule = '/sbin/ip "rule del unicast iif eth0 table 1"'
                            commands += [commandAddRule]
                            gateway = str(self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_far_end_ip)
                            commandAddRoute = '/sbin/ip "route del table 1 dev %% default via ' + gateway + '"'
                            commands += [commandAddRoute]
                            #FIXME: will have to consider eth1 there and route from tun0 to eth1
                            #no need to do this with eth0 since it's configured by dhcp
                        elif self._tundev_dict[session.master_dev_id].vtunService.vtun_server_tunnel.tunnel_mode.get_mode() == 'L2':
                            commandSetBridgeDown = '/sbin/ip "link set br0 down"'
                            commands += [commandSetBridgeDown]
                            commandRemoveTunnelIfaceFromBridge = '/sbin/brctl "delif br0 tap0"'
                            commands += [commandRemoveTunnelIfaceFromBridge]
                            commandRemoveUplinkIfaceFromBridge = '/sbin/brctl "delif br0 eth1"'
                            commands += [commandRemoveUplinkIfaceFromBridge]
                            commandUnloadModule = '/sbin/modprobe "-r bridge"'
                            commands += [commandUnloadModule]
                            commandLoadModule = '/sbin/modprobe "bridge"'
                            commands += [commandLoadModule]
        return commands

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
    
    #Check the default policy for FORWARD table, if it is to ACCEPT, then we put it to DROP
    out = subprocess.check_output('iptables -L FORWARD | grep -Ei \'.*(policy\s.*)\' | grep -oEi \'(policy [A-Z]+)\'', shell=True)
    if out.replace('\n', '').split(' ')[1] == 'ACCEPT':
        os.system('iptables -P FORWARD DROP  > /dev/null 2>&1')
        setForwardPolicyToAcceptAtExit = True
        
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