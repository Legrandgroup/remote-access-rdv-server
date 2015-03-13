#!/usr/bin/python

import cmd
import os
import sys

class ClientDevShell(cmd.Cmd):
    """ Tundev CLI shell offered to client dev """

    username = str(os.getuid())
    prompt = username + '$ '

    def __init__(self):
        cmd.Cmd.__init__(self)

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

    def do_echo(self, command):
        """echo
        Echo the string provided as parameter"""
        print(command + '\n')

    def do_exit(self, args):
        """exit
        Terminates this command-line session"""
        self.do_close(None)
        return True

    def do_logout(self, args):
        """logout
        Terminates this command-line session"""
        return self.do_exit(args)

    def do_EOF(self, args):
        """Send EOF (^D) to terminates this command-line session"""
        return self.do_exit(args)


if __name__ == '__main__':
    ClientDevShell().cmdloop()
