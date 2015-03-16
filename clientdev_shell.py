#!/usr/bin/python

import cmd
import os
import sys

import tundev_shell

class ClientDevShell(tundev_shell.TunnellingDevShell):
    """ Tundev CLI shell offered to client dev """

    def __init__(self):
        tundev_shell.TunnellingDevShell.__init__(self)

    # Only for support
    #~ def do_set_tunnel_mode(self, args):
        #~ """Set the current tunnel mode
        #~ Valid modes are L2, L3, L3_multi
        #~ """
        #~ self._tunnel_mode = args

    def do_client_stats(self, args):
        """ Display connection statistics"""
        print('Client stats')
        
if __name__ == '__main__':
    ClientDevShell().cmdloop()
