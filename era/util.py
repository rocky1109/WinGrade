'''
Created on Mar 19, 2015

@author: nguyenc
'''
import string
import random
from datetime import datetime
from dateutil import parser
import types
from dateutil.parser import parse
import requests
import shutil
import glob
import zipfile
import logging.config
from logging.handlers import RotatingFileHandler
from logging import Formatter, StreamHandler
import os.path
import subprocess
import platform
import os
from time import time, sleep
import paramiko
import json
import logging
import os.path
import sys
import threading

try:
    from threading import _get_ident as get_ident
except ImportError:
    from thread import get_ident
import linecache
import time

from core import Singleton


class ThreadMon(object):
    '''
    A class to troubleshoot thread issues
    '''

    SECONDS_FROZEN = 30  # seconds
    TESTS_PER_SECOND = 10

    @staticmethod
    def frame2string(frame):
        # from module traceback
        lineno = frame.f_lineno  # or f_lasti
        co = frame.f_code
        filename = co.co_filename
        name = co.co_name
        s = '  File "{}", line {}, in {}'.format(filename, lineno, name)
        line = linecache.getline(filename, lineno, frame.f_globals).lstrip()
        return s + '\n\t' + line

    @staticmethod
    def thread2list(frame):
        l = []
        while frame:
            l.insert(0, ThreadMon.frame2string(frame))
            frame = frame.f_back
        return l

    @staticmethod
    def monitor():
        self = get_ident()
        old_threads = {}
        while 1:
            time.sleep(1. / ThreadMon.TESTS_PER_SECOND)
            now = time.time()
            then = now - ThreadMon.SECONDS_FROZEN
            frames = sys._current_frames()
            new_threads = {}
            for frame_id, frame in frames.items():
                new_threads[frame_id] = ThreadMon.thread2list(frame)
            for thread_id, frame_list in new_threads.items():
                if thread_id == self: continue
                if thread_id not in old_threads or \
                                frame_list != old_threads[thread_id][0]:
                    new_threads[thread_id] = (frame_list, now)
                elif old_threads[thread_id][1] < then:
                    ThreadMon.print_frame_list(frame_list, frame_id)
                else:
                    new_threads[thread_id] = old_threads[thread_id]
            old_threads = new_threads

    @staticmethod
    def print_frame_list(frame_list, frame_id):
        sys.stderr.write('-' * 20 +
                         'Thread {}'.format(frame_id).center(20) +
                         '-' * 20 +
                         '\n' +
                         ''.join(frame_list))

    @staticmethod
    def start_monitoring():
        '''After hanging SECONDS_FROZEN the stack trace of the deadlock is
        printed automatically.'''
        thread = threading.Thread(target=ThreadMon.monitor)
        thread.daemon = True
        thread.start()
        return thread


###############################################################################
#
# connectSsh --
#
# Sets up a ssh client connection object to a single host. Server, user, and
# pwd are strings to specify login credentials to a specific server.
#
# Results:
#      A paramiko SSHClient object to a single host
#
# Side effects:
#      A SSH connection is established to the server specified by the server
#      parameter
#
###############################################################################
def connectSsh(server, user, pwd):
    try:
        sshLogger = logging.getLogger("paramiko.transport")
        sshLogger.setLevel("ERROR")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server, username=user, password=pwd)
        ssh.get_transport().setName(server)
        ssh.get_transport().set_keepalive(1)
    except:
        logging.exception("***Failed to establish ssh connection to " + server)
        raise
    return ssh


###############################################################################
#
# closeSsh --
#
# Close SSH session
#
# Results:
#      None
#
# Side effects:
#      None
#
###############################################################################
def closeSsh(ssh):
    try:
        transport = ssh.get_transport()
        transport.close()
        logging.info(
            "Close ssh connection on %s" % ssh.get_transport().getName())
    except Exception, e:
        logging.error(e)


###############################################################################
#
# runSshCommand --
#
# Executes a remote command on a server over ssh. The server information is
# passed through a paramiko ssh object specified by the ssh parameter. command
# is a string representing the command to run. Optionally, timeout is the time
# in seconds to wait for the command to finish executing before throwing an
# exception. If timeout=0, the timeout will be indefinite.
#
# Results:
#      A SshCommandResult object containing stdout, stderr, and the return code
#      from the executed command. An exception is thrown if the ssh command
#      fails to execute, if it does not return within timeout seconds, or if
#      the return code from the executed command is not zero.
#
# Side effects:
#      A command may run on a remote host.
#
###############################################################################
def runSshCommand(ssh, command, timeout=10):
    startTime = datetime.now()
    RECV_CHUNK_SIZE = 128  # in bytes
    COMMAND_WAIT_SLEEP_TIME = 1
    try:
        session = ssh.get_transport().open_session()
        logging.info("Running SSH command: " + command)
        session.exec_command(command)
        # startTime = time()

        sleep(5)

        # Wait for the command to complete
        while not session.exit_status_ready():
            if timeout > 0 and (datetime.now() - startTime).total_seconds() > timeout:
                raise Exception(
                    "Timeout exceeded waiting for ssh command to finish")
            sleep(COMMAND_WAIT_SLEEP_TIME)

        returnCode = session.recv_exit_status()

        stdoutRawData = []
        while session.recv_ready():
            stdoutRawData.append(session.recv(RECV_CHUNK_SIZE))
        stdout = "".join(stdoutRawData)

        stderrRawData = []
        while session.recv_stderr_ready():
            stderrRawData.append(session.recv_stderr(RECV_CHUNK_SIZE))
        stderr = "".join(stderrRawData)
    except:
        logging.error("***Failed to execute SSH command: " + command)
        raise
    if returnCode != 0:
        errorString = "[%s]: SSH command '%s' returned a non-zero return code" \
                      % (ssh.get_transport().getName(), command)
        logging.error(errorString)
        logging.error("STDOUT from failed command: %s" % stdout)
        logging.error("STDERR from failed command: %s" % stderr)
        raise Exception(errorString)
    return SshCommandResult(stdout, stderr, returnCode)

###############################################################################
#
# runSshSudoCommand --
#
# Executes a remote sudo command on a server over ssh. The server information is
# passed through a paramiko ssh object specified by the ssh parameter. command
# is a string representing the command to run.
#
# Results:
#      The output of the executed command in the buffer . An exception is thrown
#      if the ssh command does not return within timeout seconds, or if
#      command does not execute successfully
#
###############################################################################
def runSshSudoCommand(ssh,command,pwd,wait_time_for_pwd_prompt=1,
                         wait_time_for_cmd=1,wait_string=None,
                         should_print=True,timeout=20):
    try:
        shell=ssh.invoke_shell()
        logging.info("Running command :"+command)
        shell.send(command+ " \n")
        logging.info("Waiting for "+str(wait_time_for_pwd_prompt)+
                     " seconds for password prompt")
        time.sleep(wait_time_for_pwd_prompt)
        receive_buffer = shell.recv(1028)
        if should_print:
            logging.info(receive_buffer)

        shell.send(pwd+'\n')
        time.sleep(wait_time_for_cmd)
        receive_buffer = shell.recv(2048)
        startTime=datetime.now()

        if wait_string:
            while not wait_string in receive_buffer:
                if timeout > 0 and (datetime.now() -
                                        startTime).total_seconds() > timeout:
                    raise Exception("Timeout exceeded waiting for ssh command "
                                    "to finish")

                receive_buffer += shell.recv(1024)
                logging.info(receive_buffer)
        return receive_buffer
    except Exception as e:
        logging.error("Failed to run sudo command "+str(e))
        raise
