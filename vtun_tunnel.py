#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import ipaddr

class TunnelMode:
    def __init__(self, mode):
        """ Class constructor
        mode is a string reprensenting the tunnel mode. Supported values are L2, L3 and L3_multi
        """
        self.set_mode(mode)
    
    def set_mode(self, mode):
        """ Set the tunnel mode to mode. Supported values are L2, L3 and L3_multi
        """
        if mode == 'L2' or mode == 'L3' or mode == 'L3_multi':
            self._mode = mode
        else:
            raise Exception('Invalid tunnel mode')
    
    def get_mode(self, mode):
        return self._mode

class VtunTunnel:
    """ Class representing one vtun tunnel """
    
    def __init__(self, **kwargs):
        """ Constructor for VtunTunnel class.
        Accepted kwargs are:
        tundev_shell_config is a string directly coming from the devshell command 'get_vtun_parameters', that will allow to set all the attributes of this object.
        Warning if tundev_shell_config is provided, no other argument below is allowed (or a 'SimultaneousConfigAndAgumentsNotAllowed' exception will be raised)
        mode is a string reprensenting the tunnel mode. Supported values are L2, L3 and L3_multi
        internal_tunnel_ip_network describes the IP network range in use within the tunnel
        internal_tunnel_near_end_ip describes our IP address (near end of the tunnel)
        internal_tunnel_far_end_ip describes the IP address of the peer (far end of the tunnel)
        external_tunnel_remote_host (optional, can be set to None) describes the (outer) hostname or IP address of the peer machine to which we will establish the tunnel
        external_tunnel_tcp_port (optional, can be set to None) describes the outer TCP port of the process handling the tunnel
        """
        arg_mode = kwargs.get('mode', None) # Type of tunnel (L2, L3 or L3_multi)
        arg_internal_tunnel_ip_network = kwargs.get('internal_tunnel_ip_network', None) # IP network (range) for the adressing within the tunnel
        arg_internal_tunnel_near_end_ip = kwargs.get('internal_tunnel_near_end_ip', None) # IP address of the near end of the tunnel (internal to the tunnel)
        arg_internal_tunnel_far_end_ip = kwargs.get('internal_tunnel_far_end_ip', None) # IP address of the far end of the tunnel (internal to the tunnel)
        arg_external_tunnel_remote_host = kwargs.get('external_tunnel_remote_host', None) # Hostname or IP address of the remote machine to which we setup the tunnel
        arg_external_tunnel_tcp_port = kwargs.get('external_tunnel_tcp_port', None)   # TCP port on the remote machine external_tunnel_remote_host on which to setup the tunnel

        arg_tundev_shell_config = kwargs.get('tundev_shell_config', None)  # Check if there is a tundev_shell_config argument
        if arg_tundev_shell_config:    # If so, we will generate set our attributes according to the config
            if not (arg_internal_tunnel_ip_network is None and arg_internal_tunnel_near_end_ip is None and arg_internal_tunnel_far_end_ip is None and arg_external_tunnel_remote_host is None and arg_external_tunnel_tcp_port is None):    # We also have a specific argument
                raise Exception('SimultaneousConfigAndAgumentsNotAllowed') 
            else:
                self.set_tunnel_parameters_from_tundev_shell_config(arg_tundev_shell_config)
        
        self.set_tunnel_parameters(arg_mode, arg_internal_tunnel_ip_network, arg_internal_tunnel_near_end_ip, arg_internal_tunnel_far_end_ip, arg_external_tunnel_remote_host, arg_external_tunnel_tcp_port)

    def set_tunnel_parameters(self, mode, internal_tunnel_ip_network, internal_tunnel_near_end_ip, internal_tunnel_far_end_ip, external_tunnel_remote_host, external_tunnel_tcp_port):
        """ Set this object tunnel parameters
        mode is a string reprensenting the tunnel mode. Supported values are L2, L3 and L3_multi
        internal_tunnel_ip_network describes the IP network range in use within the tunnel
        internal_tunnel_near_end_ip describes our IP address (near end of the tunnel)
        internal_tunnel_far_end_ip describes the IP address of the peer (far end of the tunnel)
        external_tunnel_remote_host (optional, can be set to None) describes the (outer) hostname or IP address of the peer machine to which we will establish the tunnel
        external_tunnel_tcp_port (optional, can be set to None) describes the outer TCP port of the process handling the tunnel
        """
        self.tunnel_mode = TunnelMode(mode)
        self.vtun_internal_tunnel_ip_network = ipaddr.IPv4Network(internal_tunnel_ip_network)
        self.vtun_internal_tunnel_near_end_ip = ipaddr.IPv4Address(internal_tunnel_near_end_ip)
        self.vtun_internal_tunnel_far_end_ip = ipaddr.IPv4Address(internal_tunnel_far_end_ip)
        self.vtun_external_tunnel_remote_host = external_tunnel_remote_host
        
        if external_tunnel_tcp_port is None:
            self.vtun_external_tunnel_tcp_port = None   # Undefined TCP ports are allowed, but we will need to specify the port before starting the tunnel!
        else:
            try:
                tcp_port = int(external_tunnel_tcp_port)
            except ValueError:
                raise Exception('InvalidTcpPort')
            
            if tcp_port > 0 and tcp_port <= 65535:
                self.vtun_external_tunnel_tcp_port = tcp_port
            else:
                raise Exception('InvalidTcpPort')

    def set_tunnel_parameters_from_tundev_shell_config(self, tundev_shell_config):
        """ Set this object tunnel parameters from a string following the tundev shell output format of the command 'get_vtun_parameters'
        """
        raise Exception('NotSupported')
    
    def to_tundev_shell_output(self):
        # In shell output, we actually do not specify the remote hostname, because it is assumed to be tunnelled inside ssh (it is thus localhost)
        message = ''
        message += 'tunnel_ip_network: ' + str(self.vtun_internal_tunnel_ip_network.network) + '\n'
        message += 'tunnel_ip_prefix: /' + str(self.vtun_internal_tunnel_ip_network.prefixlen) + '\n'
        message += 'tunnel_ip_netmask: ' + str(self.vtun_internal_tunnel_ip_network.netmask) + '\n'
        message += 'tunnelling_dev_ip_address: ' + str(self.vtun_internal_tunnel_near_end_ip) + '\n'
        message += 'rdv_server_ip_address: ' + str(self.vtun_internal_tunnel_far_end_ip) + '\n'
        if self.vtun_external_tunnel_tcp_port is None:
            raise Exception('InvalidTcpPort')
        else:
            message += 'rdv_server_vtun_tcp_port: ' + str(self.vtun_external_tunnel_tcp_port)
        return message
        
    def from_tundev_shell_output(self, intput):
        pass    # FIXME: to be implemented