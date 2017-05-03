import httplib
import json
import os.path
import ssl
import sys
from contextlib import closing
import time
import abc
from abc import ABCMeta
import logging
import atexit
import requests
import re
import urllib
import  shutil

from core import Singleton
from util import Timings
from util import String
from util import Validation
from util import pingServer


class Http(object):
    '''
    HTTP helper.
    This helper provides the methods for basic HTTP operations such as GET/POST
    and streaming files.
    '''

    def __init__(self, address, port, max_retry=None, **kwargs):
        self.__address = address.strip()
        self.__port = port
        self.max_retry = max_retry or Timings().get_max_retry_attempt_4()

    def __repr__(self):
        return self.__address + ':' + str(self.__port)

    def post(self, url, use_ssl=False, headers=None, delay=None, out_file=None):
        '''
        Send a POST
        @param url: the target URL
        '''
        return self.__request(url, 'POST', use_ssl=use_ssl, headers=headers,
                              delay=delay,
                              out_file=out_file)

    def delete(self, url, use_ssl=False, headers=None, delay=None):
        '''
        Send a POST
        @param url: the target URL
        '''
        return self.__request(url, 'DELETE', use_ssl=use_ssl, headers=headers,
                              delay=delay)

    def post_data(self, url, data, use_ssl=False, headers=None, delay=None,
                  out_file=None, plain_text=False):
        '''
        Send a POST
        @param url: the target URL
        '''
        return self.__request(url, 'POST', data=data, use_ssl=use_ssl,
                              headers=headers, delay=delay, out_file=out_file,
                              plain_text=plain_text)

    def put_data(self, url, data, use_ssl=False, headers=None, delay=None):
        '''
        Send a POST
        @param url: the target URL
        '''
        return self.__request(url, 'PUT', data=data, use_ssl=use_ssl,
                              headers=headers, delay=delay)

    def post_and_stream(self, url, stream_file, delay=None):
        '''
        Stream a file to given URL
        @param url: the target URL
        @param stream_file: the file to be streamed
        '''
        msg = self.__address + ': streaming ' + stream_file + ' to ' + url
        logging.debug(msg)
        retries = 0
        while True:
            try:
                with closing(httplib.HTTPConnection(self.__address,
                                                    self.__port)) as conn:
                    conn.connect()
                    conn.putrequest('POST', url)
                    conn.putheader('Content-Type',
                                   'application/octet-stream, '
                                   'text/javascript, */*; q=0.01')

                    total_size = os.path.getsize(stream_file)
                    installer_dat = open(stream_file, 'rb')

                    conn.putheader('Content-Length', str(total_size))
                    conn.endheaders()

                    while True:
                        chunk = installer_dat.read(65536)
                        if not chunk:
                            break
                        conn.send(chunk)
                    resp = conn.getresponse()

                    if resp.status == 200:
                        logging.debug(msg + ': result = OK')
                        return
                    else:
                        logging.debug(msg + ': error = ' + str(resp.status))
            except:
                if retries < self.max_retry:
                    retries += 1
                    logging.debug(msg + ' attempt ' + str(retries) + '/'
                                  + str(self.max_retry))
                    time.sleep(delay or
                               Timings().get_task_wait_interval_sec_3())
                else:
                    logging.debug(msg + ' failed, error ' + sys.exc_info()[0])
                    raise

    def get(self, url, cookie=None, use_ssl=False, headers=None, delay=None,
            out_file=None, plain_text=False):
        '''
        Send a GET
        @param url: the target URL
        @param delay: delay in s between retries
        '''
        return self.__request(url, 'GET', cookie=cookie, use_ssl=use_ssl,
                              headers=headers, delay=delay, out_file=out_file,
                              plain_text=plain_text)

    def get_json(self, url, cookie=None, delay=None):
        '''
        Fetch given URL as a JSON string
        @param url: the target URL
        '''
        return json.loads(
            self.__request(url, 'GET', cookie=cookie, delay=delay))

    def process_request(self, conn, url, method, cookie=None, data=None,
                        headers=None,
                        out_file=None,
                        plain_text=False):
        if data:
            if plain_text:
                _headers = {'Content-type': 'text/plain'}
            else:
                _headers = {'Content-type': 'application/json'}
        elif cookie:
            _headers = {'Cookie': cookie, 'Content-type': 'application/json'}
        else:
            _headers = {'Content-length': '0'}

        if headers:
            logging.debug('headers = ' + String.to_string(headers))
            _headers.update(headers)

        if data:
            logging.debug('data = ' + String.to_string(data))

        if data:
            conn.request(method, url, body=data, headers=_headers)
        else:
            conn.request(method, url, headers=_headers)

        conn.sock.settimeout(15)
        resp = conn.getresponse()
        logging.debug('response = ' + str(resp.status))
        if resp.status == 200:
            logging.debug(url + ' --> OK')

            if resp.fp and out_file:
                logging.debug('writing attachment to file ' + out_file)
                file_content=resp.read()
                with open(out_file, 'wb') as f:
                    f.write(file_content)

                return out_file

            r = resp.read()
            if hasattr(resp, 'msg'):
                if hasattr(resp.msg, 'dict'):
                    if 'set-cookie' in resp.msg.dict:
                        rd = json.loads(r)
                        rd['cookie'] = resp.msg.dict['set-cookie']
                        return str(rd)
                    if 'authorization' in resp.msg.dict:
                        rd = {'authorization': resp.msg.dict['authorization'],
                              'x-dt-csrf-header': resp.msg.dict[
                                  'x-dt-csrf-header']}
                        return rd

            return r
        elif resp.status == 401:
            return 'error: unauthorized'
        elif resp.status == 201:
            return 'created'
        elif resp.status == 500:
            return 'error: ' + String.to_string(resp.msg.headers)
        else:
            raise Exception(self.__address + ' '
                            + method + ' ' + url
                            + ' error ' + str(resp.status))

    def __request(self, url, method, use_ssl=False, cookie=None, data=None,
                  headers=None, delay=None,
                  out_file=None, plain_text=False):
        '''
        The common request method
        @param url: the target URL
        @param method: type of web method (GET,POST)
        @param delay: the delay in seconds between retries
        '''
        msg = self.__address + ': ' + method.upper() + ' ' + url
        logging.debug(msg)
        retries = 0

        while True:
            try:
                if use_ssl:
                    ## try to set sslContext for python 2.7.9+
                    ## see https://docs.python.org/2/library/httplib.html
                    try:
                        sslContext = ssl.create_default_context()
                        sslContext.check_hostname = False
                        sslContext.verify_mode = ssl.CERT_NONE
                        with closing(httplib.HTTPSConnection(self.__address,
                                                             self.__port,
                                                             context=sslContext)) as conn:
                            return self.process_request(conn, url, method,
                                                        cookie,
                                                        data, headers,
                                                        out_file=out_file,
                                                        plain_text=plain_text)
                    except:
                        ssl._create_default_https_context = \
                            ssl._create_unverified_context
                        with closing(httplib.HTTPSConnection(self.__address,
                                                             self.__port)) as \
                                conn:
                            return self.process_request(conn, url, method,
                                                        cookie,
                                                        data, headers,
                                                        out_file=out_file,
                                                        plain_text=plain_text)
                else:
                    with closing(httplib.HTTPConnection(self.__address,
                                                        self.__port)) as conn:
                        return self.process_request(conn, url, method, cookie,
                                                    data, headers,
                                                    out_file=out_file,
                                                    plain_text=plain_text)

            except Exception, ex:
                if hasattr(ex, 'message') and ex.message:
                    logging.debug(ex.message)
                if retries < self.max_retry:
                    retries += 1
                    logging.debug(msg + ' attempt ' + str(retries) + '/'
                                  + str(self.max_retry))
                    time.sleep(delay or
                               Timings().get_task_wait_interval_sec_3())
                else:
                    logging.debug(msg + ' failed, error: ' + ex.message)
                    raise

    def is_ok(self, url):
        '''
        determine if the target server is responding to requests
        @param url: target URL
        '''
        with closing(httplib.HTTPConnection(self.__address,
                                            self.__port,
                                            timeout=1)) as conn:
            try:
                conn.request('GET', url)
                return conn.getresponse().status == 200
            except:
                return False


