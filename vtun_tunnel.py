#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import ipaddr

class TunnelMode(object):
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
            raise Exception('InvalidTunnelMode:' + str(mode))
    
    def get_mode(self):
        return self._mode
        
    def __str__(self):
        return self.get_mode()

class VtunTunnel(object):
    """ Class representing a vtun tunnel """
    
    def __init__(self, **kwargs):
        """ Constructor for VtunTunnel class.
        Accepted kwargs are:
        tundev_shell_config is a string directly coming from the devshell command 'get_vtun_parameters', that will allow to set all the attributes of this object.
        Warning if tundev_shell_config is provided, no other argument below is allowed (or a 'SimultaneousConfigAndAgumentsNotAllowed' exception will be raised)
        mode is a string or a TunnelMode object representing the tunnel mode. Supported values are L2, L3 and L3_multi
        tunnel_ip_network string or an ipaddr.IPv4Network object containing the IP network range in use within the tunnel
        tunnel_near_end_ip string or an ipaddr.IPv4Address object containing our IP address inside the tunnel (near end of the tunnel)
        tunnel_far_end_ip string or an ipaddr.IPv4Address object containing  the IP address of the peer inside the tunnel (far end of the tunnel)
        vtun_server_tcp_port (optional, can be set to None if unknown) a string or an int describes the outer TCP port of the process handling the tunnel
        """
        self._vtun_pid = None    # The PID of the slave vtun process handling this tunnel
        self._vtun_process = None    # The python process object handling this tunnel
        
        arg_mode = kwargs.get('mode', None) # Type of tunnel (L2, L3 or L3_multi)
        arg_tunnel_ip_network = kwargs.get('tunnel_ip_network', None) # IP network (range) for the addressing within the tunnel
        arg_tunnel_near_end_ip = kwargs.get('tunnel_near_end_ip', None) # IP address of the near end of the tunnel (internal to the tunnel)
        arg_tunnel_far_end_ip = kwargs.get('tunnel_far_end_ip', None) # IP address of the far end of the tunnel (internal to the tunnel)
        arg_vtun_server_tcp_port = kwargs.get('vtun_server_tcp_port', None)   # TCP port on which to connect on the tunnel server machine

        arg_tundev_shell_config = kwargs.get('tundev_shell_config', None)  # Check if there is a tundev_shell_config argument
        if arg_tundev_shell_config:    # If so, we will generate set our attributes according to the config
            if not (arg_tunnel_ip_network is None and arg_tunnel_near_end_ip is None and arg_tunnel_far_end_ip is None and vtun_server_tcp_port is None):    # We also have a specific argument
                raise Exception('SimultaneousConfigAndAgumentsNotAllowed') 
            else:
                self.set_characteristics_from_string(arg_tundev_shell_config)
        else:
            self.set_characteristics(str(arg_mode), arg_tunnel_ip_network, arg_tunnel_near_end_ip, arg_tunnel_far_end_ip, arg_vtun_server_tcp_port)

    def set_characteristics(self, mode, tunnel_ip_network, tunnel_near_end_ip, tunnel_far_end_ip, vtun_server_tcp_port):
        """ Set this object tunnel parameters
        mode is a string or a TunnelMode object reprensenting the tunnel mode. Supported values are L2, L3 and L3_multi
        tunnel_ip_network string containing the IP network range in use within the tunnel
        tunnel_near_end_ip string containing our IP address inside the tunnel (near end of the tunnel)
        tunnel_far_end_ip string containing  the IP address of the peer inside the tunnel (far end of the tunnel)
        vtun_server_tcp_port (optional, can be set to None if unknown) describes the outer TCP port of the process handling the tunnel
        """
        if mode is None:
            raise Exception('TunnelModeCannotBeNone')
        
        self.tunnel_mode = TunnelMode(str(mode))
        self.tunnel_ip_network = ipaddr.IPv4Network(str(tunnel_ip_network))
        self.tunnel_near_end_ip = ipaddr.IPv4Address(str(tunnel_near_end_ip))
        self.tunnel_far_end_ip = ipaddr.IPv4Address(str(tunnel_far_end_ip))
        
        if vtun_server_tcp_port is None:
            self.vtun_server_tcp_port = None   # Undefined TCP ports are allowed, but we will need to specify the port before starting the tunnel!
        else:
            try:
                tcp_port = int(vtun_server_tcp_port)
            except ValueError:
                raise Exception('InvalidTcpPort:' + str(tcp_port))
            
            if tcp_port > 0 and tcp_port <= 65535:
                self.vtun_server_tcp_port = tcp_port
            else:
                raise Exception('InvalidTcpPort:' + str(tcp_port))

    def set_characteristics_from_string(self, tundev_shell_config):
        """ Set this object tunnel parameters from a string following the tundev shell output format of the command 'get_vtun_parameters'
        """
        raise Exception('NotYesImplemented')
    
    def is_valid(self):
        """ Check if our attributes are enough to define a vtun tunnel
        Returns True if all minimum attributes are set
        """
        if self.tunnel_mode is None:
            return False
        if self.tunnel_ip_network is None:
            return False
        if self.tunnel_near_end_ip is None:
            return False
        if self.tunnel_far_end_ip is None:
            return False
        # Note: vtun_server_tcp_port is not stricly required to define a valid the tunnel (but it will be to start it)
        return True
    
    def to_vtund_config(self):
        """ Generate a vtund config matching with the state of this object and return it as a string
        """
        pass    # 'virtual' method
        
    def start(self):
        if not (self._vtun_pid is None and self._vtun_process is None):    # There is already a slave vtun process running
            raise Exception('VtundAlreadyRunning')
        vtund_config = self.to_vtund_config()
        # Save into a file
        # Run the process on the file
        raise Exception('NotYetImplemented')
    
    def stop(self):
        # Check PID and subprocess
        # Kill them, remove the temporary config file
        raise Exception('NotYetImplemented')

