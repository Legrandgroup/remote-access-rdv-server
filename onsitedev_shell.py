#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import os.path
import sys
import re
import ipaddr
import time

import getpass

import cmd

import logging

import tundev_shell

import atexit

import threading

DBUS_OBJECT_ROOT = '/com/legrandelectric/RemoteAccess/TundevManager'    # The root under which we will create a D-Bus object with the username of the account for the tunnelling device for D-Bus communication, eg: /com/legrandelectric/RemoteAccess/TundevManager/1000 to communicate with a TundevBinding instance running for the UNIX account 1000 (/home/1000)
DBUS_SERVICE_INTERFACE = 'com.legrandelectric.RemoteAccess.TundevManager'    # The name of the D-Bus service under which we will perform input/output on D-Bus

progname = os.path.basename(sys.argv[0])
lockfilename = None

def cleanup_at_exit():
    """
    Called when this program is terminated, to release the lock
    """
    
    global lockfilename
    
    if lockfilename:
        os.remove(lockfilename)
        #print('Releasing lock file at exit', file=sys.stderr)   # For debug
        lockfilename = None

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

class OnsiteDevShell(tundev_shell.TunnellingDevShell):
    """ Tundev CLI shell offered to an onsite dev """

    VTUN_READY_FNAME_PREFIX = "/var/run/vtun_ready-"
    
    def __init__(self, username, logger, lockfilename):
        """ Constructor
        \param username The user account we are using on the RDV server
        \param logger A logging.Logger to use for log messages
        \param lockfilename The lockfile to grabbed during the whole life duration of the shell
        """
        tundev_shell.TunnellingDevShell.__init__(self, shell_user_name = username, logger = logger, lockfilename = lockfilename)    # Construct inherited TunnellingDevShell object
        
        self.uplink_type = None

    def do_get_role(self, args):
        """Usage: get_role

Returns the role of the user account running the current shell, which can be 'master' or 'onsite'"""
        print('onsite')

    def do_set_tunnelling_dev_uplink_type(self, args):
        """Usage: set_tunnelling_dev_uplink_type {type}

Publish the type of uplink used by the tunnelling dev
Argument type is a string
eg: "lan\""""
        if args == 'lan' or args == 'wlan' or args == '3g':
            self.uplink_type = args
        else:
            print('Unsupported uplink type: ' + args, file=sys.stderr)

    def do_wait_master_connection(self, args):
        """Usage: wait_vtun_allowed

Wait until the RDV server is ready to accept a new vtun session.

Output the readiness status of the RDV server, possible return values are "ready", "not_ready"
"""
        self._assert_registered_to_manager()
                
        timeout = 60
        event =threading.Event()
        event.clear()
        
        def VtunAllowedHandler():
            event.set()
        
        try:
            obj = self._bus.get_object(DBUS_SERVICE_INTERFACE, DBUS_OBJECT_ROOT + '/' + str(self.username))
            obj.connect_to_signal("VtunAllowedSignal", VtunAllowedHandler,dbus_interface=DBUS_SERVICE_INTERFACE)
        except dbus.DBusException:
            import traceback
            traceback.print_exc()
        
        event.wait(timeout)
        if not event.is_set():
            print('not_ready', file=sys.stderr)
        else:
            print('ready')
            return False
    
    def do_get_vtun_parameters(self, args):
        """Usage: get_vtun_parameters

Output the parameters of the vtun tunnel to connect to the RDV server
"""
        
        self._start_remote_vtun_server()
        print(self._vtun_config_to_str())

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig()

    progname = progname.split('.')[0]
    
    logger = logging.getLogger(progname)
    
    logger.setLevel(logging.WARNING)    # In production mode
    
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(asctime)s %(name)s():%(lineno)d %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

    # Find out the user account we will handle
    username = getpass.getuser()
    
    logger.debug('Starting onsitedev shell for user account ' + username)

    # lockfilename is passed to OnsiteDevShell's constructor. This file will be kept under a filesystem lock until this shell process is terminated
    lockfilename = '/var/lock/' + progname + '-' + str(os.getpid()) + '.lock'
    
    # Instanciate the shell
    onsite_dev_shell = OnsiteDevShell(username = username, logger = logger, lockfilename = lockfilename)
    onsite_dev_shell.tunnel_mode = 'L3'	# FIXME: Whatever we set here is not used (tunnel mode is set by master dev shell)
    
    atexit.register(cleanup_at_exit)  # Function cleanup_at_exit() will make sure the lockfilename above is deleted when this process exists
    
    # Loop into the shell CLI parsing
    onsite_dev_shell.cmdloop()
    
    onsite_dev_shell = None # Destroy OnsiteDevShell instance
    
    cleanup_at_exit()
