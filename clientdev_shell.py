#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys
import re
import ipaddr

import tundev_shell

class ClientDevShell(tundev_shell.TunnellingDevShell):
    """ Tundev CLI shell offered to client dev """

    def __init__(self, username):
        tundev_shell.TunnellingDevShell.__init__(self, username)
        self.lan_ip_address = None
        self.lan_ip_prefix = None

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
eg: 192.168.1.2/24"""
        try:
            ipv4=ipaddr.IPv4Network(args)
            self.lan_ip_address = ipv4.ip
            self.lan_ip_prefix = ipv4._prefixlen
        except ValueError:
            print('Invalid IP network: ' + args, file=sys.stderr)

if __name__ == '__main__':
    username = str(os.getuid())
    clientdev_shell = ClientDevShell(username)
    clientdev_shell.tunnel_mode = 'L3'	# FIXME: read from file (should be set by support dev shell)
    clientdev_shell.cmdloop()
