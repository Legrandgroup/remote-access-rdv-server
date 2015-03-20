#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys
#We depend on the PythonVtunLib from http://sirius.limousin.fr.grpleg.com/gitlab/ains/pythonvtunlib
from pythonvtunlib import vtun_tunnel

class TundevBinding(object):
    """ Class representing a tunnelling dev connected to the RDV server
    Among other, it will make sure the life cycle of the vtun tunnels are handled in a centralised way
    """
    
    def __init__(self, username, shell_alive_lock_fn = None):
        """ Create a new object to represent a tunnelling device from the vtun manager perspective
        \param username The username (account) of the tundev_shell that is object will be bound to
        \param shell_alive_lock_fn A filename on which the shell has grabbed an exclusive lock. The tundev_shell will keep this filesystem lock as long as it requires the vtun tunnel to be kept up.
        """
        self.username = username
        self.shell_lock_fn = shell_alive_lock_fn    # Fixme: start a thread that will try to grab this lock and perform tunnel cleanup if it does, or do it in configure_service()
        self.vtun_server_tunnel = None
        if self.username == '1000':    # For our (only) onsite RPI
            self.tundev_role = 'onsite'
        elif self.username == '1001':    # For our (only) master RPI
            self.tundev_role = 'master'
        else:
            raise Exception('UnknownTundevAccount:' + str(self.username))

    def configure_service(self, mode):
        """ Configure a tunnel server to handle connectivity with this tunnelling device
        
        \param mode A string or TunnelMode object describing the type of tunnel (L2, L3 etc...)
        """
        
        if self.tundev_role == 'onsite':    # For our (only) onsite RPI
            self.vtun_server_tunnel = vtun_tunnel.ServerVtunTunnel(mode = mode, tunnel_ip_network = '192.168.100.0/30', tunnel_near_end_ip = '192.168.100.1', tunnel_far_end_ip = '192.168.100.2', vtun_server_tcp_port = 5000)
            self.vtun_server_tunnel.restrict_server_to_iface('lo')
            self.vtun_server_tunnel.set_shared_secret(self.username)
            self.vtun_server_tunnel.set_tunnel_name('tundev' + self.username)
        elif self.tundsev_role == 'master':    # For our (only) master RPI
            self.vtun_server_tunnel = vtun_tunnel.ServerVtunTunnel(mode = mode, tunnel_ip_network = '192.168.101.0/30', tunnel_near_end_ip = '192.168.101.1', tunnel_far_end_ip = '192.168.101.2', vtun_server_tcp_port = 5001)
            self.vtun_server_tunnel.restrict_server_to_iface('lo')
            self.vtun_server_tunnel.set_shared_secret(self.username)
            self.vtun_server_tunnel.set_tunnel_name('tundev' + self.username)

    def start_vtun_server(self):
        """ Start a vtund server to handle connectivity with this tunnelling device
        """
        if not self.vtun_server_tunnel is None:
            print('Starting vtun server... on account ' + str(self.username) + ' (doing nothing)!')
            print('Config file for vtund would be "' + self.vtun_server_tunnel.to_vtund_config() + '"')
        else:
            raise Exception('VtunServerCannotBeStarted:NotConfigured')

    def stop_vtun_server(self):
        """ Stop the vtund server that is handling connectivity with this tunnelling device
        """
        if not self.vtun_server_tunnel is None:
            print('Stopping vtun server... on account ' + str(self.username) + ' (doing nothing)!')
        else:
            raise Exception('VtunServerCannotBeStopped:NotConfigured')

    def to_matching_client_tundev_shell_output(self):
        """ Output a tundev shell output string for a client tunnel matching with this configured vtun server
        
        This can directly be output in the tundev shell for the tunnelling device to know which client vtun configuration to apply
        
        \return A string containing tundev shell output string for the tundev shell command get_vtun_parameters
        """
        matching_client_tunnel = vtun_tunnel.ClientVtunTunnel(from_server = self.vtun_server_tunnel)
        # In shell output, we actually do not specify the vtun_server_hostname, because it is assumed to be tunnelled inside ssh (it is thus localhost)
        message = ''
        message += 'tunnel_ip_network: ' + str(matching_client_tunnel.tunnel_ip_network.network) + '\n'
        message += 'tunnel_ip_prefix: /' + str(matching_client_tunnel.tunnel_ip_network.prefixlen) + '\n'
        message += 'tunnel_ip_netmask: ' + str(matching_client_tunnel.tunnel_ip_network.netmask) + '\n'
        message += 'tunnelling_dev_ip_address: ' + str(matching_client_tunnel.tunnel_near_end_ip) + '\n'
        message += 'rdv_server_ip_address: ' + str(matching_client_tunnel.tunnel_far_end_ip) + '\n'
        if matching_client_tunnel.vtun_server_tcp_port is None:
            raise Exception('TcpPortCannotBeNone')
        else:
            message += 'rdv_server_vtun_tcp_port: ' + str(matching_client_tunnel.vtun_server_tcp_port)
        message += 'tunnel_secret: ' + str(matching_client_tunnel.tunnel_key) + '\n'
        return message

class TundevManager(object):
    """ Tunnelling device management class
    This class manages all tunnelling devices connected to the the RDV server
    Exchange of data between tundev shells and this manager are done via D-Bus
    """

    def __init__(self):
        self.tundev_dict = {}

    def register(self, username, shell_alive_lock_fn):
        """ Register a new tunnelling device to the TundevManager
        
        \param username Username of the account used by the tunnelling device
        \param shell_alive_lock_fn Filename of a flock()'ed file. The tundev shell should flock() this file and keep it this way, which proofs that the tundev shell is still alive. We will detect if the lock falls and assume the tundevl shell is not running anymore
        """
        # TODO: grab a mutex
        if username in self.tundev_dict:
            raise Exception('DuplicateTundevError') # FIXME: if this username is already known, clean up previous instance (tunnel etc...)
        
        self.tundev_dict[username] = TundevBinding(username, shell_alive_lock_fn)
    
    def request_new_tunnel(self, username, mode):
        """ Ask for a new vtun tunnel to serve the tundev shell specified by \p username
        
        \param username Username of the account used by the tunnelling device
        \mode A string or TunnelMode object describing the type of tunnel (L2, L3 etc...)
        
        \return We will return the newly instanciated TundevBinding
        """
        # FIXME: handle the case where there is no TundevInstance for this username
        self.tundev_dict[username].configure_service(mode)
        return self.tundev_dict[username]

