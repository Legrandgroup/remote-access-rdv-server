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

class MasterDevShell(tundev_shell.TunnellingDevShell):
    """ Tundev CLI shell offered to an onsite dev """
    
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
        print('master')

    def do_set_tunnel_mode(self, args):
        """Set the current tunnel mode
        Valid modes are L2, L3, L3_multi
        """
        self.tunnel_mode = args

    def do_get_vtun_parameters(self, args):
        """Usage: get_vtun_parameters

Output the parameters of the vtun tunnel to connect to the RDV server
"""
        
        self._start_remote_vtun_server()
        print(self._vtun_config_to_str())

    def do_show_online_onsite_devs(self, args):
        """Usage: show_online_onsite_devs
        Lists all onsite devices connected
        """
        for dev in self._dbus_manager_iface.DumpTundevBindings():
            print(dev.replace(DBUS_OBJECT_ROOT + '/', ''))
            
    def do_connect_to_onsite_dev(self, id):
        """Usage: connect_to_onsite_dev_id {id}
        \param id The id of the onsite device to connect to.
        """
        self._assert_registered_to_manager()
        
        self._dbus_manager_iface.ConnectMasterDevToOnsiteDev(self.username, id)
        pass

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

    # lockfilename is passed to MasterDevShell's constructor. This file will be kept under a filesystem lock until this shell process is terminated
    lockfilename = '/var/lock/' + progname + '-' + str(os.getpid()) + '.lock'
    
    # Instanciate the shell
    master_dev_shell = MasterDevShell(username = username, logger = logger, lockfilename = lockfilename)
    
    atexit.register(cleanup_at_exit)  # function cleanup_at_exit() will make sure the lockfilename above is deleted when this process exists
    
    # Loop into the shell CLI parsing
    master_dev_shell.cmdloop()
    
    master_dev_shell = None # Destroy MasterDevShell instance
    
    cleanup_at_exit()