###############################################################################
#
# sendFile --
#
# Sends a file to a remote host via sftp. The remote host is specified by the
# paramiko SSHClient object passed to "ssh". The local and remote file paths
# are given by localPath and remotePath, respectively.
#
# Results:
#      Nothing if the sftp command succeeds. An exception is raised if it
#      doesn't succeed.
#
# Side effects:
#      A file may be copied to a remote host.
#
###############################################################################
def sendFile(ssh, localPath, remotePath):
    try:
        sftp = ssh.open_sftp()
        sftp.put(localPath, remotePath)
        sftp.close()
    except:
        logging.error("***Failed to sftp file " + localPath)
        raise

###############################################################################
#
# getFile --
#
# Gets a file from remote host via sftp. The remote host is specified by the
# paramiko SSHClient object passed to "ssh". The local and remote file paths
# are given by localPath and remotePath, respectively.
#
# Results:
#      Nothing if the sftp command succeeds. An exception is raised if it
#      doesn't succeed.
#
# Side effects:
#      A file may be copied to a remote host.
#
###############################################################################
def getFile(ssh, remotePath, localPath):
   try:
      sftp = ssh.open_sftp()
      sftp.get(remotePath,localPath)
      sftp.close()
   except:
      logging.error("***Failed to sftp file " + localPath)
      raise

###############################################################################
#
# SshCommandResult --
#
# Class to store the results of executing a SSH command on a remote host.
# Standard input, error, and the command's return code can be accessed through
# the public members stdout, stderr, and returnCode.
#
###############################################################################
class SshCommandResult:
    def __init__(self, stdout, stderr, returnCode):
        self.stdout = stdout
        self.stderr = stderr
        self.returnCode = returnCode


#################################################################
# This is wrapper on "ovftool" to deploy ova or ovf
# It needs json file to read options needed for deploy
# It assumes "ovftool" is installed on host where this will run.
# TODO: Impliment ovf deploy via pyvmomi
#################################################################

def readJSON(jsonfile):
    """
    Reads json file and returns datastructure
    :param jsonfile: jsonfile location
    :return: json file data
    """
    logging.info("Read JSON")
    with open(jsonfile) as f:
        data = json.load(f)

    return data


def appendCommand(cmd, options, prefix):
    """
    Append options to ofvdeploy tool
    :param cmd: command string to append options to
    :param options: dict with k:v pair
    :param prefix: prefix to add before each option
    :return: cmd string with options appended
    """
    if len(options.keys()) > 0:
        for key, value in options.iteritems():
            if value != "":
                cmd = cmd + " --%s:%s=%s" % (prefix, key, value)
            else:
                continue

    return cmd


def deployOVF(jsonfile, ovflocation, poweron=False, overwrite=False):
    """
    OS call to deploy ovf/ova using "ovftool"
    :param jsonfile: jsonfile location
    :param ovflocation: ovf/ova file location
    :param poweron: Boolean value to powerON VM after deploy
    :param overwrite: Poweroff and Overwrite existing VM
    :return: None
    """
    cmdList = []
    cmd = "ovftool --acceptAllEulas --skipManifestCheck --X:injectOvfEnv"

    if poweron:
        cmd += " --powerOn"

    if overwrite:
        cmd += " --overwrite --powerOffTarget"

    data = readJSON(jsonfile)

    cmd = constructCommand(ovflocation, data, cmd)

    cmdList.append(cmd)
    logging.info("Running ovftool command:\n%s" % cmd)
    p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, )
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("%r failed, status code %s stdout %r stderr %r"
                           % (cmd, p.returncode, out, err))
    logging.info(out)


def constructCommand(ovflocation, data, cmd):
    """
    Construct command needed for deploying givien OVA/OVF
    :param ovflocation: ofv/ova file location
    :param data: data from json file
    :param cmd: cmd string
    :return: cmd string with all needed options appended
    """
    vcinfo = data['vc']
    logging.debug(vcinfo)
    deployLocation = "%s/%s/host" % (vcinfo['ip'], vcinfo['datacenter'])
    if vcinfo.has_key('cluster'):
        deployLocation = deployLocation + "/" + vcinfo['cluster']
    if vcinfo.has_key('poolname'):
        deployLocation = deployLocation + "/" + vcinfo['poolname']

    vcConnect = "vi://%s:%s@%s" % (vcinfo['user'], vcinfo['password'],
                                   deployLocation)

    # Append vmname
    if data['vmconfig'].has_key('vmname'):
        cmd += " --name='%s'" % data['vmconfig']['vmname']

    # Append datastore and diskmode
    if data['vmconfig'].has_key('datastore'):
        cmd += " --datastore='%s'" % data['vmconfig']['datastore']

    if data['vmconfig'].has_key('diskMode'):
        cmd += " --diskmode='%s'" % data['vmconfig']['diskmode']

    # Append network key values to cmd
    for ele in data['ethernetAdapter']:
        cmd = appendCommand(cmd, ele, "net")

    # Append other properties
    cmd = appendCommand(cmd, data['property'], "prop")

    # Append ova/ovf location
    cmd += " %s" % ovflocation

    # Append VC info
    cmd += " '%s'" % vcConnect
    print(cmd)
    return cmd


