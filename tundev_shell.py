#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys

import threading

import gobject
import dbus
import dbus.mainloop.glib

import fcntl    # For lockf()

import logging

DBUS_NAME = 'com.legrandelectric.RemoteAccess.TundevManager'    # The name of bus we are creating in D-Bus
DBUS_OBJECT_ROOT = '/com/legrandelectric/RemoteAccess/TundevManager'    # The root under which we will create a D-Bus object with the username of the account for the tunnelling device for D-Bus communication, eg: /com/legrandelectric/RemoteAccess/TundevManager/1000 to communicate with a TundevBinding instance running for the UNIX account 1000 (/home/1000)
DBUS_SERVICE_INTERFACE = 'com.legrandelectric.RemoteAccess.TundevManager'    # The name of the D-Bus service under which we will perform input/output on D-Bus

class TunnellingDevShell(cmd.Cmd):
    """ Tundev CLI shell offered to tunnelling devices """

    def __init__(self, shell_user_name, logger, lockfilename = None):
        """ Constructor
        \param shell_user_name The user account we are using on the RDV server
        \param logger A logging.Logger to use for log messages
        \param lockfilename The lockfile to grabbed during the whole life duration of the shell
        """
        cmd.Cmd.__init__(self) # cmd is a Python old-style class so we cannot use super()
        
        self.tunnel_mode = 'L3' # By default, use L3 tunnel mode
        
        self.username = shell_user_name
        self.logger = logger
        
        self.prompt = self.username + '$ '
        
        self._vtun_server_tunnel = None # The vtun tunnel service
        
        self._dbus_loop = gobject.MainLoop()    # Get a reference to the mainloop
        self._bus = dbus.SystemBus()    # Get a reference to the D-Bus system bus
        dbus_manager_object = DBUS_OBJECT_ROOT
        self._dbus_manager_proxy = self._bus.get_object(DBUS_SERVICE_INTERFACE, dbus_manager_object)
        self._dbus_manager_iface = dbus.Interface(self._dbus_manager_proxy, DBUS_SERVICE_INTERFACE)
        
        self._tundevbinding_dbus_path = None
        self._dbus_binding_proxy = None
        self._dbus_binding_iface = None
        
        gobject.threads_init() # Allow the mainloop to run as an independent thread
        dbus.mainloop.glib.threads_init()
        
        self._dbus_loop_thread = threading.Thread(target = self._loopHandleDbus) # Start handling D-Bus messages in a background thread
        self._dbus_loop_thread.setDaemon(True) # D-Bus loop should be forced to terminate when main program exits
        self._dbus_loop_thread.start()
        self._bus.watch_name_owner(DBUS_NAME, self._handleBusOwnerChanged) # Install a callback to run when the bus owner changes
        
        if not lockfilename is None:
            self._shell_lockfilename = lockfilename
            self._shell_lockfile_fd = open(self._shell_lockfilename, 'w')
            try:
                self.logger.debug('Acquiring lock on ' + lockfilename)
                fcntl.flock(self._shell_lockfile_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                raise Exception('CannotGetLockfile')
            print(str(os.getpid()), file=self._shell_lockfile_fd)
            print(self.username, file=self._shell_lockfile_fd)
        
    # D-Bus related methods
    def _loopHandleDbus(self):
        """ This method should be run within a thread... This thread's aim is to run the Glib's main loop while the main thread does other actions in the meantime
        This methods will loop infinitely to receive and send D-Bus messages and will only stop looping when the Glib's main loop is stopped using .quit()
        """
        self.logger.debug("Starting dbus mainloop")
        self._dbus_loop.run()
        self.logger.debug("Stopping dbus mainloop")
        
    def _handleBusOwnerChanged(self, new_owner):
        """ Callback called when our D-Bus bus owner changes
        """
        if new_owner == '':
            self.logger.warn('Lost remote D-Bus manager process on bus name ' + DBUS_NAME)
            raise Exception('LostMasterProcess')
        else:
            pass # Owner exists
    
    def _get_vtun_shell_config(self):
        """ Retrieve from the remote TundevBindingDBusService, a tundev shell output string
        
        \return A list of strings containing in each entry, a line for the tundev shell output
        """
        
        self._assert_registered_to_manager()
        return self._dbus_binding_iface.GetAssociatedClientTundevShellConfig()
    
    def _register_to_manager(self):
        """ Register to the manager, we will then have a binding allocated for our shell on the manager
        
        Create a new D-Bus interface object to talk to the newly instanciated binding and store it into self._dbus_binding_iface
        """
        self._tundevbinding_dbus_path = self._dbus_manager_iface.RegisterTundevBinding(self.username, self.tunnel_mode, self._shell_lockfilename)
        # Now create a proxy and interface to be abled to communicate with this binding
        self.logger.debug('Registered to binding with D-Bus object path: "' + str(self._tundevbinding_dbus_path) + '"')
        self._dbus_binding_proxy = self._bus.get_object(DBUS_SERVICE_INTERFACE, self._tundevbinding_dbus_path)
        self._dbus_binding_iface = dbus.Interface(self._dbus_binding_proxy, DBUS_SERVICE_INTERFACE)

    def _is_registered_on_manager(self):
        """ Check if we already have a binding allocated to us on the manager
        
        \return True if there is a binding allocated to us on the manager 
        """
        return not self._tundevbinding_dbus_path is None
    
    def _assert_registered_to_manager(self):
        """ Make sure we have already a valid registration to the manager
        """
        if not self._is_registered_on_manager():
            self._register_to_manager()        

    def _stop_remote_vtun_server(self):
        """ Request the remote TunDevManager to stop the vtund server that handles the tunnelling for this tunnelling device
        
        Note: we will not do anything is there is no binding allocated to us on the manager
        """
        if self._is_registered_on_manager():    # Only request the stop if there is already a binding allocated to us
            self._dbus_binding_iface.StopTunnelServer()
    
    def _start_remote_vtun_server(self):
        """ Request the remote TunDevManager to start the vtund server that will perform tunnelling for this tunnelling device
        """
        self._assert_registered_to_manager()
        self._dbus_binding_iface.StartTunnelServer()
    
    # Shell commands
    def do_get_tunnel_mode(self, args):
        """Usage: get_tunnel_mode

Get the current tunnel mode"""
        if self.tunnel_mode is None:
            print('(unknown)')
        else:
            print(self.tunnel_mode)

    def do_echo(self, command):
        """Usage: echo {string}

Echo the string provided as parameter back to the console"""
        print(command)

    def do_drop_vtun(self, command):
        """Usage: drop_vtun

Asks the RDV server to drop the vtun tunnel to the tunnelling dev executing this command"""
        
        self._stop_remote_vtun_server()
         
    def do_exit(self, args):
        """Usage: exit

Terminates this command-line session"""
        return True

    def do_logout(self, args):
        """Usage: logout

Terminates this command-line session"""
        return self.do_exit(args)

    def do_EOF(self, args):
        """Send EOF (^D) to terminates this command-line session"""
        return self.do_exit(args)
    
    def _vtun_config_to_str(self):
        """ Dump the vtun parameters on the tunnelling dev side (client side of the tunnel)
        
        \return A multi-line config used for shell output
        """
        return '\n'.join(self._get_vtun_shell_config())


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True) # Use Glib's mainloop as the default loop for all subsequent code