class ISession(object):
    __metaclass__ = ABCMeta
    '''
    Session interface

    This interface should be implemented by all helper classes which need
    to authenticate to the REST/SOAP servers and to have their
    sessions maintained by the SessionMgr. Examples include VSphereHelper and
    WemHelper.
    '''
    skip_login = False
    @abc.abstractmethod
    def get_session_key(self):
        '''
        This is the key to use for fetching or storing an instance of the
        implementation. This key should be in the form of

        [service type]|[target service host]|[user to login]

        E.g.: VIM|VC1|administrator@vpshere.local
        '''
        return

    @abc.abstractmethod
    def is_logged_in(self):
        '''
        This is used to determine if there is any existing active session to
        re-use. This is called first while retrieving a session so that
        we always use existing sessions if they exist.
        '''
        return

    @abc.abstractmethod
    def login(self):
        '''
        Login to the REST/SOAP services that require authentication such as
        VIM/View/WEM. Some services such as the ERA agent REST service doesn't
        require authentication, and they don't need to implement ISession.
        '''
        return

    @abc.abstractmethod
    def logout(self):
        '''
        This is used to log off current active session. This should be called
        by the consumer to clean up their sessions.
        '''
        return

    def __getattribute__(self, name):
        '''
        Intercept to check and relogin if necessary
        :param name:
        :return:
        '''
        attr = object.__getattribute__(self, name)

        if hasattr(attr, '__call__') and \
                        name not in \
                        ['get_session_key','is_logged_in','login','logout',
                         'get_connection_params',
                         'get_settings',
                         'wait_av',
                         'init_av_session',
                         'set_skip_login']\
                and not name.startswith('_')\
                and not self.skip_login:

            def w(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except:
                    # see if we are still logged in, if not login then invoke
                    # the call again
                    if not self.is_logged_in():
                        self.login()
                        return attr(*args, **kwargs)
                    else:
                        raise

            return w
        else:
            return attr


class SessionMgr(object):
    __metaclass__ = Singleton
    '''
    This class manages sessions for REST/SOAP services that require
    authentication
    before calling their APIs. Example services include WEM/View/VIM. Some
    services don't require authentication such as the ERA REST agent service and
    they don't need to go through this class, since there is no session to
    maintain. This is a singleton class and guarantees there is only one
    instance at any moment. This single instance nature enables a single active
    session for each user per service host per service type.
    '''

    def __init__(self):
        '''
        Constructor
        '''
        self.sessions = {}

    def get_session(self, imp):
        '''
        This is used to fetch an existing or establishing a new session. The
        caller should pass an implementation of ISession, which contains a key
        in the format 'service type'|'service host'|'API user'.
        @param imp:
        '''
        session = None
        if imp.get_session_key() in self.sessions:
            s = self.sessions[imp.get_session_key()]
            try:
                if s.is_logged_in():
                    logging.debug(imp.get_session_key() + ': Reusing session')
                    session = s
            except:
                logging.debug(imp.get_session_key()
                              + ": Failed to reuse existing session")

        if not session:
            imp.login()
            self.sessions[imp.get_session_key()] = imp
            session = imp

        return session


    def logout_all_sessions(self):
        '''
        This should be used to clean up all sessions prior to terminating the
        test. This will go through all existing sessions being maintained
        in this session manager and call their logoffs.
        '''
        for session_key, session in self.sessions.iteritems():
            logging.debug(session_key + ': Logging off')
            session.logout()


    @staticmethod
    @atexit.register
    def log_offs():
        SessionMgr().logout_all_sessions()

class Web(object):
    @staticmethod
    def get_ova_url(buildnumber):
        '''
        This function uses a REST api call to fetch the weblink for  OVA
        given a buildnumber.
        @param buildnumber : build number to fetch to the deliverable
        '''

        logging.info("Fetching the OVA url using builweb rest api")

        # rest api to get the deliverable
        url = "/ob/deliverable/?build=" + buildnumber

        # creating an http object to make a get call
        http_obj = Http("buildapi.eng.vmware.com", 80)
        result = Http.get_json(http_obj, url)

        # Iterate through the result to find .ova url
        deliverables = result['_list']
        for d in deliverables:
            if ".ova" in d['_download_url']:
                ova_url = d['_download_url']
                ova = "http://build-squid.eng.vmware.com/build/mts/release/bora" \
                      "-" + \
                      buildnumber + "/publish/%s" % ova_url.split('/')[-1]
                return ova

        # if .ova is not found, raise an exception. Test case fails.
        raise Exception("Unable to locate OVA. Please check the build number.")

    @staticmethod
    def verify_ap_is_up(ip):
        '''
        This function verifies if static IP is acquired by the AP VM. It also
        looks if swagger-ui is up and running
        :param ip: Static IP for AP VM
        :return: True is both checks pass. Or raises Exception
        '''
        start_time = time.time()

        logging.info("Verifying if VM can be pinged.. ")

        if pingServer(ip) != 0:
            raise Exception("AP is not up. Please check the appliance !!")

        logging.info("Ping Successful")
        timeout = 1800
        logging.info("timeout : " + str(timeout))
        time.sleep(5)
        currtime = time.time() - start_time
        logging.info("current time: " + str(currtime))
        while currtime < timeout:
            try:
                requests.post(
                    "https://" + ip + ":9443/swagger-ui/index.html")
            except Exception, ex:
                logging.info("Output for swagger call: " + str(ex.message))
                error = str(ex.message)
                expected_string = "CERTIFICATE_VERIFY_FAILED]"
                logging.info("Verifying if SSL error is thrown")
                logging.info(error)
                if expected_string in error:
                    return True

            time.sleep(5)
            currtime = time.time() - start_time
            logging.info("current time: " + str(currtime))

        logging.info("SSL error not thrown. AP setup did not complete in time.")
        raise Exception("AP setup timedout")


class Request(object):
    '''
    HTTP helper using requests.
    '''

    def __init__(self, address, end_point, port=80, max_retry=None, delay=None,
                 **kwargs):
        Validation.validate_param(address, 'Missing host')
        self.__address = address.strip()
        self.__endpoint = end_point
        self.__port = port
        self.max_retry = max_retry or Timings().get_max_retry_attempt_4()
        self.delay = delay or Timings().get_task_wait_interval_sec_2()
        self.session = requests.session()
        self.data = {}

        self.url = 'http' if port == 80 else 'https'
        self.url += '://' + self.__address
        self.url_prefix = self.url
        self.url += '/' + self.__endpoint

    def update_data(self, val):
        '''
        Add or update current data dictionary
        :param val:
        :return:
        '''
        self.data.update(val)

    def init_session(self, response):
        '''
        initialize web session
        Set the followings in current data dictionary:
         - csrf/authenticity token
         - session id
        :param response:
        :return:
        '''

        # this regex will match if AV manager is to be configured
        xp = 'meta content="(.*)" name="csrf-token" /'
        ret = {}
        csrf = re.search(xp, str(response.text))
        if not csrf:
            # this regex will match if AV manager is already configured
            xp1 = 'name="authenticity_token" type="hidden" value="(.*)" /'
            csrf = re.search(xp1, str(response.text))

            # return a flag to turn on the login interceptor
            ret = {'skip_login': False}
            if not csrf:
                msg = 'Failed to obtain csrf token from server'
                logging.warn(msg)
                raise Exception(msg)
            else:
                logging.debug('AV manager has been configured.Login '
                              + 'interception will be turned on.')
        else:
            logging.debug('AV manager has not been configured. '\
                          + 'Login interception will be off.')

        self.data['authenticity_token'] = csrf.group(1)

        if '_session_id' in response.cookies:
            self.data['_session_id'] = response.cookies['_session_id']
            logging.debug(self.__address + ': current web session id = '
                          + self.data['_session_id'])

        return ret

    def __request(self, url, params, method='GET', data=None, files=None):
        '''
        The wrapper for all GET, POST, PUT
        :param url:
        :param params:
        :param method:
        :param data:
        :param files:
        :return:
        '''

        # if the passed in url starts with / then will use it as is, otherwise
        # prepend the current self.url to the passed in url
        #
        # some services provide certain API that does not use end point such
        # as the login API for cv_api
        url = self.url_prefix + url if url.startswith('/') \
                    else self.url + '/' + url

        if params:
            url += '?' + urllib.urlencode(params)
        msg = self.__address + ': ' + method.upper() + ' ' + url + ' '

        # if data are not passed in then use the internal data dictionary
        if not data:
            data = self.data
        retries = 0
        rs = None
        while True:
            try:
                # set verify=False to disable SSL verification
                if self.__port == 443:
                    if method == 'GET':
                        rs = self.session.get(url, verify=False)
                    elif method == 'POST':
                        rs = self.session.post(url, data=data, files=files,
                                               verify=False)
                    elif method == 'PUT':
                        rs = self.session.put(url, data, verify=False)
                    else:
                        rs = self.session.delete(url, verify=False)
                else:
                    if method == 'GET':
                        rs = self.session.get(url)
                    elif method == 'POST':
                        rs = self.session.post(url, data=data, files=files)
                    elif method == 'PUT':
                        rs = self.session.put(url, data)
                    else:
                        rs = self.session.delete(url)
                break
            except:
                logging.debug(sys.exc_info()[1])
                if retries < self.max_retry:
                    retries += 1
                    logging.debug(msg + 'attempt ' + str(retries) + '/'
                                  + str(self.max_retry))
                    time.sleep(self.delay)
                else:
                    logging.debug(msg + 'failed, error: ' + sys.exc_info()[1])
                    raise

        if rs.status_code not in [200, 201]:
            msg = msg + 'failed, rc=' + str(rs.status_code) + ' ' + rs.text
            logging.warn(msg)
            raise Exception(msg)

        return rs

    def get(self, url, params=None):
        '''
        Wrapper to send a GET request
        :param url:
        :param params:
        :param data:
        :return:
        '''
        return self.__request(url, params=params)

    def get_json(self, url, params=None):
        '''
        Wrapper to send a GET request and return objects from the json output
        :param url:
        :param params:
        :return:
        '''
        rs = self.get(url, params=params)
        return json.loads(rs.text)

    def post(self, url, params=None, data=None, files=None, out_file=None):
        '''
        Wrapper to send a POST request
        :param url:
        :param params:
        :param data:
        :param files:
        :return:
        '''
        return self.__request(url, params=params, method='POST', data=data,
                              files=files)

    def put(self, url, params, data=None):
        '''
        Wrapper to send a PUT request
        :param url:
        :param params:
        :param data:
        :return:
        '''
        self.__request(url, params=params, method='PUT', data=data)

    def delete(self, url):
        self.__request(url, params=None, method='DELETE')