def generate_ap_deploy_command(data, vcsa_ova, host):
    logging.info("Constructing command for VCSA deployment from the params..")

    # read data from the json param file

    ap_vmname = data['ap_vmname']
    Validation.validate_param(ap_vmname, "ap_vmname not set")
    logging.info( "ap_vmname: " + ap_vmname)

    datastore = data['datastore']
    Validation.validate_param(datastore, "datastore not set")
    logging.info( "datastore: " + datastore)

    deployment_option = data['deployment_option']
    Validation.validate_param(deployment_option, "deployment_option not set")
    logging.info( "deployment_option: " + deployment_option)

    public_nw = data['public_nw']
    Validation.validate_param(public_nw, "public_nw not set")
    logging.info( "public_nw: " + public_nw)

    mngmt_nw = data['mngmt_nw']
    Validation.validate_param(mngmt_nw, "mngmt_nw not set")
    logging.info( "mngmt_nw: " + mngmt_nw)

    backbone_nw = data['backbone_nw']
    Validation.validate_param(backbone_nw, "backbone_nw not set")
    logging.info( "backbone_nw: " + backbone_nw)

    ip0 = data['ip0']
    Validation.validate_param(ip0, "ip0 not set")
    logging.info("ip0: " + ip0)

    route0 = data['route0']
    Validation.validate_param(route0, "route0 not set")
    logging.info("route0: " + route0)

    dns = data['dns']
    Validation.validate_param(dns, "dns not set")
    logging.info( "dns: " + dns)

    adminpwd = data['adminpwd']
    Validation.validate_param(adminpwd, "adminpwd not set")
    logging.info( "adminpwd: " + adminpwd)

    rootpwd = data['rootpwd']
    Validation.validate_param(rootpwd, "rootpwd not set")
    logging.info( "rootpwd: " + rootpwd)

    vcenter_server = data['vcenter_server']
    Validation.validate_param(vcenter_server, "vcenter_server not set")
    logging.info( "vcenter_server: " + vcenter_server)

    vc_user = data['vc_user']
    Validation.validate_param(vc_user, "vc_user not set")
    logging.info( "vc_user: " + vc_user)

    vc_pwd = data['vc_pwd']
    Validation.validate_param(vc_pwd, "vc_pwd not set")
    logging.info( "vc_pwd: " + vc_pwd)

    if host != "esxi":
        resourcepool = data['resourcepool']
        if resourcepool is not None:
            if len(resourcepool) > 1:
                Validation.validate_param(resourcepool, "resourcepool not set")
                logging.info( "resourcepool: " + resourcepool)
        datacenter = data['datacenter']
        Validation.validate_param(datacenter, "datacenter not set")
        logging.info( "datacenter: " + datacenter)

    # constructing command based on the values read from the json file
    cmd = 'ovftool --X:enableHiddenProperties  --powerOffTarget  --powerOn  ' \
          '--overwrite --net:Internet="'+ public_nw +'"  '\
          '--net:ManagementNetwork="'+mngmt_nw+'" '\
         '--net:BackendNetwork="'+backbone_nw+'" -ds="'+datastore+  \
          '" --name="'+ap_vmname+'"  --ipAllocationPolicy=fixedPolicy ' \
        '--deploymentOption='+deployment_option+'  --prop:ip0='+ip0+  \
       ' --prop:DNS="'+dns+'"  --prop:adminPassword='+adminpwd+  \
        ' --prop:rootPassword='+rootpwd+' --prop:ipMode0=STATICV4 ' \
        '--prop:routes0="'+route0+'" ' \
          # '--prop:viewDestinationURL='+horizon_server_url+' '

    if "twonic" in deployment_option:
        ip1 = data['ip1']
        Validation.validate_param(ip1, "ip1 not set")
        logging.info("ip1: " + ip1)

        route1 = data['route1']
        Validation.validate_param(route1, "route1 not set")
        logging.info("route1: " + route1)

        cmd+='--prop:ip1='+ip1+' --prop:routes1="'+route1+'" '

    cmd += str(vcsa_ova)

    if host == "esxi":
        cmd += ' vi://' + vc_user + ':' + vc_pwd + '@' + vcenter_server
    else:
        if resourcepool is None:
            cmd += ' vi://' + vc_user + ':' + vc_pwd + '@' + vcenter_server +\
                '/' +datacenter + '/host/' + host
        else:
            if len(resourcepool) > 1:
                cmd += ' vi://' + vc_user + ':' + vc_pwd + '@' + vcenter_server +\
                '/' + datacenter + '/host/' + host + '/Resources/' + resourcepool
            else:
                cmd += ' vi://' + vc_user + ':' + vc_pwd + '@' + vcenter_server + \
                       '/' + datacenter + '/host/' + host

    cmd=cmd.replace('$', '\$')

    return cmd


def generate_vcsa_command(data, vcsa_ova, host):
    '''
    @param data: Data read from the json
    @param vcsa_ova: URL for the OVA
    '''
    logging.info( "Constructing command for VCSA deployment from the params..")

    # read data from the json param file

    vcsa_vmname = data['vcsa_vmname']
    Validation.validate_param(vcsa_vmname, "vcsa_vmname not set")
    logging.info("vcsa_vmname: " + vcsa_vmname)
    vcsa_root_pwd = "ca\$hc0w"
    Validation.validate_param(vcsa_root_pwd, "vcsa_root_pwd not set")
    logging.info( "vcsa_root_pwd: " + vcsa_root_pwd.replace('\\',''))
    vcsa_network_mode = "static"
    Validation.validate_param(vcsa_network_mode, "vcsa_network_mode not set")
    logging.info( "vcsa_network_mode: " + vcsa_network_mode)
    vcsa_network_family = "ipv4"
    Validation.validate_param(vcsa_network_family, "vcsa_network_family  not "
                                                   "set")
    logging.info( "vcsa_network_family: " + vcsa_network_family)
    vcsa_network_prefix = "21"
    Validation.validate_param(vcsa_network_prefix, "vcsa_network_prefix  not "
                                                   "set")
    logging.info( "vcsa_network_prefix: " + vcsa_network_prefix)
    vcsa_hostname = data['vcsa_hostname']
    Validation.validate_param(vcsa_hostname, "vcsa_hostname not set")
    logging.info( "vcsa_hostname: " + vcsa_hostname)
    vcsa_ip = data['vcsa_ip']
    Validation.validate_param(vcsa_ip, "vcsa_ip not set")
    logging.info( "vcsa_ip: " + vcsa_ip)
    vcsa_gateway = data['vcsa_gateway']
    Validation.validate_param(vcsa_gateway, "vcsa_gateway not set")
    logging.info( "vcsa_gateway: " + vcsa_gateway)
    vcsa_dns = data['vcsa_dns']
    Validation.validate_param(vcsa_dns, "vcsa_dns not set")
    logging.info( "vcsa_dns: " + vcsa_dns)
    vcsa_enable_ssh = "True"
    Validation.validate_param(vcsa_enable_ssh, "vcsa_enable_ssh not set")
    logging.info( "vcsa_enable_ssh: " + vcsa_enable_ssh)
    vcsa_deployment_size = data['vcsa_deployment_size']
    Validation.validate_param(vcsa_deployment_size, "vcsa_deployment_size  "
                                                    "not set")
    logging.info( "vcsa_deployment_size: " + vcsa_deployment_size)

    sso_domain_name = "vsphere.local"
    Validation.validate_param(sso_domain_name, "sso_domain_name not set")
    logging.info( "sso_domain_name: " + sso_domain_name)
    sso_site_name = "Default-First-Site"
    Validation.validate_param(sso_site_name, "sso_site_name not set")
    logging.info( "sso_site_name: " + sso_site_name)
    sso_admin_pwd = "Ca\$hc0w1"
    Validation.validate_param(sso_admin_pwd, "sso_admin_pwd not set")
    logging.info( "sso_admin_pwd: " + sso_admin_pwd.replace('\\',''))

    ntp_servers = data['ntp_servers']
    Validation.validate_param(ntp_servers, "ntp_servers not set")
    logging.info( "ntp_servers: " + ntp_servers)

    vcenter_server = data['vcenter_server']
    Validation.validate_param(vcenter_server, "vcenter_server not set")
    logging.info( "vcenter_server: " + vcenter_server)
    # host = "Infra-01"
    Validation.validate_param(host, "host not set")
    logging.info( "host: " + host)
    # vc_user = "vtfserviceaccount@horizon.net"
    vc_user = data['vc_user']
    Validation.validate_param(vc_user, "vc_user not set")
    logging.info( "vc_user: " + vc_user)
    vc_pwd = data['vc_pwd']
    Validation.validate_param(vc_pwd, "vc_pwd not set")
    logging.info( "vc_pwd: " + vc_pwd)
    vm_network = data['vm_network']
    Validation.validate_param(vm_network, "vm_network not set")
    logging.info( "vm_network: " + vm_network)
    datastore = data['vm_datastore']
    Validation.validate_param(datastore, "datastore not set")
    logging.info( "datastore: " + datastore)

    resourcepool = data['resourcepool']

    # datacenter = "WDC"
    datacenter = data['datacenter']
    version = data['version']

    if host != "esxi":
        Validation.validate_param(resourcepool, "resourcepool not set")
        print "resourcepool: " + resourcepool
        Validation.validate_param(datacenter, "datacenter not set")
        print "datacenter: " + datacenter

    # constructing command based on the values read from the json file
    cmd = 'ovftool --acceptAllEulas ' \
          '--skipManifestCheck --X:injectOvfEnv  ' \
          '--allowExtraConfig --X:enableHiddenProperties --X:waitForIp  ' \
          '--sourceType=OVA --powerOn --noSSLVerify \
            "--net:Network 1=' + vm_network + '" "--datastore=' + datastore +\
          '" "--diskMode=thin" "--name=' + vcsa_vmname + '" \
           "--deploymentOption=' + vcsa_deployment_size + '" \
            "--prop:guestinfo.cis.vmdir.domain-name=' + sso_domain_name + '" \
            "--prop:guestinfo.cis.vmdir.site-name=' + sso_site_name + '" \
            "--prop:guestinfo.cis.vmdir.password=' + sso_admin_pwd + '" \
            "--prop:guestinfo.cis.appliance.net.addr.family=' +  \
          vcsa_network_family + '" \
            "--prop:guestinfo.cis.appliance.net.addr=' + vcsa_ip + '" \
            "--prop:guestinfo.cis.appliance.net.pnid=' + vcsa_hostname + '" \
            "--prop:guestinfo.cis.appliance.net.prefix=' + \
          vcsa_network_prefix +  '" \
            "--prop:guestinfo.cis.appliance.net.mode=' + vcsa_network_mode +'" \
            "--prop:guestinfo.cis.appliance.net.dns.servers=' + vcsa_dns + '" \
            "--prop:guestinfo.cis.appliance.net.gateway=' + vcsa_gateway + '" \
            "--prop:guestinfo.cis.appliance.root.passwd=' + vcsa_root_pwd + '" \
            "--prop:guestinfo.cis.appliance.ssh.enabled=' + vcsa_enable_ssh  \
          + '" \
            "--prop:guestinfo.cis.appliance.ntp.servers=' + ntp_servers + '" '

    if version == "65":
        cmd += ' "--prop:guestinfo.cis.ceip_enabled=True" '
        cmd += ' "--prop:guestinfo.cis.deployment.autoconfig=True" '

    cmd += vcsa_ova

    if host == "esxi":
        cmd += ' vi://' + vc_user + ':' + vc_pwd + '@' + vcenter_server
    else:
        cmd += ' vi://' + vc_user + ':' + vc_pwd + '@' + vcenter_server + '/'+\
           datacenter + '/host/' + host + '/Resources/' + resourcepool

    cmd.replace('$', '\$')

    return cmd