class ServerVtunTunnel(VtunTunnel):
    """ Class representing a vtun tunnel service (listening) """
    def __init__(self, **kwargs): # See VtunTunnel.__init__ for the inherited kwargs
        super(ServerVtunTunnel, self).__init__(**kwargs)

class ClientVtunTunnel(VtunTunnel):
    """ Class representing a vtun tunnel client (connecting) """
    def __init__(self, **kwargs): # See VtunTunnel.__init__ for the inherited kwargs
        arg_from_server = kwargs.get('from_server', None) # Server from which we create a client config
        if arg_from_server is None:
            super(ClientVtunTunnel, self).__init__(**kwargs)
        else:   # We are building the client config to match a server config
            if not isinstance(arg_from_server, ServerVtunTunnel):
                raise Exception('WrongFromServerObject')
            super(ClientVtunTunnel, self).__init__(mode =  arg_from_server.tunnel_mode, tunnel_ip_network = arg_from_server.tunnel_ip_network, tunnel_near_end_ip = arg_from_server.tunnel_far_end_ip, tunnel_far_end_ip = arg_from_server.tunnel_near_end_ip, vtun_server_tcp_port = arg_from_server.vtun_server_tcp_port)
        self.vtun_server_hostname = kwargs.get('vtun_server_hostname', None)  # The remote host to connect to (if provided)
        # Note: in all cases, the caller will need to provide a vtun_server_hostname (it is not part of the ServerVtunTunnel object)
    
    def set_vtun_server_hostname(self, vtun_server_hostname):
        """ Set the remote host to connect to (this is mandatory after populating ClientVtunTunnel's attribute using from_server on ClientVtunTunnel's constructor
        vtun_server_hostname: the hostname or IP address of the vtund server
        """
        self.vtun_server_hostname = vtun_server_hostname
    
    def to_tundev_shell_output(self):
        # In shell output, we actually do not specify the vtun_server_hostname, because it is assumed to be tunnelled inside ssh (it is thus localhost)
        message = ''
        message += 'tunnel_ip_network: ' + str(self.tunnel_ip_network.network) + '\n'
        message += 'tunnel_ip_prefix: /' + str(self.tunnel_ip_network.prefixlen) + '\n'
        message += 'tunnel_ip_netmask: ' + str(self.tunnel_ip_network.netmask) + '\n'
        message += 'tunnelling_dev_ip_address: ' + str(self.tunnel_near_end_ip) + '\n'
        message += 'rdv_server_ip_address: ' + str(self.tunnel_far_end_ip) + '\n'
        if self.vtun_server_tcp_port is None:
            raise Exception('TcpPortCannotBeNone')
        else:
            message += 'rdv_server_vtun_tcp_port: ' + str(self.vtun_server_tcp_port)
        return message
        
    def is_valid(self): # Overload is_valid() for client tunnels... we also need a vtun_server_hostname and a vtun_server_tcp_port
        """ Check if our attributes are enough to define a vtun tunnel
        Returns True if all minimum attributes are set
        """
        if not super(ClientVtunTunnel, self).is_valid():    # First ask parent's is_valid()
            return False
        if self.vtun_server_hostname is None:
            return False
        return True
        
    
    def from_tundev_shell_output(self, input):
        raise Exception('NotYetImplemented')    # FIXME: to be implemented

