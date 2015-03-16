#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys

class TunnellingDevShell(cmd.Cmd):
    """ Tundev CLI shell offered to tunnelling devices """

    def __init__(self, shell_user_name):
        cmd.Cmd.__init__(self)
        self.tunnel_mode = 'L3'
        self._username = shell_user_name
        self.prompt = self._username + '$ '

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
