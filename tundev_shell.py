#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys
import ipaddr

class TunnellingDevShell(cmd.Cmd):
    """ Tundev CLI shell offered to tunnelling devices """

    def __init__(self, shell_user_name):
        cmd.Cmd.__init__(self)
        self.tunnel_mode = 'L3'
        self._username = shell_user_name
        self.prompt = self._username + '$ '
        
        self._vtun_tunnel_ip_network = None
        self._vtun_tunnelling_dev_ip = None
        self._vtun_rdv_server_ip = None
        self._vtun_rdv_server_tcp_port = None
    
    #~ def do_connect(self, args):
        #~ """Connect to all hosts in the hosts list"""
        #~ self._ssh_connection = paramiko.SSHClient()
        #~ self._ssh_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #~ self._ssh_connection.connect(self._rdv_server, username='pi', password='raspberry')

    #~ def do_run(self, command):
        #~ """run
        #~ Execute this command on the remote server"""
        #~ if command:
            #~ if self._ssh_connection:
                #~ print 'Host: %s'  % (self._rdv_server)
                #~ stdin, stdout, stderr = self._ssh_connection.exec_command(command)
                #~ stdin.close()
                #~ for line in stdout.read().splitlines():
                    #~ print 'host: %s: %s' % (self._rdv_server, line)
        #~ else:
            #~ print "usage: run "

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
        print(command + '\n')

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

    def _generate_vtun_config(self):
        """ Populate the attribute related to the vtun tunnel of this object """
        if self._username == '1000':    # For our (only) client RPI
            self._vtun_tunnel_ip_network = ipaddr.IPv4Network('192.168.100.0/30')
            self._vtun_tunnelling_dev_ip = ipaddr.IPv4Address('192.168.100.2')
            self._vtun_rdv_server_ip = ipaddr.IPv4Address('192.168.100.1')
            self._vtun_rdv_server_tcp_port = 5000
        elif self._username == '1001':    # For our (only) support RPI
            self._vtun_tunnel_ip_network = ipaddr.IPv4Address('192.168.101.0/30')
            self._vtun_tunnelling_dev_ip = ipaddr.IPv4Address('192.168.101.2')
            self._vtun_rdv_server_ip = ipaddr.IPv4Address('192.168.101.1')
            self._vtun_rdv_server_tcp_port = 5001
        else:
            print('Unknown tunnelling device account "%s"... cannot generate vtun parameters' % (self._username), file=sys.stderr)

    def _has_valid_vtun_config(self):
        if self._vtun_tunnel_ip_network is None or self._vtun_tunnelling_dev_ip is None or self._vtun_rdv_server_ip is None or self._vtun_rdv_server_tcp_port is None:
            return False
        return True

    def _start_vtun(self):
        """ Start the vtun service according to the remote tundev shell configuration """
        if not self._has_valid_vtun_config():
            print('Cannot start rdv server side vtun. vtun is not fully configured', file=sys.stderr)
        else:
            pass
    
    def _vtun_config_to_str(self):
        message = ''
        message += 'tunnel_ip_network: ' + str(self._vtun_tunnel_ip_network.network) + '\n'
        message += 'tunnel_ip_prefix: /' + str(self._vtun_tunnel_ip_network.prefixlen) + '\n'
        message += 'tunnel_ip_netmask: ' + str(self._vtun_tunnel_ip_network.netmask) + '\n'
        message += 'tunnelling_dev_ip_address: ' + str(self._vtun_tunnelling_dev_ip) + '\n'
        message += 'rdv_server_ip_address: ' + str(self._vtun_rdv_server_ip) + '\n'
        message += 'rdv_server_vtun_tcp_port: ' + str(self._vtun_rdv_server_tcp_port)
        return message