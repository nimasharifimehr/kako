import time
import boto3
import socket
import logging
import SocketServer

from kako import messaging
from kako.simulation.server import error


class RequestHandler(SocketServer.BaseRequestHandler):
    ''' Implements TCP handling for client connections. '''
    simulation = 'UNKNOWN'

    def __init__(self, request, client_address, server):
        ''' Bolt on a logger to push messages back to Kako. '''
        self.log = logging.getLogger()
        self.buffer = []
        self.record = []

        # Setup an AWS SNS client for publishing captures.
        self.sns = boto3.client(
            'sns', region_name=server.configuration['results']['region']
        )

        # Finish initialization using the parent class.
        SocketServer.BaseRequestHandler.__init__(
            self, request, client_address, server
        )

    def write(self, message):
        ''' Writes to the socket. '''
        self.request.sendall(message)

    def read(self, length, record=True):
        ''' Reads from the socket into the record and build a byte-array. '''
        raw = self.request.recv(length)
        if raw == '':
            raise error.ClientDisconnect()

        # If requested, save the read data into the record buffer, and stuff
        # it into the read buffer eitherway.
        if record:
            self.record.append(raw.strip())
        self.buffer = map(ord, list(raw))

    def capture(self):
        ''' Implements 'capture' functionality for identified requests. '''
        msg = messaging.capture.Capture(
            ts=int(time.time()),
            node=socket.gethostname(),
            cap=self.record,
            src_ip=self.client_address[0],
            src_port=self.client_address[1],
            sim_name=self.simulation,
            sim_version=self.simulation_version
        )

        # Publish to SNS.
        self.log.info('Publishing results from interaction to SNS.')
        self.sns.publish(
            TopicArn=self.server.configuration['results']['topic'],
            Message=msg.toJSON()
        )


class Server(SocketServer.ThreadingTCPServer):
    ''' Extends SocketServer ThreadingTCPServer to provide configuration. '''

    def __init__(self, server_address, RequestHandlerClass, configuration):
        SocketServer.ThreadingTCPServer.__init__(
            self, server_address, RequestHandlerClass
        )
        self.configuration = configuration
