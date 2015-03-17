#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys
import vtun_tunnel

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
        if self._username == '1000':    # For our (only) client RPI
            self._vtun_server_tunnel = vtun_tunnel.ServerVtunTunnel(mode = self.tunnel_mode, internal_tunnel_ip_network = '192.168.100.0/30', internal_tunnel_near_end_ip = '192.168.100.1', internal_tunnel_far_end_ip = '192.168.100.2', external_tunnel_remote_host = 'RDV', external_tunnel_server_tcp_port = 5000)
        elif self._username == '1001':    # For our (only) support RPI
            self._vtun_server_tunnel = vtun_tunnel.ServerVtunTunnel(mode = self.tunnel_mode, internal_tunnel_ip_network = '192.168.101.0/30', internal_tunnel_near_end_ip = '192.168.101.1', internal_tunnel_far_end_ip = '192.168.101.2', external_tunnel_remote_host = 'RDV', external_tunnel_server_tcp_port = 5001)
        else:
            print('Unknown tunnelling device account "%s"... cannot generate vtun parameters' % (self._username), file=sys.stderr)

    def _has_valid_vtun_config(self):
        """ Check if we have an existing (not None) and valid self._vtun_server_tunnel attribute. Return True is so """
        if self._vtun_server_tunnel is None:
            return False
        if not self._vtun_server_tunnel.is_valid(): # Check if tunnel environment is sufficiently filled-in to start vtun
            return False
        return True

    def _start_vtun_server(self):
        """ Start the vtun service according to the remote tundev shell configuration """
        if not self._has_valid_vtun_config():
            raise Exception('VtunNotProperlyConfigured')
        else:
            pass    # TODO
    
    def _vtun_config_to_str(self):
        """ Dump the vtun parameters on the tunnelling dev side (client side of the tunnel) """
        if not self._has_valid_vtun_config():
            raise Exception('VtunNotProperlyConfigured')
        else:
            return vtun_tunnel.ClientVtunTunnel(from_server = self._vtun_server_tunnel).to_tundev_shell_output()
