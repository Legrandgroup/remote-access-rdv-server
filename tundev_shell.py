#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys
import vtun_manager

class TunnellingDevShell(cmd.Cmd):
    """ Tundev CLI shell offered to tunnelling devices """

    def __init__(self, shell_user_name):
        cmd.Cmd.__init__(self) # cmd is a Python old-style class so we cannot use super()
        self.tunnel_mode = 'L3'
        self._username = shell_user_name
        self.prompt = self._username + '$ '
        
        self._vtun_server_tunnel = None # The vtun tunnel service

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

    def _prepare_server_vtun_env(self):
        """ Populate the attributes related to the tunnel configuration and store this into a newly instanciated self._vtun_server_tunnel """
        self._vtun_server_tunnel = vtun_manager.VtunManager().request_new_tunnel(self.tunnel_mode, self._username)

    def _start_vtun_server(self):
        """ Start the vtun service according to the remote tundev shell configuration """
        if not self._vtun_server_tunnel is None:
            self._vtun_server_tunnel.start_server()
        else:
            raise Exception('VtunNotProperlyConfigured')
    
    def _vtun_config_to_str(self):
        """ Dump the vtun parameters on the tunnelling dev side (client side of the tunnel) """
        if not self._vtun_server_tunnel is None:
            return self._vtun_server_tunnel.to_matching_client_config_str()
        else:
            raise Exception('VtunNotProperlyConfigured')