def configure_ap_hza(data, ta_net_info):

    logging.info("SSH session for SP: ")

    ssh = connectSsh(data['sp_ip'], data['sp_user'], data['sp_pwd'])

    result = runSshCommand(ssh, "ifconfig")
    sp_backbone_ip = result.stdout.split("Bcast:")[3].split(" ")[0]

    logging.info("SP backbone IP: " + sp_backbone_ip)

    s = sp_backbone_ip.split('.')
    for net in ta_net_info:
        ip = str(net.ipAddress)
        ta_backbone_ip = ip.replace(' ', '').replace('\n', '').split(',')[0]
        ta_backbone_ip = ta_backbone_ip.replace('[', '').replace('\'',
                                         '').replace('(str)', '')
        s = s[0]
        ip=ta_backbone_ip.split('.')[0]
        if s in ip:
            break
    logging.info("TA backbone IP: " + ta_backbone_ip)

    ap_pwd = data['ap_pwd']
    ap_pwd = ap_pwd.replace('$', '\\$')

    args = "$'n\\nno\\n"+ap_pwd+"\\n"+data[
        'management_ip']+"\\n"+data['external_ip']+"\\n"+data[
        'external_ip']+"\\n4172\\n8443\\n443\\n'"

    cmd="hostname ;ssh -o \"StrictHostKeyChecking no\" "+ta_backbone_ip+" " \
                "/usr/local/desktone/scripts/apsetup.sh <<< " + args

    logging.info(cmd)

    result = runSshCommand(ssh, cmd)

    logging.info(result.stdout)
    logging.info(result.returnCode)

    if "400" in str(result.stdout) or "200" in str(result.stdout):
        logging.info(result.stderr)
        return True
    else:
        raise Exception("apsetup.sh script failed. Error: "+result.stdout + " "\
                        + str(result.returnCode))


def get_sslThumbprint(hostname):
    '''
    :param hostname: Host IP to get the sslThumbprint
    :return: thumbprint
    '''
    cmd = "echo -n | openssl s_client -connect " + hostname +  ":443 " \
                                                               "2>/dev/null | "\
            "openssl x509 -noout -fingerprint -sha1"
    output = Process().start_process(cmd)

    if output is not None:
            return output.split('=')[1]

    return None


def get_dct_bundle(vm_agent, location=None):
    '''
    Download DCT Bundle
    :param vm_name:
    :param location:
    :return:
    '''
    # vm_agent = ERAAgent(vm_name)

    # Check and wait for 2 min for ERA Agent to respond
    vm_agent.wait_til_ok(max_wait_sec=30)

    logging.info("Starting DCT support on %s" % vm_agent)
    vm_agent.start_dct_bundle()

    logging.info("Waiting for DCT support to finish..")
    while vm_agent.get_dct_succeeded() != 'true':
        logging.debug("Sleeping for 10 sec before next check...")
        time.sleep(10)

    if vm_agent.get_dct_succeeded() == 'true':
        name = vm_agent.get_dct_name().split("\\")[-1].strip('"')
        newlocation = os.path.join(location, name)
        logging.info("Downloading %s from %s" % (name, vm_agent.ip))
        vm_agent.get_dct_bundle(name, newlocation)
        logging.info("Completed downloading DCT support bundle %s under "
                     "%s" % (name, newlocation))


class Process(object):
    '''
    Utility to launch new processes
    '''

    @staticmethod
    def start_process(cmd):
        msg = 'Launching process: ' + cmd
        logging.debug(msg)
        p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, )
        out, err = p.communicate()
        if p.returncode != 0 or err:
            raise RuntimeError("%r failed, status code %s stdout %r stderr %r"
                               % (cmd, p.returncode, out, err))
        return out.strip()


