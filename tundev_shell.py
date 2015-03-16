#!/usr/bin/python

import cmd
import os
import sys

class TunnellingDevShell(cmd.Cmd):
    """ Tundev CLI shell offered to tunnelling devices """

    username = str(os.getuid())
    prompt = username + '$ '

    def __init__(self):
        cmd.Cmd.__init__(self)
        self._tunnel_mode = 'L3'

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
        """Get the current tunnel mode"""
        if self._tunnel_mode is None:
            print('(unknown)')
        else:
            print self._tunnel_mode

    def do_echo(self, command):
        """Echo the string provided as parameter"""
        print(command + '\n')

    def do_exit(self, args):
        """Terminates this command-line session"""
        return True

    def do_logout(self, args):
        """Terminates this command-line session"""
        return self.do_exit(args)

    def do_EOF(self, args):
        """Send EOF (^D) to terminates this command-line session"""
        return self.do_exit(args)
