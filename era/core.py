'''
Created on Jul 7, 2015

@author: nguyenc
'''

from urllib2 import HTTPSHandler
import suds.transport.http
from suds.sudsobject import Property
from suds.client import Client
from suds.plugin import MessagePlugin
import logging
import ssl
from urlparse import urlparse
from datetime import datetime
import time


class Singleton(type):
    '''
    The singleton meta class.
    This is used to mark a class as a singleton. Examples of singleton classes
    are SessionMgr and TestParam.
    '''
    _instances = {}

    def __call__(self, *args, **kwargs):
        if 'instance' not in self.__dict__:
            self.instance = super(Singleton, self).__call__(*args, **kwargs)
        return self.instance


class HttpsTransport(suds.transport.http.HttpTransport):
    """A modified HttpTransport using an explicit SSL context.
    """

    def __init__(self, context, **kwargs):
        """Initialize the HTTPSTransport instance.
        :param context: The SSL context to use.
        :type context: :class:`ssl.SSLContext`
        :param kwargs: keyword arguments.
        :see: :class:`suds.transport.http.HttpTransport` for the
            keyword arguments.
        """
        suds.transport.http.HttpTransport.__init__(self, **kwargs)
        self.ssl_context = context
        self.verify = (context and context.verify_mode != ssl.CERT_NONE)

    def u2handlers(self):
        """Get a collection of urllib handlers.
        """
        handlers = suds.transport.http.HttpTransport.u2handlers(self)
        if self.ssl_context:
            try:
                handlers.append(HTTPSHandler(context=self.ssl_context,
                                             check_hostname=self.verify))
            except TypeError:
                # Python 2.7.9 HTTPSHandler does not accept the
                # check_hostname keyword argument.
                #
                # Note that even older Python versions would also
                # croak on the context keyword argument.  But these
                # old versions do not have SSLContext either, so we
                # will not end up here in the first place.
                handlers.append(HTTPSHandler(context=self.ssl_context))
        return handlers


class ValuePlugin(MessagePlugin):
    '''
    The value attribute of MapEntry is of generic type. This causes the View
    API server to throw invalid request since it expects a specific type,
    such as
    string, int, or boolean. This plugin adds a specific type to value
    attribute.

    Use set_value_Type(type) to set a specific type before calling the target
    api.
    '''

    def __init__(self):
        self.value_type = 'xsd:string'

    def set_value_type(self, val):
        '''
        Set the type of the value
        :param val: type of the value
        :return:
        '''
        self.value_type = val

    def add_value_type(self, node):
        '''
        Internal method
        :param node:
        :return:
        '''
        if node.name == 'value':
            if node.parent.name in ('updates', 'filter', 'filters', 'values'):
                ## only set type attribute if it does not exist
                if len(node.attributes) == 0:
                    node.set('xsi:type', self.value_type)

    def marshalled(self, context):
        '''
        Internal method
        :param context:
        :return:
        '''
        context.envelope.walk(self.add_value_type)


class NameSpacePlugin(MessagePlugin):
    '''
    While parsing the WSDL of View API, SUDS leaves out the xsd name space. This
    plugin re-adds xsd namespace.
    '''

    def marshalled(self, context):
        ## adding xsd namespace if missing
        if not 'xsd' in context.envelope.nsprefixes:
            context.envelope.nsprefixes[
                'xsd'] = 'http://www.w3.org/2001/XMLSchema'


class MOR():
    '''
    Creates a managed object reference, which is usually the first param when
    calling View API.
    '''

    @staticmethod
    def get_mor(mor_type):
        '''
        Fetch the VIM Managed Object Reference
        :param mor_type: The type of the object
        :return:
        '''
        mor = Property(mor_type)
        mor._type = mor_type
        return mor


class Suds(object):
    '''
    Wrapper for suds
    See https://bitbucket.org/jurko/suds
    '''

    ## turn off suds debug logs
    logging.getLogger('suds').setLevel(logging.INFO)

    ## set suds.transport level to DEBUG to log SOAP requests & responses
    logging.getLogger('suds.transport').setLevel(logging.INFO)
    logging.getLogger('suds.client').setLevel(logging.INFO)

    def __init__(self, wsdl, url):
        '''
        Constructor
        '''
        self.value_type = ValuePlugin()
        self.wsdl_file = wsdl
        self.url = url
        url_parse = urlparse(url)
        self.host = url_parse.netloc
        ctx = SslContext.get_context()
        tr = None
        if ctx:
            tr = HttpsTransport(ctx)
        self.client = Client(self.wsdl_file, location=self.url,
                             plugins=[self.value_type, NameSpacePlugin()],
                             timeout=180,
                             transport=tr)

    def get_svc(self):
        '''
        Fetch the service object, which wraps all available API exposed by
        this service
        :return:
        '''
        return self.client.service

    def get_object(self, object_type):
        '''
        Fetch a service object given its type
        :param object_type:
        :return:
        '''
        return self.client.factory.create(object_type)

    def set_value_type(self, v_type):
        '''
        Override the type of a member in the service request object, since suds
        sometimes can't figure out the exact type and will default to no type
        :param v_type:
        :return:
        '''
        self.value_type.set_value_type(v_type)


class SslContext():
    '''
    To create unverified context for SSL connection
    '''

    @staticmethod
    def get_context():
        '''
        Fetch an unverified context
        :return:
        '''
        ret = None
        if hasattr(ssl, '_create_unverified_context'):
            ctx_method = getattr(ssl, '_create_unverified_context')
            ret = ctx_method()
            logging.debug('using SSL unverified context')
        return ret

class Waiter():
    '''
    A convenience class to help repeating some tasks for sometime
    '''
    def __init__(self, max_wait_sec, delay_sec, message='Waiter'):
        '''

        :param max_wait_sec:
        :param delay_sec:
        :param message: a message to display while waiting
        '''
        self.max_wait_sec = max_wait_sec
        self.delay_sec = delay_sec
        logging.debug(message + ' - timeout=' + str(max_wait_sec) + 's delay='
                      + str(delay_sec) + 's')
        self.message = message
        self.elapsed = 0
        self.start = None
        self.stop = False

    def waiting(self):
        '''
        This should return True or False to indicate continuing or stopping
        :return:
        '''
        if self.stop:
            return False

        if not self.start:
            self.start = datetime.now()
        else:
            logging.debug(self.message + ' - waiting')
            time.sleep(self.delay_sec)

        self.elapsed = (datetime.now() - self.start).total_seconds()
        if self.elapsed > self.max_wait_sec:
            logging.debug(self.message + ' - timed out.')
            return False

        return True

    def stopping(self):
        self.stop = True

