#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import os.path
import sys
import re
import ipaddr
import time

import tundev_shell

class ClientDevShell(tundev_shell.TunnellingDevShell):
    """ Tundev CLI shell offered to client dev """

    VTUN_READY_FNAME_PREFIX = "/var/run/vtun_ready-"
    
    def __init__(self, username):
        tundev_shell.TunnellingDevShell.__init__(self, username)
        self.lan_ip_address = None
        self.lan_ip_prefix = None
        self.uplink_type = None

    # Only for support
    #~ def do_set_tunnel_mode(self, args):
        #~ """Set the current tunnel mode
        #~ Valid modes are L2, L3, L3_multi
        #~ """
        #~ self._tunnel_mode = args

    def do_set_tunnelling_dev_lan_ip_address(self, args):
        """Usage: set_tunnelling_dev_lan_ip_address {address}

Publish the LAN IP address of the tunnelling dev
Argument address should contain the IP address and the CIDR prefix separated by a character '/'
eg: "192.168.1.2/24\""""
        try:
            ipv4=ipaddr.IPv4Network(args)
            self.lan_ip_address = ipv4.ip
            self.lan_ip_prefix = ipv4._prefixlen
        except ValueError:
            print('Invalid IP network: ' + args, file=sys.stderr)

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
        timeout = 60    # 60s
        vtun_check_fname = ClientDevShell.VTUN_READY_FNAME_PREFIX + self._username
        print('Checking "%s"' % (vtun_check_fname))
        while timeout>0:
            if os.path.isfile(vtun_check_fname):
                print('ready')
                return False
            else:
                time.sleep(1)
                timeout -= 1
        print('not_ready', file=sys.stderr)
    
    def do_get_vtun_parameters(self, args):
        self._generate_vtun_config()
        self._start_vtun()
        print(self._vtun_config_to_str())

if __name__ == '__main__':
    username = str(os.getuid())
    clientdev_shell = ClientDevShell(username)
    clientdev_shell.tunnel_mode = 'L3'	# FIXME: read from file (should be set by support dev shell)
    clientdev_shell.cmdloop()
