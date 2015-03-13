#!/usr/bin/python

import paramiko
import cmd
import os
import sys

class ClientDevCli(cmd.Cmd):
    """ Tundevl CLI shell offered to client dev """

    username = str(os.getuid())
    prompt = username + '$ '

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.hosts = []
        self.connections = []

    def do_add_host(self, args):
        """add_host 
        Add the host to the host list"""
        if args:
            self.hosts.append(args.split(','))
        else:
            print "usage: host "

    def do_connect(self, args):
        """Connect to all hosts in the hosts list"""
        for host in self.hosts:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(
                paramiko.AutoAddPolicy())
            client.connect(host[0], 
                username=host[1], 
                password=host[2])
            self.connections.append(client)

    def do_run(self, command):
        """run 
        Execute this command on all hosts in the list"""
        if command:
            for host, conn in zip(self.hosts, self.connections):
                print 'Host: %s'  % (host[0])
                stdin, stdout, stderr = conn.exec_command(command)
                stdin.close()
                for line in stdout.read().splitlines():
                    print 'host: %s: %s' % (host[0], line)
        else:
            print "usage: run "

    def do_close(self, args):
        for conn in self.connections:
            conn.close()

    def do_exit(self, args):
        """exit
        Terminates this command-line session"""
        return True

    def do_logout(self, args):
        """logout
        Terminates this command-line session"""
        return True

    def do_EOF(self, args):
        """Send EOF (^D) to terminates this command-line session"""
        return True


if __name__ == '__main__':
    ClientDevCli().cmdloop()
