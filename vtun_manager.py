#!/usr/bin/python

# -*- coding: utf-8 -*-

from __future__ import print_function

import cmd
import os
import sys
#We depend on the PythonVtunLib from http://sirius.limousin.fr.grpleg.com/gitlab/ains/pythonvtunlib
from pythonvtunlib import vtun_tunnel

class VtunServerInstance(object):
    """ Class representing a vtun server running on the RDV server
    """
    
    def __init__(self, username):
        self.username = username
        self.vtun_tunnel = None

    def configure_service(self, mode):
        if self.username == '1000':    # For our (only) onsite RPI
            self.vtun_tunnel = vtun_tunnel.ServerVtunTunnel(mode = mode, tunnel_ip_network = '192.168.100.0/30', tunnel_near_end_ip = '192.168.100.1', tunnel_far_end_ip = '192.168.100.2', vtun_server_tcp_port = 5000)
        elif self.username == '1001':    # For our (only) master RPI
            self.vtun_tunnel = vtun_tunnel.ServerVtunTunnel(mode = mode, tunnel_ip_network = '192.168.101.0/30', tunnel_near_end_ip = '192.168.101.1', tunnel_far_end_ip = '192.168.101.2', vtun_server_tcp_port = 5001)
        else:
            raise Exception('UnknownTundevAccount:' + str(self.username))

    def start_server(self):
        print('Starting vtun server... doing nothing!')

    def to_matching_client_config_str(self):
        return vtun_tunnel.ClientVtunTunnel(from_server = self.vtun_tunnel).to_tundev_shell_output()

class VtunManager(object):
    """ vtun management class
    This class manages all instances of vtun servers running on the RDV server (creation/destructions) based on sollicitations from tundev shell processes
    Sollicitations from tundev shells are coming via D-Bus requests
    It will make sure the life cycle of the vtun tunnels are handled in a single place
    """

    def __init__(self):
        self._vtun_server_tunnel_list = []

    def request_new_tunnel(self, mode, username):
        """ Populate the attributes related to the tunnel configuration and store this into a newly instanciated self._vtun_server_tunnel """
        new_vtun_server_instance = VtunServerInstance(username)
        new_vtun_server_instance.configure_service(mode)
        self._vtun_server_tunnel_list.append(new_vtun_server_instance)
        return new_vtun_server_instance