def ping(serverIP):
    '''
    :param serverIP: server name or IP to ping
    :return: True if server is pingable or False otherwise
    '''
    if platform.system() == "Windows":
        res = subprocess.call(['ping', serverIP])
    else:
        res = subprocess.call(['ping', '-c', '3', serverIP])

    if res == 0:
        return True
    else:
        return False


def pingServer(serverIP, timeout=1800):
    '''
    pingServer --
    pings server IP/Name specified. Server name or IP as string parameter.

    Returns:
    0 if ping is successful, else return 1
    '''
    returnValue = 0

    curTime = time.time()
    # waittime = curTime + timeout

    while True:
        if ping(serverIP):
            returnValue = 0
            break
        elif (time.time() - curTime) > timeout:
            returnValue = 1
            break
        else:
            logging.info("Server ping is not back...")
            logging.info("Sleeping for 5 min before checking again on %s"
                         % serverIP)
            sleep(300)

    return returnValue


class Linux(object):
    '''
    Utilities to work with Linux VMs
    '''

    sudo_prefix = 'sudo ' if 'root' != Process.start_process('whoami') else ''

    @staticmethod
    def mount(user, password, net_share, local_folder):
        '''
        Mount CIF shares
        Require cifs-utils.
        :param user:
        :param password:
        :param net_share:
        :param local_folder:
        :return:
        '''
        if not os.path.exists(local_folder):
            cmd = Linux.sudo_prefix + 'mkdir ' + local_folder
            logging.debug('creating mount point: ' + local_folder)
            Process.start_process(cmd)

        cmd = 'mount | grep ' + local_folder
        try:
            out = Process.start_process(cmd)
        except:
            cmd = Linux.sudo_prefix + '/sbin/mount.cifs ' + net_share + ' ' \
                  + local_folder + ' -o user=' + user + ',sec=ntlm,password=' + password
            logging.debug('mounting share: ' + cmd)
            Process.start_process(cmd)

    @staticmethod
    def umount(net_share):
        '''
        Unmount a share
        :param net_share:
        :return:
        '''
        cmd = Linux.sudo_prefix + 'umount ' + net_share
        logging.debug('umounting: ' + cmd)
        Process.start_process(cmd)


