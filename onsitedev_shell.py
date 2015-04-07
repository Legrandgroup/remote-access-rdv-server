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

    # Only for master dev=>move to masterdev_shell.py
    #~ def do_set_tunnel_mode(self, args):
        #~ """Set the current tunnel mode
        #~ Valid modes are L2, L3, L3_multi
        #~ """
        #~ self._tunnel_mode = args

    def do_set_tunnelling_dev_uplink_type(self, args):
        """Usage: set_tunnelling_dev_uplink_type {type}

Publish the type of uplink used by the tunnelling dev
Argument type is a string
eg: "lan\""""
        if args == 'lan' or args == '3g':
            self.uplink_type = args
        else:
            print('Unsupported uplink type: ' + args, file=sys.stderr)

    def do_wait_vtun_allowed(self, args):
        """Usage: wait_vtun_allowed

Wait until the RDV server is ready to accept a new vtun session.

Output the readiness status of the RDV server, possible return values are "ready", "not_ready"
"""
        # Lionel: FIXME: implement something better than a file polling, something like a flock maybe?
        # But we need to make sure that this type of event can be generated from commands in vtund's up block
        timeout = 60
        event =threading.Event()
        event.clear()
        
        def VtunAllowedHandler():
            print('Signal VtunAllowed received')
            event.set()
        
        obj = self._bus.get_object(DBUS_SERVICE_INTERFACE, DBUS_OBJECT_ROOT + str(self.username))
        obj.connect_to_signal("VtunAllowedSignal", VtunAllowedHandler,dbus_interface=DBUS_SERVICE_INTERFACE)
        
        event.wait(timeout)
        if not event.is_set():
            print('not_ready', file=sys.stderr)
        else:
            print('ready')
            return False
        #timeout = 60    # 60s
        #vtun_check_fname = OnsiteDevShell.VTUN_READY_FNAME_PREFIX + self.username
        #print('Checking "%s"' % (vtun_check_fname))
        #while timeout>0:
        #    if os.path.isfile(vtun_check_fname):
        #        print('ready')
        #        return False
        #    else:
        #        time.sleep(1)
        #        timeout -= 1
        #print('not_ready', file=sys.stderr)
    
    def do_get_vtun_parameters(self, args):
        """Usage: get_vtun_parameters

Output the parameters of the vtun tunnel to connect to the RDV server
"""
        
        self._start_remote_vtun_server()
        print(self._vtun_config_to_str())

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig()
    
    logger = logging.getLogger(__name__)
    
    logger.setLevel(logging.WARNING)    # In production mode
    
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(asctime)s %(name)s():%(lineno)d %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

    # Find out the user account we will handle
    username = getpass.getuser()
    
    logger.debug(progname + ': Starting on user account ' + username)

    # lockfilename is passed to OnsiteDevShell's constructor. This file will be kept under a filesystem lock until this shell process is terminated
    lockfilename = '/var/lock/' + progname + '-' + str(os.getpid()) + '.lock'
    
    # Instanciate the shell
    onsite_dev_shell = OnsiteDevShell(username = username, logger = logger, lockfilename = lockfilename)
    onsite_dev_shell.tunnel_mode = 'L3'	# FIXME: read from file (should be set by master dev shell)
    
    atexit.register(cleanup_at_exit)  # function cleanup_at_exit() will make sure the lockfilename above is deleted when this process exists
    
    # Loop into the shell CLI parsing
    onsite_dev_shell.cmdloop()
    
    onsite_dev_shell = None # Destroy OnsiteDevShell instance
    
    cleanup_at_exit()