class Timings(object):
    __metaclass__ = Singleton

    '''
    Controls:

    - delays, using Timings().get_task_wait_interval_sec_x
    - timeouts, using Timings().get_timeout_sec_x
    - retry attempts, using Timings().get_max_retry_attempt_x
    - reconfirm counts, using Timings().get_reconfirm_count_x

    where x = [1(fastest) .. 7(slowest)]

    To change test execution speed:

    Timings().update(n)

    where:
    - n > 0 to speed up
    - n < 0 to slow down
    - n range [1 .. 6]

    Slowing things down can make test executions more stable
    '''

    def __init__(self):
        self.max_retry_attempt_values = [3, 6, 10, 20, 40, 80, 160, 320, 640]
        self.reconfirm_count_values = [1, 2, 5, 10, 15, 20, 25, 30, 35]
        self.task_wait_interval_sec_values = [1, 5, 20, 40, 80, 160, 320, 1280,
                                              5120]
        self.timeout_sec_values = [60, 120, 300, 900, 1800, 3600, 7200, 10800,
                                   14400]
        self.adjust = 0
        self.bound = 8
        self.lock = threading.RLock()

    def get_max_retry_attempt_range(self):
        '''
        Fetch the list of possible values for max_retry_attempt
        :return:
        '''
        return self.max_retry_attempt_values

    def get_reconfirm_count_range(self):
        '''
        Fetch the list of possible values for reconfirm_count
        :return:
        '''
        return self.reconfirm_count_values

    def get_task_wait_interval_sec_range(self):
        '''
        Fetch a list of possible values for task_wait_interval_sec
        :return:
        '''
        return self.task_wait_interval_sec_values

    def get_timeout_sec_range(self):
        return self.timeout_sec_values

    def get_max_retry_attempt_1(self):
        return self.get_value(0, self.max_retry_attempt_values)

    def get_max_retry_attempt_2(self):
        return self.get_value(1, self.max_retry_attempt_values)

    def get_max_retry_attempt_3(self):
        return self.get_value(2, self.max_retry_attempt_values)

    def get_max_retry_attempt_4(self):
        return self.get_value(3, self.max_retry_attempt_values)

    def get_max_retry_attempt_5(self):
        return self.get_value(4, self.max_retry_attempt_values)

    def get_max_retry_attempt_6(self):
        return self.get_value(5, self.max_retry_attempt_values)

    def get_max_retry_attempt_7(self):
        return self.get_value(6, self.max_retry_attempt_values)

    def get_reconfirm_count_1(self):
        return self.get_value(0, self.reconfirm_count_values)

    def get_reconfirm_count_2(self):
        return self.get_value(1, self.reconfirm_count_values)

    def get_reconfirm_count_3(self):
        return self.get_value(2, self.reconfirm_count_values)

    def get_reconfirm_count_4(self):
        return self.get_value(3, self.reconfirm_count_values)

    def get_reconfirm_count_5(self):
        return self.get_value(4, self.reconfirm_count_values)

    def get_reconfirm_count_6(self):
        return self.get_value(5, self.reconfirm_count_values)

    def get_reconfirm_count_7(self):
        return self.get_value(6, self.reconfirm_count_values)

    def get_reconfirm_count_8(self):
        return self.get_value(7, self.reconfirm_count_values)

    def get_reconfirm_count_9(self):
        return self.get_value(8, self.reconfirm_count_values)

    def get_task_wait_interval_sec_1(self):
        return self.get_value(0, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_2(self):
        return self.get_value(1, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_3(self):
        return self.get_value(2, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_4(self):
        return self.get_value(3, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_5(self):
        return self.get_value(4, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_6(self):
        return self.get_value(5, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_7(self):
        return self.get_value(6, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_8(self):
        return self.get_value(7, self.task_wait_interval_sec_values)

    def get_task_wait_interval_sec_9(self):
        return self.get_value(8, self.task_wait_interval_sec_values)

    def get_timeout_sec_1(self):
        return self.get_value(0, self.timeout_sec_values)

    def get_timeout_sec_2(self):
        return self.get_value(1, self.timeout_sec_values)

    def get_timeout_sec_3(self):
        return self.get_value(2, self.timeout_sec_values)

    def get_timeout_sec_4(self):
        return self.get_value(3, self.timeout_sec_values)

    def get_timeout_sec_5(self):
        return self.get_value(4, self.timeout_sec_values)

    def get_timeout_sec_6(self):
        return self.get_value(5, self.timeout_sec_values)

    def get_timeout_sec_7(self):
        return self.get_value(6, self.timeout_sec_values)

    def get_timeout_sec_8(self):
        return self.get_value(7, self.timeout_sec_values)

    def get_timeout_sec_9(self):
        return self.get_value(8, self.timeout_sec_values)

    def get_value(self, level, values):
        '''
        Fetch the value for the given level from given possible values
        :param level:
        :param values:
        :return:
        '''
        with self.lock:
            idx = level + self.adjust
            idx = max(0, min(idx, self.bound))
            return values[idx]

    def update(self, adjust_level):
        '''
        Set new adjustment
        :param adjust_level:  + to speed up, - to slow down
        :return:
        '''
        with self.lock:
            self.adjust = -adjust_level


class IPList(object):
    '''
    A class to contain a range of IPs
    '''

    def __init__(self, ip_list):
        '''
        Constructor
        '''

        toks = ip_list.split(',')
        self.ip_list = []
        for tok in toks:
            if '-' in tok:
                (ip_min, ip_max) = tok.split('-')
                ip_pref = ip_min[:ip_min.rindex('.') + 1]
                ip_min_index = int(ip_min[ip_min.rindex('.') + 1:])
                ip_max_index = int(ip_max) + 1
                for i in range(ip_min_index, ip_max_index):
                    self.ip_list.append(ip_pref + str(i))
            else:
                self.ip_list.append(tok)

    def next_ip(self):
        '''
        Fetch the next available IP
        '''
        if len(self.ip_list) > 0:
            return self.ip_list.pop()
        else:
            None

    def use_static_ip(self):
        '''
       If this container is not empty then use IPs from it
        '''
        return len(self.ip_list) > 0


class Env(object):
    '''
    Test env utility
    '''

    def __init__(self, params):
        '''
        Constructor
        '''

    @staticmethod
    def getRootFolder():
        '''
        Fetch the folder where this deployment script is run from
        '''
        return os.path.dirname(os.path.abspath(__file__))


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


class DisableLog(logging.Filter):
    def __init__(self, disable_list=[]):
        self.disable_list = disable_list

    def filter(self, record):
        return True not in [d in record.msg for d in self.disable_list]


class Log(object):
    '''
    Logging utility
    '''
    stdout = sys.stdout
    stderr = sys.stderr

    def __init__(self, params):
        '''
        Constructor
        '''

    @staticmethod
    def set_interactive(level):
        '''
        Set console logging for interactive mode
        :param level: 'debug' for debug level
        :return:
        '''
        root = logging.getLogger()
        if len(root.handlers) > 0:
            del root.handlers[:]
        logging.basicConfig(level=logging.DEBUG if level.lower() == 'debug'
                                    else logging.INFO,
                            format='%(asctime)-15s [%(levelname)-5s]'
                                   + ' [%(filename)s:%(lineno)s %(funcName)s()]'
                                   + ' [T-%(thread)-5d] %(message)s')

    @staticmethod
    def setup(root_dir, log_file_name=None, log_filters=[]):
        '''
        Create the log folder if needed
        @param main_script:
        '''
        DETAIL_FORMAT = r'%(asctime)-15s [%(levelname)-5s] ' \
                        r'[%(filename)s,%(lineno)d] [T-%(thread)-5d] ' \
                        r'%(message)s'
        BRIEF_FORMAT = r'%(message)s'

        log_dir = os.path.join(root_dir, ERAConstants.LOG_DIR)
        File.create_folder(log_dir)
        log_conf = os.path.join(root_dir, ERAConstants.LOG_CONF)

        logging.config.fileConfig(log_conf)
        logger = logging.getLogger()
        h1 = None
        h2 = None
        if log_file_name:
            log_file_name = os.path.join(log_dir, log_file_name)
        for h in logger.handlers:
            # override the log handler to customize log file name
            if isinstance(h, logging.handlers.RotatingFileHandler):
                if not log_file_name:
                    log_file_name = h.baseFilename
                    last_dot = log_file_name.rindex('.')
                    log_file_tmp = log_file_name[:last_dot] + '-' \
                                   + String.time_stamp()
                    log_file_tmp_debug = log_file_tmp + '-debug'
                    log_file_tmp += log_file_name[last_dot:]
                    log_file_tmp_debug += log_file_name[last_dot:]
                else:
                    log_file_tmp = log_file_name + '.log'
                    log_file_tmp_debug = log_file_name + '-debug.log'

                h1 = RotatingFileHandler(log_file_tmp, h.mode, h.maxBytes,
                                         h.backupCount)
                h1.formatter = logging.Formatter(DETAIL_FORMAT) \
                    if h.level == 10 else logging.Formatter(BRIEF_FORMAT)
                h1.level = h.level
                logger.addHandler(h1)

                # INFO=20 DEBUG=10: add a debug log if logging.conf's
                # level is info
                if h.level == 20:
                    h2 = RotatingFileHandler(log_file_tmp_debug, h.mode,
                                             h.maxBytes, h.backupCount)
                    h2.formatter = logging.Formatter(DETAIL_FORMAT)
                    h2.level = 10
                    logger.addHandler(h2)

                logger.removeHandler(h)
                break

        for h in logger.handlers:
            h.addFilter(DisableLog(log_filters))

        if type(sys.stdout) is StreamToLogger:
            return
        stdout_logger = logging.getLogger('STDOUT')
        sl = StreamToLogger(stdout_logger, logging.DEBUG)
        sys.stdout = sl

        stderr_logger = logging.getLogger('STDERR')
        sl = StreamToLogger(stderr_logger, logging.WARN)
        sys.stderr = sl

    @staticmethod
    def start_brief_log():
        '''
        This is used to log only the time stamp.
        This is used at the end of a test run and when we need to print out the
        test result summary, we don't want to print out the complete log line.

        E.g. 2015-07-10 03:03:06,765 Runlist name: Demo runlist
        '''
        logger = logging.getLogger()
        h1 = None
        new_handlers = []
        old_handlers = []
        for h in logger.handlers:
            if isinstance(h, logging.handlers.RotatingFileHandler):
                h1 = RotatingFileHandler(h.baseFilename, h.mode, h.maxBytes,
                                         h.backupCount)
            else:
                h1 = StreamHandler()

            h1.formatter = Formatter(fmt='%(asctime)-15s %(message)s')
            h1.level = h.level
            new_handlers.append(h1)
            old_handlers.append(h)

        for h in old_handlers:
            logger.removeHandler(h)

        for h in new_handlers:
            logger.addHandler(h)

    @staticmethod
    def get_label(s, width=80):
        '''
        Create a label in the form of a list of string.

        The label may look like the following:

        2015-07-10 03:03:06,762 *********************************
        2015-07-10 03:03:06,763 ** *** Test Result Summary *** **
        2015-07-10 03:03:06,763 *********************************

        @param s:
        @param width:
        '''
        MARGIN = 6
        l = len(s)
        lines = []
        if l > width:
            s1 = '*' * (width + MARGIN)
            lines.append(s1)
            while l > width:
                lines.append('** ' + s[:width] + ' **')
                s = s[width:]
                l = len(s)

            if l > 0:
                sp = ' ' * (width - l)
                lines.append('** ' + s + sp + ' **')
            lines.append(s1)
        else:
            s1 = '*' * (l + MARGIN)
            lines.append(s1)
            lines.append('** ' + s + ' **')
            lines.append(s1)
        return lines

    @staticmethod
    def label_debug(s, width=80):
        '''
        Log the label.

        This first obtains the label lines from get_label then send them to
        the log.

        @param s:
        @param width:
        '''
        Log.label(s, width, True)

    @staticmethod
    def label(s, width=80, debug=False):
        '''
        Log the label.

        This first obtains the label lines from get_label then send them to
        the log.

        @param s:
        @param width:
        '''
        lines = Log.get_label(s, width)
        for line in lines:
            if debug:
                logging.debug(line)
            else:
                logging.info(line)

    @staticmethod
    def log_and_throw(message, exception=None):
        '''
        Log a message and throw an exception

        @param message:
        @param exception:
        '''
        logging.error(message)
        if exception:
            raise exception
        else:
            raise Exception(message)

    @staticmethod
    def reset_stds():
        sys.stdout = Log.stdout
        sys.stderr = Log.stderr

    @staticmethod
    def table(dat, headers):
        '''
        print dat in a table
        :param dat: a list of dictionaries, where keys map to tuples in headers
        :param headers: a list of tuples, where the first element in each tuple
        maps to the keys in dat and the second element is printed out as column
        header
        :return:
        '''

        max_widths, data_copy, final = {}, [dict(headers)] + list(dat), ''
        a, asc_s, asc_t, asc_p, asc_h = '-', \
                                        ' | ', \
                                        '-+-', \
                                        '| %s |\n', \
                                        '+-%s-+\n'

        for col in data_copy[0].keys():
            max_widths[col] = max([len(str(row[col])) for row in data_copy])
        cols_order = [tup[0] for tup in headers]

        def leftright(col, value):
            if type(value) == int:
                return str(value).rjust(max_widths[col])
            else:
                return value.ljust(max_widths[col])

        for idx, row in enumerate(data_copy):
            row_str = asc_s.join([leftright(col, row[col])
                                  for col in cols_order])
            final += asc_p % row_str

            if (data_copy.index(row) == 0 or
                data_copy.index(row) == (len(data_copy) - 1)):
                line = asc_t.join([a * max_widths[col] for col in cols_order])
                final += asc_h % line

        logging.info('\n\n' + final)


class File(object):
    '''
    File utility
    '''

    def __init__(self, params):
        '''
        Constructor
        '''

    @staticmethod
    def create_sub_folder(parent_folder, folder_name):
        '''
        Create given folder name under given folder
        :param parent_folder:
        :param folder_name:
        :return:
        '''
        if parent_folder:
            target_folder = os.path.join(parent_folder, folder_name)
        else:
            target_folder = folder_name

        try:
            os.makedirs(target_folder)
        except OSError:
            if not os.path.isdir(target_folder):
                raise

    @staticmethod
    def create_script_folder(main_script, folder_name):
        '''
        Create a folder under the main script folder
        @param main_script: a main script
        @param folder_name: name of a folder to create
        '''
        parent_dir = os.path.dirname(os.path.abspath(main_script))
        File.create_sub_folder(parent_dir, folder_name)

    @staticmethod
    def create_folder(folder_name):
        '''
        Create given folder
        :param folder_name:
        :return:
        '''
        File.create_sub_folder(None, folder_name)

    @staticmethod
    def down_load(url, destination):
        '''
        Download a file from a given URL
        @param url: source URL
        @param destination: destination path
        '''
        MAX_RETRY = Timings().get_max_retry_attempt_2()
        retries = 0
        while True:
            try:
                r = requests.get(url, stream=True)
                if r.status_code == 200:
                    with open(destination, 'wb') as f:
                        for chunk in r.iter_content(65536):
                            f.write(chunk)
                    return
                else:
                    logging.warn('failed to download ' + url + ' error '
                                 + str(r.status_code))
                    raise Exception('failed to download ' + url + ' error '
                                    + str(r.status_code))

            except:
                if retries < MAX_RETRY:
                    retries += 1
                    logging.debug('re-downloading ('
                                  + str(retries) + '/' + str(MAX_RETRY)
                                  + ') ' + str(url))
                else:
                    logging.warn('failed to download ' + str(url))
                    logging.warn(sys.exc_info()[0])
                    raise

    @staticmethod
    def copy(src, dst):
        '''
        Copy file from src to dst
        @param src:
        @param dst:
        '''
        shutil.copy2(src, dst)

    @staticmethod
    def get_latest(file_path, index_to_fetch=1):
        '''
        Fetch the most recent modified folder
        :param file_path:
        :param index_to_fetch:
        :return:
        '''
        ps = file_path.split('**')
        tmp = ''
        for i in ps:
            if tmp == '':
                tmp += i
            else:
                tmp += '*'
                if i != '':
                    tmp += i[:i.index(os.sep)]
                gs = glob.glob(tmp)
                gs.sort()
                if 'System' in gs[-1]:
                    if len(gs) == index_to_fetch:
                        index_to_fetch -= 1
                    elif len(gs) < index_to_fetch:
                        return None
                    tmp = gs[-1 - index_to_fetch]
                else:
                    tmp = gs[-index_to_fetch]
                if i != '':
                    tmp += os.sep + i[i.index(os.sep) + 1:]

        rets = glob.glob(tmp)
        rets.sort(key=lambda x: os.path.getctime(x))
        return rets[-1]

    @staticmethod
    def create_any_folder(folder_path):
        '''
        Create given folder
        :param folder_path:
        :return:
        '''
        if not os.path.exists(folder_path):
            logging.info('Creating folder ' + folder_path)
            os.makedirs(folder_path)

    @staticmethod
    def zip(src, dst):
        '''
        Zip given source to given destination
        :param src:
        :param dst:
        :return:
        '''
        logging.info('zipping files in ' + src)
        zf = zipfile.ZipFile("%s.zip" % (dst), "w", zipfile.ZIP_DEFLATED)
        abs_src = os.path.abspath(src)
        for dirname, subdirs, files in os.walk(src):
            for filename in files:
                absname = os.path.abspath(os.path.join(dirname, filename))
                arcname = absname[len(abs_src) + 1:]
                zf.write(absname, arcname)
        zf.close()

    @staticmethod
    def unzip(src, destination=None):
        '''
        Unzip a file
        :param src:
        :return:
        '''
        logging.debug('unzipping ' + src)
        z = zipfile.ZipFile(src, 'r')
        z.extractall(path=destination)
        z.close()

    @staticmethod
    def copy_folder(src, dst):
        '''
        Copy given source folder to given destination
        :param src:
        :param dst:
        :return:
        '''
        msg = 'copying folder ' + src + ' to ' + dst + '...'
        logging.debug(msg)
        shutil.copytree(src, dst)
        logging.debug(msg + ' done.')

    @staticmethod
    def delete_folder(folder_path):
        '''
        Delete the given folder
        :param folder_path:
        :return:
        '''
        msg = 'deleteing folder ' + folder_path + '...'
        logging.debug(msg)
        shutil.rmtree(folder_path)


class ERAConstants(object):
    '''
    This contains all test constants.
    '''

    def __init__(self, params):
        '''
        Constructor
        '''

    LOG_CONF = 'logging.conf'
    LOG_DIR = 'logs'
    DT_SVC_ENDPOINT = '/dt-rest/v100/'
    DT_SVC_PORT = 443


class Validation(object):
    '''
    Test param validation utility.
    This should be used to validate test params to ensure that all prerequisite
    params are valid before continue with the test execution.
    '''

    def __init__(self, params):
        '''
        Constructor
        '''

    @staticmethod
    def validate_param(param, message):
        '''
        Validate given param.
        If the param is invalid then log and throw a new exception with the
        given
        error message.
        @param param:
        @param message:
        '''
        if not param:
            Log.log_and_throw(message)


class String(object):
    '''
    String utilities
    '''

    def __init__(self, params):
        '''
        Constructor
        '''

    @staticmethod
    def trim_quotes(s):
        '''
        Remove double quotes from start and end of a string
        @param s:
        '''
        if s.endswith('"'):
            s = s[:-1]
        if s.startswith('"'):
            s = s[1:]
        return s

    @staticmethod
    def random(size=8):
        '''
        Generate a random string of given size
        @param size:
        '''
        char_set = string.ascii_uppercase + string.digits
        return ''.join(random.choice(char_set) for _ in range(size))

    @staticmethod
    def is_true(val):
        '''
        Parse boolean
        :param val:
        :return:
        '''
        return val and val.upper() in ['TRUE', 'T', 'YES', 'Y']

    @staticmethod
    def to_valid_json_str(rs):
        '''
        Reformat to valid json
        :param rs:
        :return:
        '''
        rs = rs.replace("u'", "\"")
        rs = rs.replace("'", "\"")
        return rs

    @staticmethod
    def format_elapsed(t):
        '''
        Format time interval
        :param t:
        :return:
        '''
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return "{:0>2}:{:0>2}:{:05.2f}".format(int(h), int(m), int(s))

    @staticmethod
    def format_time_stamp(t):
        '''
        Format time stamp
        :param t:
        :return:
        '''
        return datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def trim_enum(v):
        '''
        Trim enums
        :param v:
        :return:
        '''
        s = str(v)
        r = s.split('.')[1]
        return r

    @staticmethod
    def to_epoch(t):
        '''
        convert to epoch
        :param t:
        :return:
        '''
        d = parser.parse(t)
        d = d.replace(tzinfo=None)
        e = datetime.utcfromtimestamp(0)
        delta = d - e
        return int(1000 * delta.total_seconds())

    @staticmethod
    def to_string(obj, depth=4, l=""):
        '''
        Convert object to string
        :param obj:
        :param depth:
        :param l:
        :return:
        '''
        # fall back to repr
        if depth < 0:
            return repr(obj)
        # expand/recurse dict
        if isinstance(obj, dict):
            name = ""
            objdict = obj
        else:
            # if basic type, or list thereof, just print
            canprint = lambda o: isinstance(o, (
                long, int, float, str, unicode, bool,
                types.NoneType, types.LambdaType))
            try:
                if canprint(obj) or sum(not canprint(o) for o in obj) == 0:
                    return repr(obj)
            except TypeError, e:
                pass
            # try to iterate as if obj were a list
            try:
                return "[\n" + "\n".join(l + String.to_string(k,
                                                              depth=depth
                                                                        - 1,
                                                              l=l + "  ")
                                         + ","
                                         for k in obj) + "\n" + l + "]"
            except TypeError, e:
                # else, expand/recurse object attribs
                name = (hasattr(obj, '__class__') and obj.__class__.__name__
                        or type(obj).__name__)
                objdict = {}
                for a in dir(obj):
                    if a[:2] != "__" and (not hasattr(obj, a) \
                                                  or not hasattr(
                            getattr(obj, a), '__call__')):
                        try:
                            objdict[a] = getattr(obj, a)
                        except Exception, e:
                            objdict[a] = str(e)
        return name + "{\n" + "\n".join(l
                                        + repr(k) + ": " + String.to_string(
            v, depth=depth - 1, l=l + "  ")
                                        + "," for k, v in
                                        objdict.iteritems()) + "\n" + l + "}"

    @staticmethod
    def time_stamp():
        '''
        Fetch the time stamp
        :return:
        '''
        return datetime.strftime(datetime.now(), '%Y_%m_%d_%H%M%S')

    @staticmethod
    def to_date(val):
        '''
        Parse date
        :param val:
        :return:
        '''
        return parse(val)

def merge_two_maps(a, b):
    '''
        merges b into a
    '''
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_two_maps(a[key], b[key])
            else :
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a

class Constants:
    ERA_AGENT_PRODUCT_CODE = '82B0A2CD-AAAF-4D2E-A2FC-6959201F1CBE'
    GET_ADMIN_ACCESS_TOKEN = "/SAAS/API/1.0/REST/auth/system/login"
    GET_ACCESS_TOKEN = "/SAAS/API/1.0/oauth2/token?grant_type=client_credentials"
    CREATE_AUTH_CLIENT_ID = "/SAAS/jersey/manager/api/oauth2clients"
    GET_USER_ACCESS_TOKEN = "/SAAS/API/1.0/oauth2/token"
    VIDM_AGENT_PORT = "443"
    OAUTH_CLIENT= "/SAAS/jersey/manager/api/oauth2clients/"
    VERIFY_CONNECTOR = "/SAAS/jersey/manager/api/connectormanagement/connectorinstances/"
    CREATE_CONNECTOR = "/SAAS/jersey/manager/api/connectormanagement/connectors/"
    GET_ACTIVATION_TOKEN = "/generateactivationtoken"
    ACTIVATE_CONNECTOR = "/hc/API/1.0/REST/connectormanagement/connector/activate/"
    CREATE_DIRECTORY = "/SAAS/jersey/manager/api/connectormanagement/directoryconfigs/"
    DIR_SYNC_DRYRUN = "/syncprofile/dryrun"
    DIR_SYNC = "/syncprofile/sync"
    CREATE_ADMIN = "/SAAS/jersey/manager/api/tenants/tenant"
    HPQC_URL = "https://quality-api.eng.vmware.com:8443/QCIntgrt/rest/END_USER_COMP/DESKTOP"
    HPQC_API_KEY = "U56EWCQJz4usnGxkHE00ehf4hNsC45XZ"
    LINK_CON_DIR = "/associatedirectory"
    CONFIG_VIEW_VIDM1 = "/hc/t/"
    CONFIG_VIEW_VIDM2= "/admin/viewpools/"
    SYNC_VIEW_POOLS1 = "/hc/"
    SYNC_VIEW_POOLS2 = "/admin/viewpools/sync-now/"
    GET_WORKER_TENANT_ID = "/recognize"
    CONFIG_CPA_POOLS1 = "API/1.0/REST/"
    CONFIG_CPA_POOLS2 = "viewcpa/config?isAjax=true"
    GET_ALL_GROUPS1 = "/directorygroups"
    ADD_GROUPS_TO_DIR1 = "/syncprofile"