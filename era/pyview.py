'''
Created on Oct 9, 2015

@author: nguyenc
'''

import abc
import base64
from collections import deque as stack
import logging
from datetime import datetime
import time

from net import ISession
from util import String
from util import Validation
from core import Suds
from core import MOR
from util import Timings


class UserStats(object):
    '''
    User status container
    '''

    def __init__(self):
        '''
        Constructor
        '''
        self.client_logon_time = 0
        self.broker_logon_time = 0
        self.windows_logon_time = 0
        self.windows_run_time = 0
        self.client_broker_sec_difference = 0
        self.client_desktop_sec_difference = 0
        self.desktop_vm = None

    def set_desktop_vm(self, val):
        '''
        Set the desktop vm name
        :param val:
        :return:
        '''
        self.desktop_vm = val

    def get_desktop_vm(self):
        '''
        Fetch the desktop vm name
        :return:
        '''
        return self.desktop_vm

    def set_client_broker_sec_difference(self, val):
        '''
        Set the time difference b/w client and broker VMs
        :param val:
        :return:
        '''
        self.client_broker_sec_difference = val

    def set_client_desktop_sec_difference(self, val):
        '''
        Set the time difference b/w client and desktop VMs
        :param val:
        :return:
        '''
        self.client_desktop_sec_difference = val

    def set_client_logon_time(self, val):
        '''
        Set the logon time as the time when the View client is launched on
        client
        VMs
        :param val:
        :return:
        '''
        self.client_logon_time = val

    def set_broker_logon_time(self, val):
        '''
        Set the logon time as reported by the broker
        :param val:
        :return:
        '''
        self.broker_logon_time = val

    def get_broker_request_time(self):
        '''
        Calculate the interval for a logon request to initiates from the client
        VM to when the broker reports the logon
        :return:
        '''
        if isinstance(self.broker_logon_time, int):
            broker_logon_time = self.broker_logon_time
        else:
            broker_logon_time = String.to_epoch(self.broker_logon_time)
            # broker_logon_time = self.broker_logon_time
        if isinstance(self.client_logon_time, int):
            client_logon_time = self.client_logon_time
        else:
            client_logon_time = String.to_epoch(self.client_logon_time)

        return broker_logon_time - client_logon_time \
               - 1000 * self.client_broker_sec_difference

    def set_windows_logon_time(self, val):
        '''
        Set the logon time as reported by Windows OS
        :param val:
        :return:
        '''
        if not val.startswith('user'):
            self.windows_logon_time = 1000 * float(val)

    def set_windows_run_time(self, val):
        '''
        Set the time as set by the 'SetLoginTime' app as login time. This app
        is triggered using the Run registry.
        :param val:
        :return:
        '''
        logging.debug('Using windows desktop ready time.')
        self.windows_run_time = val

    def get_total_logon_time(self):
        '''
        Set the total logon time from View client launch to when Windows reports
        the logon
        :return:
        '''
        if isinstance(self.windows_run_time, int):
            windows_run_time=self.windows_run_time
        else:
            windows_run_time = String.to_epoch(self.windows_run_time)
        if isinstance(self.client_logon_time, int):
            client_logon_time = self.client_logon_time
        else:
            client_logon_time = String.to_epoch(self.client_logon_time)

        return max(0, windows_run_time - client_logon_time - 1000 *
                   self.client_desktop_sec_difference)

    def get_stat_for_logging(self):
        '''
        Fetch the logon statistics
        :return:
        '''
        return str(self.client_logon_time) + ',' + str(
            self.broker_logon_time) + ',' \
               + str(self.get_broker_request_time()) + ',' \
               + str(self.windows_run_time) + ',' \
               + str(self.get_total_logon_time())


class ViewBase(object):
    '''
    Base class for View helpers
    '''

    def __init__(self, sud):
        '''
        Constructor
        '''
        self.sud = sud
        self.viewapi = sud.get_svc()
        self.mor = MOR.get_mor(self.get_mor_type())

    @abc.abstractmethod
    def get_mor_type(self):
        pass

    def get_object(self, object_type):
        '''
        Fetch vim object of given type
        :param object_type:
        :return:
        '''
        return self.sud.get_object(object_type)

    def set_value_type(self, v_type):
        '''
        Override the default no-type type of a member in the request
        :param v_type:
        :return:
        '''
        self.sud.set_value_type(v_type)

    def get_host(self):
        return self.sud.host


class VC(ViewBase):
    '''
    Helper for VC serice APIs
    '''

    def get_mor_type(self):
        return 'VirtualCenter'

    def list(self):
        '''
        Fetch a list of VC that have been added to View
        :return:
        '''
        return self.viewapi.VirtualCenter_List(self.mor)

    def get_id(self, vc_host):
        '''
        Fetch the View ID object of given VC
        :param vc_host:
        :return:
        '''
        vc_list = self.list()
        ret = None
        if vc_list:
            for vc in vc_list:
                if vc.serverSpec.serverName.lower() == vc_host.lower():
                    ret = vc.id
                    break
        return ret

    def get_template_by_name(self, vc_id, template_name):
        '''
        Fetch the template object given the template name and VC ID
        :param vc_id:
        :param template_name:
        :return:
        '''
        images = self.viewapi.VmTemplate_List(MOR.get_mor('VmTemplate'),
                                               vc_id)
        for image in images:
            if image.name.lower() == template_name.lower():
                return image

        return None

    def get_template_id(self, vc_id, template_name):
        '''
        Fetch the template ID object of given template and VC ID
        :param vc_id:
        :param template_name:
        :return:
        '''
        image = self.get_template_by_name(vc_id, template_name)
        if image:
            return image.id

        return None

    def get_template_dc_id(self, vc_id, template_name):
        '''
        Fetch the View datacenter ID object given a template name and VC ID object
        :param vc_id:
        :param template_name:
        :return:
        '''
        image = self.get_template_by_name(vc_id, template_name)
        if image:
            return image.datacenter

        return None

    def get_vm_by_name(self, vc_id, vm_name):
        '''
        Fetch the VM object given the VM name and VC ID
        :param vc_id:
        :param vm_name:
        :return:
        '''
        images = self.viewapi.BaseImageVm_List(MOR.get_mor('BaseImageVm'),
                                               vc_id)
        for image in images:
            if image.name.lower() == vm_name.lower():
                return image

        return None

    def get_vm_id(self, vc_id, vm_name):
        '''
        Fetch the VM ID object of given VM and VC ID
        :param vc_id:
        :param vm_name:
        :return:
        '''
        image = self.get_vm_by_name(vc_id, vm_name)
        if image:
            return image.id

        return None

    def get_vm_dc_id(self, vc_id, vm_name):
        '''
        Fetch the View datacenter ID object given a VM name and VC ID object
        :param vc_id:
        :param vm_name:
        :return:
        '''
        image = self.get_vm_by_name(vc_id, vm_name)
        if image:
            return image.datacenter

        return None

    def get_vm_ss_id(self, vc_id, vm_name, ss_path):
        '''
        Fetch the snapshot ID object of the given VM and SS path
        :param vc_id:
        :param vm_name:
        :param ss_path:
        :return:
        '''
        image_id = self.get_vm_id(vc_id, vm_name)
        if not image_id:
            raise Exception('Image ' + vm_name + ' is not found')
        image_ss_list = self.viewapi.BaseImageSnapshot_List(MOR.get_mor(
            'BaseImageSnapshot'), image_id)
        if not image_ss_list:
            raise Exception('Image ' + vm_name + ' has no snapshot.')

        for image_ss in image_ss_list:
            if image_ss.path.lower() == ss_path.lower():
                return image_ss.id

        return None

    def __search(self, root, expected_value, compare, returner):
        '''
        Internal method to search for a VIM object
        :param root:
        :param expected_value:
        :param compare:
        :param returner:
        :return:
        '''
        s = stack([root])
        while len(s):
            e = s.pop()
            if compare(e, expected_value):
                return returner(e)

            if 'children' in e:
                for child in e.children:
                    s.append(child)
        return None

    def get_vm_folder_id(self, dc_id, folder_name):
        '''
        Fetch the folder ID object for the given folder name and DC ID
        :param dc_id:
        :param folder_name:
        :return:
        '''
        t = self.viewapi.VmFolder_GetVmFolderTree(MOR.get_mor('VmFolder'),
                                                  dc_id)
        if not folder_name:
            return t.id

        return self.__search(t, folder_name,
                             lambda x,
                                    y: x.folderData.name.lower() == y.lower(),
                             lambda x: x.id)

    def get_host_or_cluster_id(self, dc_id, host_or_cluster_name):
        '''
        Fetch the host or cluster ID object given the name
        :param dc_id:
        :param host_or_cluster_name:
        :return:
        '''
        t = self.viewapi.HostOrCluster_GetHostOrClusterTree(MOR.get_mor(
            'HostOrCluster'), dc_id)
        return self.__search(t.treeContainer, host_or_cluster_name,
                             lambda x, y: x.info.name.lower() == y.lower()
                             if 'info' in x else x.name.lower() ==
                                                 y.lower(),
                             lambda x: x.info.id)

    def get_resource_pool_id(self, host_or_cluster_id, resource_pool_name):
        '''
        Fetch the resource pool ID object given the name
        :param host_or_cluster_id:
        :param resource_pool_name:
        :return:
        '''
        t = self.viewapi.ResourcePool_GetResourcePoolTree(MOR.get_mor(
            'ResourcePool'), host_or_cluster_id)

        if not resource_pool_name:
            return t.id

        return self.__search(t, resource_pool_name,
                             lambda x,
                                    y: x.resourcePoolData.name.lower() ==
                                       y.lower(),
                             lambda x: x.id)
    def get_network_label_id(self, host_or_cluster_id, network):
        '''
        Fetch the network Id of the given network label
        :param host_or_cluster_id:
        :param network:
        :return:
        '''
        networks = self.viewapi.NetworkLabel_ListByHostOrCluster(MOR.get_mor('NetworkLabel'), host_or_cluster_id)
        for network_label in networks:
            if network.lower() in network_label.data.name.lower():
                return network_label.id
        return None

    def get_nic_id(self, base_image_ss_id, nic):
        '''
        Get the NIc Id
        :return:
        '''
        nics = self.viewapi.NetworkInterfaceCard_ListBySnapshot(MOR.get_mor('NetworkInterfaceCard'), base_image_ss_id)
        for nic_tmp in nics:
            if nic.lower() in nic_tmp.data.name.lower():
                return nic_tmp.id
        return None

    def get_networks(self, host_or_cluster_id, networks, base_image_ss_id, nic):
        '''
        Fetch the networks for desktops
        :param host_or_cluster_id:
        :param networks:
        :return:
        '''
        network_list = networks.split(';')
        rets = []
        label = []
        nic_settings = self.sud.get_object('ns0:DesktopNetworkInterfaceCardSettings')
        nic_settings.nic = self.get_nic_id(base_image_ss_id, nic)
        for network in network_list:
            nw_label_id = self.get_network_label_id(host_or_cluster_id, network)
            Validation.validate_param(nw_label_id, 'Network ' + network + ' is not found')
            net_label_assignment_spec = self.sud.get_object('ns0:DesktopNetworkLabelAssignmentSpec')
            net_label_assignment_spec.enabled = True
            net_label_assignment_spec.networkLabel = nw_label_id
            net_label_assignment_spec.maxLabelType = 'UNLIMITED'
            net_label_assignment_spec.maxLabel = 5
            label.append(net_label_assignment_spec)
        nic_settings.networkLabelAssignmentSpecs = label
        rets.append(nic_settings)
        return rets

    def get_farm_networks(self, host_or_cluster_id, networks, base_image_ss_id, nic):
        '''
        Fetch the networks for Farms
        :param host_or_cluster_id:
        :param networks:
        :return:
        '''
        network_list = networks.split(';')
        rets = []
        label = []
        nic_settings = self.sud.get_object('ns0:FarmNetworkInterfaceCardSettings')
        nic_settings.nic = self.get_nic_id(base_image_ss_id, nic)
        for network in network_list:
            nw_label_id = self.get_network_label_id(host_or_cluster_id, network)
            Validation.validate_param(nw_label_id, 'Network ' + network + ' is not found')
            net_label_assignment_spec = self.sud.get_object('ns0:FarmNetworkLabelAssignmentSpec')
            net_label_assignment_spec.enabled = True
            net_label_assignment_spec.networkLabel = nw_label_id
            net_label_assignment_spec.maxLabelType = 'UNLIMITED'
            net_label_assignment_spec.maxLabel = 5
            label.append(net_label_assignment_spec)
        nic_settings.networkLabelAssignmentSpecs = label
        rets.append(nic_settings)
        return rets
    def get_datastore_id(self, host_or_cluster_id, datastore_path):
        '''
        Fetch the datastore ID object given the datastore path
        :param host_or_cluster_id:
        :param datastore_path:
        :return:
        '''
        datastores = self.viewapi.Datastore_ListDatastoresByHostOrCluster(MOR
            .get_mor(
            'Datastore'), host_or_cluster_id)
        for datastore in datastores:
            if datastore_path.lower() in datastore.datastoreData.path.lower():
                return datastore.id
        return None

    ## [Moderate,OS,data]/vdi/host/agentCluster/view_fs_22_1TB;...
    def get_datastores(self, host_or_cluster_id, datastores, disk_type):
        '''
        Fetch a list of datastore settings
        :param host_or_cluster_id:
        :param datastores:
        :param disk_type:
        :return:
        '''
        datastore_list = datastores.split(';')
        rets = []
        for datastore in datastore_list:
            if disk_type in datastore.lower():
                attrib, ds_path = datastore.split(']')
                ds_id = self.get_datastore_id(host_or_cluster_id, ds_path)
                Validation.validate_param(ds_id, 'Datastore ' + ds_path
                                          + ' is not found')
                overcommit = attrib.split(',')[0][1:]
                ds_setting = self.sud \
                    .get_object('ns0:DesktopVirtualCenterDatastoreSettings')
                ds_setting.storageOvercommit = overcommit
                ds_setting.datastore = ds_id
                rets.append(ds_setting)
        return rets

    def get_os_datastores(self, host_or_cluster_id, datastores):
        '''
        Fetch a list of datastore settings
        :param host_or_cluster_id:
        :param datastores:
        :return:
        '''
        return self.get_datastores(host_or_cluster_id, datastores, 'os')

    def get_os_datastores_for_farm(self, host_or_cluster_id, datastores):
        '''
        Fetch a list of datastore settings for Farm
        :param host_or_cluster_id:
        :param datastores:
        :return:
        '''
        datastore_list = datastores.split(';')
        rets = []
        for datastore in datastore_list:
            if 'os' in datastore.lower():
                attrib, ds_path = datastore.split(']')
                ds_id = self.get_datastore_id(host_or_cluster_id, ds_path)
                Validation.validate_param(ds_id, 'Datastore ' + ds_path
                                          + ' is not found')
                overcommit = attrib.split(',')[0][1:]
                ds_setting = self.sud \
                    .get_object('ns0:FarmVirtualCenterDatastoreSettings')
                ds_setting.storageOvercommit = overcommit
                ds_setting.datastore = ds_id
                rets.append(ds_setting)
        return rets

    def get_persistent_datastores(self, host_or_cluster_id, datastores):
        '''
        Fetch a list of persistent datastores
        :param host_or_cluster_id:
        :param datastores:
        :return:
        '''
        return self.get_datastores(host_or_cluster_id, datastores, 'data')

    def get_replica_datastore_id(self, host_or_cluster_id, datastores):
        '''
        Fetch a list of replica datastores
        :param host_or_cluster_id:
        :param datastores:
        :return:
        '''
        datastore_list = datastores.split(';')
        for datastore in datastore_list:
            if 'replica' in datastore.lower():
                attrib, ds_path = datastore.split(']')
                return self.get_datastore_id(host_or_cluster_id, ds_path)
        return None

    def get_customization_spec_id(self, vc_id, spec_name):
        '''
        Fetch the customization spec ID object given the name
        :param vc_id:
        :param spec_name:
        :return:
        '''
        specs = self.viewapi.CustomizationSpec_List(MOR.get_mor(
            'CustomizationSpec'), vc_id)
        for spec in specs:
            if spec.customizationSpecData.name.lower() == spec_name.lower():
                return spec.id
        return None

    def get_view_composer_domain_admin_id(self, vc_id):
        '''
        Fetch the view composer admin ID object given the VC ID
        :param vc_id:
        :return:
        '''
        admin_infos = self.viewapi.ViewComposerDomainAdministrator_List(MOR
            .get_mor(
            'ViewComposerDomainAdministrator'), vc_id)
        if len(admin_infos) > 0:
            return admin_infos[0].id
        else:
            return None

    def create(self, vc_host, vc_port, vc_user, vc_password, composer_host,
               composer_port, composer_user, composer_pwd, composer_type):
        '''
        Add a VC + View Composer combo to View
        :param vc_host:
        :param vc_port:
        :param vc_user:
        :param vc_password:
        :param composer_host:
        :param composer_port:
        :param composer_user:
        :param composer_pwd:
        :param composer_type:
        :return:
        '''
        vc_server_spec = self.sud.get_object('ns0:ServerSpec')
        vc_server_spec.serverName = vc_host
        vc_server_spec.port = vc_port
        vc_server_spec.userName = vc_user
        ss = self.sud.get_object('ns0:SecureString')
        ss.utf8String = base64.b64encode(vc_password.encode('utf-8'))
        vc_server_spec.password = ss
        vc_server_spec.serverType = 'VIRTUAL_CENTER'
        vc_server_spec.useSSL = True
        vc_spec = self.sud.get_object('ns0:VirtualCenterSpec')
        vc_spec.serverSpec = vc_server_spec
        vc_spec.disableVCInventoryLicenseAlarm = True
        cert_data = self.viewapi.Certificate_Validate(
            MOR.get_mor('Certificate'),
            vc_server_spec)
        if cert_data:
            vc_spec.certificateOverride = cert_data.thumbprint

        if composer_type == 'DISABLED':
            composer_server_spec = self.sud.get_object('ns0:ServerSpec')
            composer_spec = self.sud.get_object('ns0:VirtualCenterViewComposerData')
            composer_spec.serverSpec = composer_server_spec
            composer_spec.viewComposerType = composer_type
            vc_spec.viewComposerData = composer_spec
        elif composer_type in ('STANDALONE','LOCAL_TO_VC'):
            composer_server_spec = self.sud.get_object('ns0:ServerSpec')
            composer_server_spec.serverName = composer_host
            composer_server_spec.port = composer_port
            composer_server_spec.userName = composer_user
            ss = self.sud.get_object('ns0:SecureString')
            ss.utf8String = base64.b64encode(composer_pwd.encode('utf-8'))
            composer_server_spec.password = ss
            composer_server_spec.serverType = 'VIEW_COMPOSER'
            composer_server_spec.useSSL = True
            composer_cert_data = self.viewapi.Certificate_Validate(MOR.get_mor(
                'Certificate'), composer_server_spec)
            composer_spec = self.sud.get_object('ns0:VirtualCenterViewComposerData')
            if composer_cert_data:
                composer_spec.certificateOverride = composer_cert_data.thumbprint
            composer_spec.serverSpec = composer_server_spec
            composer_spec.viewComposerType = composer_type
            vc_spec.viewComposerData = composer_spec

        vc_spec.limits.vcProvisioningLimit = 20
        vc_spec.limits.vcPowerOperationsLimit = 50
        vc_spec.limits.viewComposerProvisioningLimit = 12
        vc_spec.limits.viewComposerMaintenanceLimit = 20
        vc_spec.limits.instantCloneEngineProvisioningLimit = 20
        vc_spec.storageAcceleratorData.enabled = False
        vc_spec.seSparseReclamationEnabled = False
        if composer_host:
            logging.debug(self.get_host() + ': adding VC ' + vc_host
                          + ', View Composer ' + composer_host)
        else:
            logging.debug(self.get_host() + ': adding VC ' + vc_host)
        return self.viewapi.VirtualCenter_Create(self.mor, vc_spec)

    def add_composer_domain(self, domain_name, user_name, password, vc_id):
        '''
        Add domain to given VC
        :param domain_name:
        :param user_name:
        :param password:
        :param vc_id:
        :return:
        '''
        domain_base = self.sud.get_object(
            'ns0:ViewComposerDomainAdministratorBase')
        domain_base.domain = domain_name
        domain_base.userName = user_name
        ss = self.sud.get_object('ns0:SecureString')
        ss.utf8String = base64.b64encode(password.encode('utf-8'))
        domain_base.password = ss
        spec = self.sud.get_object('ns0:ViewComposerDomainAdministratorSpec')
        spec.base = domain_base
        spec.virtualCenter = vc_id
        mor = MOR.get_mor('ViewComposerDomainAdministrator')
        logging.debug(self.get_host() + ': adding view composer domain '
                      + domain_name + ' to vc ' + String.to_string(vc_id))
        return self.viewapi.ViewComposerDomainAdministrator_Create(mor, spec)

class InstantCloneDomain(ViewBase):
    '''
    Helper for Instant clone domain related APIs
    '''
    def __init__(self, sud):
        super(InstantCloneDomain, self).__init__(sud)
    def get_ad_domain_id(self, domain_name):
        ad_domain_infos = self.viewapi.ADDomain_List(MOR.get_mor('ADDomain'))
        if not ad_domain_infos:
            raise Exception('ADDomain service did not list any domains')
        for ad_domain_info in ad_domain_infos:
            if ad_domain_info.dnsName.lower() == domain_name.lower():
                return ad_domain_info.id
        return None

    def get_instant_clone_domain_admin_id(self, domain_name):
        iced_admin_infos = \
            self.viewapi.InstantCloneEngineDomainAdministrator_List(MOR\
                .get_mor('InstantCloneEngineDomainAdministrator'))
        for iced_admin_info in iced_admin_infos:
            if iced_admin_info.namesData.dnsName.lower() == domain_name.lower():
                return iced_admin_info.id
        return None

    def add_instant_clone_domain_admin(self, domain_name, user_name, password):
        domain_base = self.sud.get_object('ns0:InstantCloneEngineDomainAdministratorBase')
        ad_domain_id = self.get_ad_domain_id(domain_name)
        domain_base.domain = ad_domain_id
        domain_base.userName = user_name
        ss = self.sud.get_object('ns0:SecureString')
        ss.utf8String = base64.b64encode(password.encode('utf-8'))
        domain_base.password = ss
        spec = self.sud.get_object('ns0:InstantCloneEngineDomainAdministratorSpec')
        spec.base = domain_base
        mor = MOR.get_mor('InstantCloneEngineDomainAdministrator')
        return self.viewapi.InstantCloneEngineDomainAdministrator_Create(mor, spec)


class Apps(ViewBase):
    '''
    Helper for Application Service API
    '''

    def __init__(self, sud):
        super(Apps, self).__init__(sud)
        self.queries = Queries(sud)
        self.vc = VC(sud)
        self.farms = Farms(sud)

    def get_mor_type(self):
        return 'Application'

    def get_app(self, app_id):
        '''
        Fetch summary of given app id
        :param app_id:
        :return:
        '''
        return self.viewapi.Application_Get(self.mor, app_id)

    def query_app(self, query_filter):
        '''
        Search for apps based on the filter
        :param query_filter:
        :return:
        '''
        return self.queries.query(query_filter, 'ApplicationInfo')

    def get_app_id_by_name(self, app_name):
        '''
        Get the app id given its name
        :param app_name:
        :return:
        '''
        query_filter = self.queries \
            .get_equal_filter('data.name', app_name)
        ret = self.query_app(query_filter)

        if not hasattr(ret, 'results'):
            return None
        if len(ret.results) > 1:
            raise Exception('Found more than 1 app pool with name ' + app_name)

        return ret.results[0].id

    def get_farm_id_by_app_name(self, app_name):
        '''
        Get the farm id of the farm to which the app_name belongs to
        :param app_name:
        :return:
        '''
        query_filter = self.queries \
            .get_equal_filter('data.name', app_name)
        ret = self.query_app(query_filter)

        if not hasattr(ret, 'results'):
            return None
        if len(ret.results) > 1:
            raise Exception('Found more than 1 app pool with name ' + app_name)

        return ret.results[0].executionData.farm

    def get_access_group_id(self):
        '''
        Fetch the access group ID
        :return:
        '''
        rets = self.viewapi.AccessGroup_List(MOR.get_mor('AccessGroup'))
        if len(rets) > 0:
            return rets[0].id
        else:
            return None

    def create_app(self, params):
        '''
        Create application pool from the given params
        :param params:
        :return:
        '''
        app_pool_settings_pars = params['pool_settings']
        app_spec = self.sud.get_object('ns0:ApplicationSpec')

        app_data = self.sud.get_object('ns0:ApplicationData')
        app_data.name = app_pool_settings_pars['pool_name']
        app_data.displayName = app_data.name
        app_data.description = app_data.name
        app_data.enabled = True
        app_data.enableAntiAffinityRules = False

        app_spec.data = app_data

        app_exec_data = self.sud.get_object('ns0:ApplicationExecutionData')
        app_exec_data.executablePath = app_pool_settings_pars['pool_path']
        farm_name = app_pool_settings_pars['farm_name']
        app_exec_data.farm = self.farms.get_farm_id_by_name(farm_name)
        app_exec_data.autoUpdateFileTypes = True
        app_exec_data.autoUpdateOtherFileTypes = True

        app_spec.executionData = app_exec_data

        app_id = self.viewapi.Application_Create(self.mor, app_spec)
        logging.debug(self.get_host() + ': Start creating application pool '
                      + app_data.name + ' ID = ' + app_id.id)
        return app_id

    def app_delete_by_name(self, app_name):
        '''
        Delete the app pool by its name
        :param app_name:
        :return:
        '''
        logging.debug(self.get_host() + ': deleting pool ' + app_name)
        self.app_delete(self.get_app_id_by_name(app_name))

    def app_delete(self, app_id):
        '''
        Delete the app pool by its id
        :param app_id:
        :return:
        '''
        self.viewapi.Application_Delete(self.mor, app_id)


class Farms(ViewBase):
    '''
    Helper for Farm Service API
    '''

    def __init__(self, sud):
        super(Farms, self).__init__(sud)
        self.queries = Queries(sud)
        self.vc = VC(sud)
        self.instantclonedomain = InstantCloneDomain(sud)

    def get_mor_type(self):
        return 'Farm'

    def get_summaryview(self, farm_id):
        '''
        Fetch summary of given farm id
        :param farm_id:
        :return:
        '''
        return self.viewapi.Farm_GetSummaryView(self.mor, farm_id)

    def query_farm(self,query_filter):
        '''
        Search for farms based on the filter
        :param query_filter:
        :return:
        '''
        return self.queries.query(query_filter,'FarmSummaryView')

    def get_farm_id_by_name(self, farm_name):
        '''
        Get the farm id given its name
        :param farm_name:
        :return:
        '''
        query_filter = self.queries \
            .get_equal_filter('data.name', farm_name)
        ret = self.query_farm(query_filter)

        if not hasattr(ret, 'results'):
            return None
        if len(ret.results) > 1:
            raise Exception('Found more than 1 farm with name ' + farm_name)

        return ret.results[0].id

    def query_farm_summary_view(self, query_filter):
        '''
        :param query_filter:
        :return:
        '''
        ret = self.queries.create(query_filter, 'FarmSummaryView')
        query_id = ret.id
        rds_servers = []
        rds_server_count = 0
        try:
            while 'results' in ret:
                for mc in ret.results:
                    rds_server_count = mc.data.rdsServerCount
                    rds_servers.append(mc)
                ret = self.queries.next(query_id)
        finally:
            if query_id:
                self.queries.delete(query_id)
        return rds_server_count

    def query_farm_health_info(self, farm_id, rds_server_count):
        '''
        Get the farm health info
        :param farm_id:
        :param rds_server_count
        :return:
        '''
        ret = self.queries.create_without_filter('FarmHealthInfo')
        query_id = ret.id
        rds_servers = []
        count = 0
        try:
            while 'results' in ret:
                for rds_s in ret.results:
                    if rds_s.id.id == farm_id.id:
                        while 'rdsServerHealth' in rds_s:
                            for rdsh_s in rds_s.rdsServerHealth:
                                rds_servers.append(rdsh_s)
                                count += 1
                            if rds_server_count == count:
                                break
                ret = self.queries.next(query_id)
        finally:
            if query_id:
                self.queries.delete(query_id)
        return rds_servers

    def get_farm_rdsh_in_state(self, farm_name, rdsh_state):
        '''
        Get the RDS host status in a farm
        :param farm_name:
        :param rdsh_state:
        :return:
        '''
        farm_id = self.get_farm_id_by_name(farm_name)
        query_filter = self.queries.get_equal_filter('data.name', farm_name)
        rds_server_count = self.query_farm_summary_view(query_filter)
        rds_servers = self.query_farm_health_info(farm_id, rds_server_count)
        ret = []
        for rds_s in rds_servers:
            if rds_s.status == rdsh_state:
                ret.append(rds_s)
        return ret

    def get_farm(self, farm_id):
        '''
        Fetch the farm object given its ID
        :param farm_id:
        :return:
        '''
        return self.viewapi.Farm_Get(self.mor, farm_id)

    def get_access_group_id(self):
        '''
        Fetch the access group ID
        :return:
        '''
        rets = self.viewapi.AccessGroup_List(MOR.get_mor('AccessGroup'))
        if len(rets) > 0:
            return rets[0].id
        else:
            return None

    def create_linked_clone_farm(self, params):
        '''
        Create an automated farm with linked clones
        :param params:
        :return:
        '''
        farm_spec = self.sud.get_object('ns0:FarmSpec')
        farm_spec.type = 'AUTOMATED'

        farm_data = self.sud.get_object('ns0:FarmData')
        farm_settings_pars = params['farm_settings']
        farm_session_settings_pars = params['session_settings']
        farm_protocol_settings_pars = params['protocol_settings']
        vc_settings_pars = params['vc_settings']
        adv_storage_pars = params['advanced_storage_options']
        cust_spec_pars = params['guest_customization']
        storage_optimization_pars = params['storage_optimization']
        farm_data.name = farm_settings_pars['farm_name']
        farm_data.displayName = farm_data.name
        farm_data.accessGroup = self.get_access_group_id()
        farm_data.description = farm_data.name
        farm_data.enabled = True
        farm_data.deleting = False

        farm_session_settings = self.sud.get_object('ns0:FarmSessionSettings')
        farm_session_settings.disconnectedSessionTimeoutPolicy = farm_session_settings_pars['session_disconnect_timeout_policy']
        if farm_session_settings.disconnectedSessionTimeoutPolicy == 'AFTER':
            farm_session_settings.disconnectedSessionTimeoutMinutes = int(farm_session_settings_pars['session_disconnect_timeout'])
        farm_session_settings.emptySessionTimeoutPolicy = farm_session_settings_pars['empty_session_timeout_policy']
        farm_session_settings.emptySessionTimeoutMinutes= int(farm_session_settings_pars['empty_session_timeout'])
        farm_session_settings.logoffAfterTimeout = String.is_true(farm_session_settings_pars['logoff_after_timeout'])
        farm_data.settings = farm_session_settings

        farm_protocol_settings = self.sud.get_object('ns0:FarmDisplayProtocolSettings')
        farm_protocol_settings.defaultDisplayProtocol = farm_protocol_settings_pars['default_protocol']
        farm_protocol_settings.allowDisplayProtocolOverride = String.is_true(farm_protocol_settings_pars['allow_protocol_override'])
        farm_protocol_settings.enableHTMLAccess = String.is_true(farm_protocol_settings_pars['enable_html_access'])
        farm_data.displayProtocolSettings = farm_protocol_settings

        farm_spec.data = farm_data

        farm_auto_spec = self.sud.get_object('ns0:FarmAutomatedFarmSpec')
        farm_auto_spec.provisioningType = 'VIEW_COMPOSER'
        vc = farm_settings_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')
        farm_auto_spec.virtualCenter = vc_id

        farm_naming_spec = self.sud.get_object('ns0:FarmRDSServerNamingSpec')
        farm_naming_spec.namingMethod = 'PATTERN'

        farm_pattern_naming_settings = self.sud.get_object('ns0:FarmPatternNamingSettings')
        farm_pattern_naming_settings.namingPattern = farm_settings_pars['name_prefix']
        farm_pattern_naming_settings.maxNumberOfRDSServers = int(farm_settings_pars['maximum_count'])
        farm_naming_spec.patternNamingSettings = farm_pattern_naming_settings

        farm_auto_spec.rdsServerNamingSpec = farm_naming_spec

        farm_vc_provision_settings = self.sud.get_object('ns0:FarmVirtualCenterProvisioningSettings')
        farm_vc_provision_settings.enableProvisioning = True
        farm_vc_provision_settings.stopProvisioningOnError = String.is_true(
            farm_settings_pars['stop_provision_on_error'])
        farm_vc_provision_settings.minReadyVMsOnVComposerMaintenance = int(farm_settings_pars['min_ready'])

        farm_vc_provisioning_data = self.sud.get_object('ns0:FarmVirtualCenterProvisioningData')
        base_image = vc_settings_pars['vm_name']
        base_image_id = self.vc.get_vm_id(vc_id, base_image)
        Validation.validate_param(base_image_id, 'Base image ' + base_image + ' is not found.')
        farm_vc_provisioning_data.parentVm = base_image_id
        base_image_ss_path = vc_settings_pars['snapshot_path']
        base_image_ss_id = self.vc.get_vm_ss_id(vc_id, base_image,
                                                base_image_ss_path)
        farm_vc_provisioning_data.snapshot = base_image_ss_id
        Validation.validate_param(base_image_ss_id,
                                  'Snapshot ' + base_image_ss_path + ' for base image  ' + base_image + ' is not found.')
        base_image_dc_id = self.vc.get_vm_dc_id(vc_id, base_image)
        Validation.validate_param(base_image_dc_id, 'Datacenter for base image ' + base_image + ' is not found.')
        farm_vc_provisioning_data.datacenter = base_image_dc_id

        vm_folder = vc_settings_pars['folder_name']
        vm_folder_id = self.vc.get_vm_folder_id(base_image_dc_id, vm_folder)
        Validation.validate_param(vm_folder_id, 'Folder ' + vm_folder + ' is not found.')
        farm_vc_provisioning_data.vmFolder = vm_folder_id

        host_or_cluster_name = vc_settings_pars['host_or_cluster_name']
        host_or_cluster_id = self.vc.get_host_or_cluster_id(base_image_dc_id, host_or_cluster_name)
        Validation.validate_param(host_or_cluster_id, 'Host or cluster ' + host_or_cluster_name + ' is not found.')
        farm_vc_provisioning_data.hostOrCluster = host_or_cluster_id

        resource_pool_name = vc_settings_pars['resource_pool_name']
        resource_pool_id = self.vc.get_resource_pool_id(host_or_cluster_id, resource_pool_name)
        Validation.validate_param(resource_pool_id, 'Resource pool ' + resource_pool_name + ' is not found.')
        farm_vc_provisioning_data.resourcePool = resource_pool_id
        farm_vc_provision_settings.virtualCenterProvisioningData = farm_vc_provisioning_data

        farm_vc_storage_settings = self.sud.get_object('ns0:FarmVirtualCenterStorageSettings')

        datastore_paths = vc_settings_pars['datastores']
        ds_settings = self.vc.get_os_datastores_for_farm(host_or_cluster_id,
                                                datastore_paths)
        Validation.validate_param(ds_settings, 'datastores ' + datastore_paths + ' are not found.')
        farm_vc_storage_settings.datastores = ds_settings
        farm_vc_storage_settings.useVSan = String.is_true(storage_optimization_pars['use_vsan'])

        farm_composer_storage_settings = self.sud.get_object('ns0:FarmViewComposerStorageSettings')
        farm_composer_storage_settings.useSeparateDatastoresReplicaAndOSDisks = String.is_true(
            storage_optimization_pars['use_separate_datastore_4_replica_and_os_disks'])
        if farm_composer_storage_settings.useSeparateDatastoresReplicaAndOSDisks:
            farm_composer_storage_settings.replicaDiskDatastore = self.vc \
                .get_replica_datastore_id(host_or_cluster_id, datastore_paths)
        farm_composer_storage_settings.useNativeSnapshots = False

        farm_space_reclaim_settings = self.sud.get_object('ns0:FarmSpaceReclamationSettings')
        farm_space_reclaim_settings.reclaimVmDiskSpace = String.is_true(adv_storage_pars['use_sesparse_disk_format'])
        if farm_space_reclaim_settings.reclaimVmDiskSpace:
            farm_space_reclaim_settings.reclamationThresholdGB = int(adv_storage_pars['sesparse_threshold'])

        farm_composer_storage_settings.spaceReclamationSettings = farm_space_reclaim_settings

        farm_vc_storage_settings.viewComposerStorageSettings = farm_composer_storage_settings
        farm_vc_provision_settings.virtualCenterStorageSettings = farm_vc_storage_settings

        farm_vc_nw_settings = self.sud.get_object('ns0:FarmVirtualCenterNetworkingSettings')
        farm_vc_provision_settings.virtualCenterNetworkingSettings = farm_vc_nw_settings
        farm_auto_spec.virtualCenterProvisioningSettings = farm_vc_provision_settings

        farm_vc_managed_common_settings = self.sud.get_object('ns0:FarmVirtualCenterManagedCommonSettings')
        farm_vc_managed_common_settings.transparentPageSharingScope = 'GLOBAL'

        farm_auto_spec.virtualCenterManagedCommonSettings = farm_vc_managed_common_settings

        farm_customization_settings = self.sud.get_object('ns0:FarmCustomizationSettings')
        farm_customization_settings.customizationType = 'SYS_PREP'
        farm_customization_settings.domainAdministrator = self.vc.get_view_composer_domain_admin_id(vc_id)
        farm_customization_settings.reusePreExistingAccounts = False

        farm_sysprep_cust_settings = self.sud.get_object('ns0:FarmSysprepCustomizationSettings')
        cust_spec_name = cust_spec_pars['customization_spec_name']
        farm_sysprep_cust_settings.customizationSpec = self.vc.get_customization_spec_id(vc_id, cust_spec_name)
        farm_customization_settings.sysprepCustomizationSettings = farm_sysprep_cust_settings

        farm_auto_spec.customizationSettings = farm_customization_settings

        farm_rds_server_max_session_data = self.sud.get_object('ns0:FarmRDSServerMaxSessionsData')
        farm_rds_server_max_session_data.maxSessionsType = 'LIMITED'
        farm_rds_server_max_session_data.maxSessions = int(farm_settings_pars['max_sessions'])

        farm_auto_spec.rdsServerMaxSessionsData = farm_rds_server_max_session_data

        farm_spec.automatedFarmSpec = farm_auto_spec
        farm_id = self.viewapi.Farm_Create(self.mor, farm_spec)
        logging.debug(self.get_host() + ': Start creating automated farm '
                        + farm_data.name + ' ID = ' + farm_id.id)
        return farm_id

    def create_instant_clone_farm(self, params, view_param):
        '''
        Create an automated farm with instant clones
        :param params:
        :param view_param
        :return:
        '''
        farm_spec = self.sud.get_object('ns0:FarmSpec')
        farm_spec.type = 'AUTOMATED'

        farm_data = self.sud.get_object('ns0:FarmData')
        farm_settings_pars = params['farm_settings']
        farm_session_settings_pars = params['session_settings']
        farm_protocol_settings_pars = params['protocol_settings']
        vc_settings_pars = params['vc_settings']
        adv_storage_pars = params['advanced_storage_options']
        storage_optimization_pars = params['storage_optimization']
        farm_data.name = farm_settings_pars['farm_name']
        farm_data.displayName = farm_data.name
        farm_data.accessGroup = self.get_access_group_id()
        farm_data.description = farm_data.name
        farm_data.enabled = True
        farm_data.deleting = False

        farm_session_settings = self.sud.get_object('ns0:FarmSessionSettings')
        farm_session_settings.disconnectedSessionTimeoutPolicy = farm_session_settings_pars['session_disconnect_timeout_policy']
        if farm_session_settings.disconnectedSessionTimeoutPolicy == 'AFTER':
            farm_session_settings.disconnectedSessionTimeoutMinutes = int(farm_session_settings_pars['session_disconnect_timeout'])
        farm_session_settings.emptySessionTimeoutPolicy = farm_session_settings_pars['empty_session_timeout_policy']
        farm_session_settings.emptySessionTimeoutMinutes= int(farm_session_settings_pars['empty_session_timeout'])
        farm_session_settings.logoffAfterTimeout = String.is_true(farm_session_settings_pars['logoff_after_timeout'])
        farm_data.settings = farm_session_settings

        farm_protocol_settings = self.sud.get_object('ns0:FarmDisplayProtocolSettings')
        farm_protocol_settings.defaultDisplayProtocol = farm_protocol_settings_pars['default_protocol']
        farm_protocol_settings.allowDisplayProtocolOverride = String.is_true(farm_protocol_settings_pars['allow_protocol_override'])
        farm_protocol_settings.enableHTMLAccess = String.is_true(farm_protocol_settings_pars['enable_html_access'])
        farm_data.displayProtocolSettings = farm_protocol_settings

        farm_spec.data = farm_data

        farm_auto_spec = self.sud.get_object('ns0:FarmAutomatedFarmSpec')
        farm_auto_spec.provisioningType = 'INSTANT_CLONE_ENGINE'
        vc = farm_settings_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')
        farm_auto_spec.virtualCenter = vc_id

        farm_naming_spec = self.sud.get_object('ns0:FarmRDSServerNamingSpec')
        farm_naming_spec.namingMethod = 'PATTERN'

        farm_pattern_naming_settings = self.sud.get_object('ns0:FarmPatternNamingSettings')
        farm_pattern_naming_settings.namingPattern = farm_settings_pars['name_prefix']
        farm_pattern_naming_settings.maxNumberOfRDSServers = int(farm_settings_pars['maximum_count'])
        farm_naming_spec.patternNamingSettings = farm_pattern_naming_settings

        farm_auto_spec.rdsServerNamingSpec = farm_naming_spec

        farm_vc_provision_settings = self.sud.get_object('ns0:FarmVirtualCenterProvisioningSettings')
        farm_vc_provision_settings.enableProvisioning = True
        farm_vc_provision_settings.stopProvisioningOnError = String.is_true(
            farm_settings_pars['stop_provision_on_error'])
        farm_vc_provision_settings.minReadyVMsOnVComposerMaintenance = int(farm_settings_pars['min_ready'])

        farm_vc_provisioning_data = self.sud.get_object('ns0:FarmVirtualCenterProvisioningData')
        base_image = vc_settings_pars['vm_name']
        base_image_id = self.vc.get_vm_id(vc_id, base_image)
        Validation.validate_param(base_image_id, 'Base image ' + base_image + ' is not found.')
        farm_vc_provisioning_data.parentVm = base_image_id
        base_image_ss_path = vc_settings_pars['snapshot_path']
        base_image_ss_id = self.vc.get_vm_ss_id(vc_id, base_image,
                                                base_image_ss_path)
        farm_vc_provisioning_data.snapshot = base_image_ss_id
        Validation.validate_param(base_image_ss_id,
                                  'Snapshot ' + base_image_ss_path + ' for base image  ' + base_image + ' is not found.')
        base_image_dc_id = self.vc.get_vm_dc_id(vc_id, base_image)
        Validation.validate_param(base_image_dc_id, 'Datacenter for base image ' + base_image + ' is not found.')
        farm_vc_provisioning_data.datacenter = base_image_dc_id

        vm_folder = vc_settings_pars['folder_name']
        vm_folder_id = self.vc.get_vm_folder_id(base_image_dc_id, vm_folder)
        Validation.validate_param(vm_folder_id, 'Folder ' + vm_folder + ' is not found.')
        farm_vc_provisioning_data.vmFolder = vm_folder_id

        host_or_cluster_name = vc_settings_pars['host_or_cluster_name']
        host_or_cluster_id = self.vc.get_host_or_cluster_id(base_image_dc_id, host_or_cluster_name)
        Validation.validate_param(host_or_cluster_id, 'Host or cluster ' + host_or_cluster_name + ' is not found.')
        farm_vc_provisioning_data.hostOrCluster = host_or_cluster_id

        resource_pool_name = vc_settings_pars['resource_pool_name']
        resource_pool_id = self.vc.get_resource_pool_id(host_or_cluster_id, resource_pool_name)
        Validation.validate_param(resource_pool_id, 'Resource pool ' + resource_pool_name + ' is not found.')
        farm_vc_provisioning_data.resourcePool = resource_pool_id
        farm_vc_provision_settings.virtualCenterProvisioningData = farm_vc_provisioning_data

        farm_vc_storage_settings = self.sud.get_object('ns0:FarmVirtualCenterStorageSettings')

        datastore_paths = vc_settings_pars['datastores']
        ds_settings = self.vc.get_os_datastores_for_farm(host_or_cluster_id,
                                                datastore_paths)
        Validation.validate_param(ds_settings, 'datastores ' + datastore_paths + ' are not found.')
        farm_vc_storage_settings.datastores = ds_settings
        farm_vc_storage_settings.useVSan = String.is_true(storage_optimization_pars['use_vsan'])

        farm_composer_storage_settings = self.sud.get_object('ns0:FarmViewComposerStorageSettings')
        farm_composer_storage_settings.useSeparateDatastoresReplicaAndOSDisks = String.is_true(
            storage_optimization_pars['use_separate_datastore_4_replica_and_os_disks'])
        if farm_composer_storage_settings.useSeparateDatastoresReplicaAndOSDisks:
            farm_composer_storage_settings.replicaDiskDatastore = self.vc \
                .get_replica_datastore_id(host_or_cluster_id, datastore_paths)
        farm_composer_storage_settings.useNativeSnapshots = False

        farm_space_reclaim_settings = self.sud.get_object('ns0:FarmSpaceReclamationSettings')
        # Farm Reclamation is not supported in instant clone
        # But the API is failing if we don't use the sesparse parameters
        # So hard coding for now.
        farm_space_reclaim_settings.reclaimVmDiskSpace = False
        if farm_space_reclaim_settings.reclaimVmDiskSpace:
            farm_space_reclaim_settings.reclamationThresholdGB = 1

        farm_composer_storage_settings.spaceReclamationSettings = farm_space_reclaim_settings

        farm_vc_storage_settings.viewComposerStorageSettings = farm_composer_storage_settings
        farm_vc_provision_settings.virtualCenterStorageSettings = farm_vc_storage_settings

        farm_vc_nw_settings = self.sud.get_object('ns0:FarmVirtualCenterNetworkingSettings')
        networks = vc_settings_pars['networks']
        if networks:
            nic = vc_settings_pars['nic']
            farm_vc_nw_settings.nics = self.vc.get_farm_networks(host_or_cluster_id, networks, base_image_ss_id, nic)
        farm_vc_provision_settings.virtualCenterNetworkingSettings = farm_vc_nw_settings
        farm_auto_spec.virtualCenterProvisioningSettings = farm_vc_provision_settings

        farm_vc_managed_common_settings = self.sud.get_object('ns0:FarmVirtualCenterManagedCommonSettings')
        farm_vc_managed_common_settings.transparentPageSharingScope = 'GLOBAL'

        farm_auto_spec.virtualCenterManagedCommonSettings = farm_vc_managed_common_settings

        farm_customization_settings = self.sud.get_object('ns0:FarmCustomizationSettings')
        farm_customization_settings.customizationType = 'CLONE_PREP'
        farm_customization_settings.reusePreExistingAccounts = False

        domain_name = view_param['domain']
        ad_domain_id = self.instantclonedomain.get_ad_domain_id(domain_name)
        Validation.validate_param(ad_domain_id, 'ADDomainId for ' \
                                  + domain_name + ' is not found.')
        ad_container_infos = self.viewapi.ADContainer_ListByDomain(MOR \
                                                                   .get_mor('ADContainer'), ad_domain_id)
        for ad_container_info in ad_container_infos:
            if ad_container_info.rdn == "CN=Computers":
                ad_container_id = ad_container_info.id
                break
        Validation.validate_param(ad_container_id, 'ADContainerId for ' \
                                  + domain_name + ' is not found.')
        farm_customization_settings.adContainer = ad_container_id
        farm_cloneprep_cust_settings = self.sud.get_object('ns0:FarmCloneprepCustomizationSettings')
        instant_clone_domain_admin_id = self.instantclonedomain \
            .get_instant_clone_domain_admin_id(domain_name)
        if instant_clone_domain_admin_id is None:
            user = view_param['user']
            password = view_param['password']
            logging.info('Adding Instant clone engine domain admin')
            instant_clone_domain_admin_id = self.instantclonedomain \
                .add_instant_clone_domain_admin(domain_name, user, password)
            logging.debug('Instant Clone domain id = ' \
                          + str(instant_clone_domain_admin_id))

        farm_cloneprep_cust_settings.instantCloneEngineDomainAdministrator = \
            instant_clone_domain_admin_id

        farm_customization_settings.cloneprepCustomizationSettings = \
                farm_cloneprep_cust_settings

        farm_auto_spec.customizationSettings = farm_customization_settings

        farm_rds_server_max_session_data = self.sud.get_object('ns0:FarmRDSServerMaxSessionsData')
        farm_rds_server_max_session_data.maxSessionsType = 'LIMITED'
        farm_rds_server_max_session_data.maxSessions = int(farm_settings_pars['max_sessions'])

        farm_auto_spec.rdsServerMaxSessionsData = farm_rds_server_max_session_data

        farm_spec.automatedFarmSpec = farm_auto_spec
        farm_id = self.viewapi.Farm_Create(self.mor, farm_spec)
        logging.debug(self.get_host() + ': Start creating instant clone farm '
                        + farm_data.name + ' ID = ' + farm_id.id)
        return farm_id

    def recompose_farm(self, params):
        '''
        Recompose the farm based on the params
        :param params:
        :return:
        '''
        vc_settings_pars = params['vc_settings']
        farm_settings_pars = params['farm_settings']
        farm_name = farm_settings_pars['farm_name']
        farm_id = self.get_farm_id_by_name(farm_name)
        vc = farm_settings_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')
        farm_recompose_spec = self.sud.get_object('ns0:FarmRecomposeSpec')
        base_image = vc_settings_pars['vm_name']
        base_image_id = self.vc.get_vm_id(vc_id, base_image)
        Validation.validate_param(base_image_id, 'Base image ' + base_image + ' is not found.')
        farm_recompose_spec.parentVm = base_image_id
        base_image_ss_path = vc_settings_pars['snapshot_path']
        base_image_ss_id = self.vc.get_vm_ss_id(vc_id, base_image,
                                                base_image_ss_path)
        farm_recompose_spec.snapshot = base_image_ss_id
        Validation.validate_param(base_image_ss_id,
                                  'Snapshot ' + base_image_ss_path + ' for base image  ' + base_image + ' is not found.')
        farm_recompose_spec.logoffSetting = "FORCE_LOGOFF"
        farm_recompose_spec.stopOnFirstError = True

        query_filter = self.queries.get_equal_filter('data.name', farm_name)
        rds_server_count = self.query_farm_summary_view(query_filter)
        rds_servers = self.query_farm_health_info(farm_id, rds_server_count)
        rds_server_ids = []
        for rds_server in rds_servers:
            rds_server_ids.append(rds_server.id)
        farm_recompose_spec.rdsServers = rds_server_ids

        logging.debug(self.get_host() + ': Start recomposing farm ' + farm_name)
        self.viewapi.Farm_Recompose(self.mor, farm_id, farm_recompose_spec)

    def farm_maintenance(self, params, ss_name):
        '''
        Farm maintenance applicable for instant clone farms
        :param params:
        :param ss_name
        :return:
        '''
        vc_settings_pars = params['vc_settings']
        farm_settings_pars = params['farm_settings']
        farm_maint_settings_pars = params['maintenance']
        farm_maint_spec = self.sud.get_object('ns0:FarmMaintenanceSpec')
        farm_maint_spec.maintenanceMode = farm_maint_settings_pars['mode']

        farm_recurr_maint_settings_pars = farm_maint_settings_pars['recurring_maint_settings']
        farm_recurr_maint_settings = self.sud.get_object('ns0:FarmRecurringMaintenanceSettings')
        farm_recurr_maint_settings.startTime = farm_recurr_maint_settings_pars['start_time']
        farm_recurr_maint_settings.maintenancePeriod = farm_recurr_maint_settings_pars['maint_period']
        farm_recurr_maint_settings.startInt = int(farm_recurr_maint_settings_pars['start_index'])
        farm_recurr_maint_settings.everyInt = int(farm_recurr_maint_settings_pars['frequency'])
        farm_maint_spec.recurringMaintenanceSettings = farm_recurr_maint_settings

        farm_image_maint_settings_pars = farm_maint_settings_pars['image_maint_settings']
        farm_image_maint_settings = self.sud.get_object('ns0:FarmImageMaintenanceSettings')
        vc = farm_settings_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')
        base_image = vc_settings_pars['vm_name']
        base_image_id = self.vc.get_vm_id(vc_id, base_image)
        Validation.validate_param(base_image_id, 'Base image ' + base_image + ' is not found.')
        farm_image_maint_settings.parentVm = base_image_id
        if ss_name:
            base_image_ss_path = vc_settings_pars['snapshot_path'] + '/' + ss_name
        else:
            base_image_ss_path = vc_settings_pars['snapshot_path']
        base_image_ss_id = self.vc.get_vm_ss_id(vc_id, base_image,
                                                base_image_ss_path)
        farm_image_maint_settings.snapshot = base_image_ss_id
        farm_image_maint_settings.logoffSetting = farm_image_maint_settings_pars['logoff_settings']
        farm_image_maint_settings.stopOnFirstError = String.is_true(farm_image_maint_settings_pars['stop_on_error'])
        farm_maint_spec.imageMaintenanceSettings = farm_image_maint_settings

        farm_name = farm_settings_pars['farm_name']
        farm_id = self.get_farm_id_by_name(farm_name)

        logging.debug(self.get_host() + ': Start maintenance of IC farm ' + farm_name)
        self.viewapi.Farm_ScheduleMaintenance(self.mor, farm_id, farm_maint_spec)

    def delete_farm(self,params):
        '''
        Delete Farm
        :param params:
        :return:
        '''
        farm_settings = params['farm_settings']
        farm_name = farm_settings['farm_name']
        farm_id = self.get_farm_id_by_name(farm_name)
        logging.debug(self.get_host() + ': Start deleting farm ' + farm_name)
        self.viewapi.Farm_Delete(self.mor, farm_id)

class Desktops(ViewBase):
    '''
    Helper for View desktop service API
    '''

    def __init__(self, sud):
        super(Desktops, self).__init__(sud)
        self.queries = Queries(sud)
        self.vc = VC(sud)
        self.instantclonedomain = InstantCloneDomain(sud)
        self.farms = Farms(sud)

    def get_mor_type(self):
        return 'Desktop'

    def get_summaryview(self, desktop_id):
        '''
        Fetch a summary for given desktop ID
        :param desktop_id:
        :return:
        '''
        return self.viewapi.Desktop_GetSummaryView(self.mor, desktop_id)

    def query_desktop(self, query_filter):
        '''
        search for desktops given the filter
        :param query_filter:
        :return:
        '''
        return self.queries.query(query_filter, 'DesktopSummaryView')

    def get_desktop_id_by_name(self, desktop_name):
        '''
        Search for desktop given the name
        :param desktop_name:
        :return:
        '''
        query_filter = self.queries \
            .get_equal_filter('desktopSummaryData.name', desktop_name)
        ret = self.query_desktop(query_filter)

        if not hasattr(ret, 'results'):
            return None
        if len(ret.results) > 1:
            raise Exception('Found more than 1 pool with name ' + desktop_name)

        return ret.results[0].id

    def get_desktop_type(self, desktop_name):
        '''
        Search for desktop type given the name
        :param desktop_name:
        :return:
        '''
        query_filter = self.queries \
            .get_equal_filter('desktopSummaryData.displayName', desktop_name)
        ret = self.query_desktop(query_filter)

        if not hasattr(ret, 'results'):
            return None
        if len(ret.results) == 1:
            return ret.results[0].desktopSummaryData.type

    def get_desktop(self, desktop_id):
        '''
        Fetch the desktop object given its ID
        :param desktop_id:
        :return:
        '''
        return self.viewapi.Desktop_Get(self.mor, desktop_id)

    def query_rds_summary_view(self, query_filter):
        '''
        Search for rds server in a farm given the filter
        :param query_filter:
        :return:
        '''
        ret = self.queries.create(query_filter, 'RDSServerSummaryView')
        query_id = ret.id
        machines = []
        try:
            while 'results' in ret:
                for mc in ret.results:
                    machines.append(mc)
                ret = self.queries.next(query_id)
        finally:
            if query_id:
                self.queries.delete(query_id)
        return machines

    def get_rds_machines_in_state(self, rds_name, machine_state):
        '''
        Fetch machines matching given state
        :param rds_name:
        :param machine_state:
        :return:
        '''
        rds_desktop_id = self.get_desktop_id_by_name(rds_name)
        query_filter = self.queries.get_equal_filter('base.desktop', rds_desktop_id)
        machines = self.query_rds_summary_view(query_filter)
        ret = []
        for machine in machines:
            if machine.runtimeData.status == machine_state:
                ret.append(machine)
        return ret

    def query_machine_names_view(self, query_filter):
        '''
        Search for machines given the filter
        :param query_filter:
        :return:
        '''
        ret = self.queries.create(query_filter, 'MachineNamesView')
        query_id = ret.id
        machines = []
        try:
            while 'results' in ret:
                for mc in ret.results:
                    machines.append(mc)
                ret = self.queries.next(query_id)
        finally:
            if query_id:
                self.queries.delete(query_id)
        return machines

    def get_machines_in_state1(self, desktop_id, machine_state):
        '''
        Fetch machines matching given state
        :param desktop_id:
        :param machine_state:
        :return:
        '''
        query_filter = self.queries.get_equal_filter('base.desktop', desktop_id)
        machines = self.query_machine_names_view(query_filter)
        ret = []
        for machine in machines:
            if machine.base.basicState == machine_state:
                ret.append(machine)
        return ret

    def get_machines_in_state(self, desktop_name, machine_state):
        '''
        Fetch machines matching given state
        :param desktop_name:
        :param machine_state:
        :return:
        '''
        desktop_id = self.get_desktop_id_by_name(desktop_name)
        return self.get_machines_in_state1(desktop_id, machine_state)

    def get_machines(self, desktop_name):
        '''
        Fetch machines in the given desktop
        :param desktop_name:
        :return:
        '''
        desktop_id = self.get_desktop_id_by_name(desktop_name)
        query_filter = self.queries.get_equal_filter('base.desktop', desktop_id)
        machines = self.query_machine_names_view(query_filter)
        ret = []
        for machine in machines:
            ret.append(machine.id)
        return ret

    def get_access_group_id(self):
        '''
        Fetch the access group ID
        :return:
        '''
        rets = self.viewapi.AccessGroup_List(MOR.get_mor('AccessGroup'))
        if len(rets) > 0:
            return rets[0].id
        else:
            return None

    def create_automated_desktop(self, params):
        '''
        Create an automated desktop
        :param params:
        :return:
        '''
        dt_spec = self.sud.get_object('ns0:DesktopSpec')
        dt_spec.type = 'AUTOMATED'

        dt_settings = self.sud.get_object('ns0:DesktopSettings')
        dt_settings.enabled = True
        dt_settings.deleting = False

        log_off_settings = self.sud.get_object('ns0:DesktopLogoffSettings')
        pl_settings_pars = params['pool_settings']
        log_off_settings.powerPolicy = pl_settings_pars['power_policy']
        try:
            tmp_time = int(pl_settings_pars['auto_logoff_time'])
            log_off_settings.automaticLogoffPolicy = 'AFTER'
            log_off_settings.automaticLogoffMinutes = tmp_time
        except:
            log_off_settings.automaticLogoffPolicy = \
                pl_settings_pars['auto_logoff_time']

        log_off_settings.deleteOrRefreshMachineAfterLogoff = \
            pl_settings_pars['delete_policy']
        log_off_settings.refreshOsDiskAfterLogoff = \
            pl_settings_pars['refresh_policy_type']
        log_off_settings.allowUsersToResetMachines = False
        log_off_settings.allowMultipleSessionsPerUser = False

        dt_settings.logoffSettings = log_off_settings

        display_protocol_settings = self.sud \
            .get_object('ns0:DesktopDisplayProtocolSettings')
        display_protocol_settings.supportedDisplayProtocols = ['BLAST', 'PCOIP', 'RDP']
        display_protocol_settings.defaultDisplayProtocol = \
            pl_settings_pars['default_protocol']
        display_protocol_settings.allowUsersToChooseProtocol = String \
            .is_true(pl_settings_pars['allow_protocol_override'])
        display_protocol_settings.enableHTMLAccess = String \
            .is_true(pl_settings_pars['enable_html_access'])
        dt_settings.flashSettings = self.sud.get_object(
            'ns0:DesktopAdobeFlashSettings')
        pcoip_display_settings = self.sud \
            .get_object('ns0:DesktopPCoIPDisplaySettings')
        pcoip_display_settings.renderer3D = 'DISABLED'
        pcoip_display_settings.enableGRIDvGPUs = False
        pcoip_display_settings.maxNumberOfMonitors = 2
        pcoip_display_settings.maxResolutionOfAnyOneMonitor = 'WUXGA'
        display_protocol_settings.pcoipDisplaySettings = pcoip_display_settings
        dt_settings.displayProtocolSettings = display_protocol_settings
        dt_settings.flashSettings.quality = pl_settings_pars['flash_quality']
        dt_settings.flashSettings.throttling = \
            pl_settings_pars['flash_throttling']
        dt_settings.mirageConfigurationOverrides = self.sud.get_object(
            'ns0:DesktopMirageConfigurationOverrides')
        dt_settings.mirageConfigurationOverrides.enabled = False
        dt_settings.mirageConfigurationOverrides.overrideGlobalSetting = False
        dt_spec.desktopSettings = dt_settings

        adt_spec = self.sud.get_object('ns0:DesktopAutomatedDesktopSpec')
        adt_spec.provisioningType = 'VIEW_COMPOSER'

        pool_def_pars = params['pool_definition']
        vc = pool_def_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')
        adt_spec.virtualCenter = vc_id
        user_assignment = self.sud.get_object('ns0:DesktopUserAssignment')
        user_assignment.userAssignment = pool_def_pars['user_assignment']
        if user_assignment.userAssignment == 'DEDICATED':
            user_assignment.automaticAssignment = String \
                .is_true(pool_def_pars['automatic_assignment'])
        adt_spec.userAssignment = user_assignment

        vm_naming_spec = self.sud.get_object(
            'ns0:DesktopVirtualMachineNamingSpec')
        vm_naming_spec.namingMethod = 'PATTERN'

        prov_settings_pars = params['provisioning_settings']
        pattern_naming_settings = self.sud \
            .get_object('ns0:DesktopPatternNamingSettings')
        pattern_naming_settings.namingPattern = prov_settings_pars \
            ['name_prefix']
        pattern_naming_settings.maxNumberOfMachines = int(
            prov_settings_pars['maximum_count'])
        if prov_settings_pars.has_key('minimum_count'):
            pattern_naming_settings.minNumberOfMachines = int(\
                        prov_settings_pars['minimum_count'])
        else:
            pattern_naming_settings.minNumberOfMachines = int(\
                        prov_settings_pars['maximum_count'])
        if prov_settings_pars.has_key('headroom_count'):
            pattern_naming_settings.numberOfSpareMachines = int(\
                        prov_settings_pars['headroom_count'])
        else:
            pattern_naming_settings.numberOfSpareMachines = int(\
                        prov_settings_pars['maximum_count'])
        pattern_naming_settings.provisioningTime = \
            prov_settings_pars['provisioning_time']

        vm_naming_spec.patternNamingSettings = pattern_naming_settings
        adt_spec.vmNamingSpec = vm_naming_spec

        vc_provision_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterProvisioningSettings')
        vc_provision_settings.enableProvisioning = String.is_true(
            prov_settings_pars['provisioning_enabled'])
        vc_provision_settings.stopProvisioningOnError = String.is_true(
            prov_settings_pars['stop_provision_on_error'])
        vc_provision_settings.minReadyVMsOnVComposerMaintenance = \
            prov_settings_pars['min_ready_vms']

        vc_setting_pars = params['vc_settings']
        base_image = vc_setting_pars['vm_name']
        base_image_id = self.vc.get_vm_id(vc_id, base_image)
        Validation.validate_param(base_image_id, 'Base image ' + base_image
                                  + ' is not found.')
        vc_provision_data = self.sud \
            .get_object('ns0:DesktopVirtualCenterProvisioningData')
        vc_provision_data.parentVm = base_image_id

        base_image_ss_path = vc_setting_pars['snapshot_path']
        base_image_ss_id = self.vc.get_vm_ss_id(vc_id, base_image,
                                                base_image_ss_path)
        Validation.validate_param(base_image_ss_id, 'Snapshot '
                                  + base_image_ss_path + ' for base image '
                                  + base_image + ' is not found.')

        vc_provision_data.snapshot = base_image_ss_id
        base_image_dc_id = self.vc.get_vm_dc_id(vc_id, base_image)
        Validation.validate_param(base_image_dc_id, 'Datacenter for base '
                                                    'image '
                                  + base_image + ' is not found.')
        vc_provision_data.datacenter = base_image_dc_id

        vm_folder = vc_setting_pars['folder_name']
        vm_folder_id = self.vc.get_vm_folder_id(base_image_dc_id, vm_folder)
        Validation.validate_param(vm_folder_id, 'Folder ' + vm_folder
                                  + ' is not found.')
        vc_provision_data.vmFolder = vm_folder_id

        host_or_cluster_name = vc_setting_pars['host_or_cluster_name']
        host_or_cluster_id = self.vc.get_host_or_cluster_id(base_image_dc_id,
                                                            host_or_cluster_name)
        Validation.validate_param(host_or_cluster_id, 'Host or cluster '
                                  + host_or_cluster_name + ' is not found.')
        vc_provision_data.hostOrCluster = host_or_cluster_id

        resource_pool_name = vc_setting_pars['resource_pool_name']
        resource_pool_id = self.vc.get_resource_pool_id(host_or_cluster_id,
                                                        resource_pool_name)
        Validation.validate_param(resource_pool_id, 'Resource pool '
                                  + resource_pool_name + ' is not found.')
        vc_provision_data.resourcePool = resource_pool_id
        vc_provision_settings.virtualCenterProvisioningData = vc_provision_data

        datastore_paths = vc_setting_pars['datastores']
        ds_settings = self.vc.get_os_datastores(host_or_cluster_id,
                                                datastore_paths)
        Validation.validate_param(ds_settings, 'datastores '
                                  + datastore_paths + ' are not found.')

        storage_opt_pars = params['storage_optimization']
        vc_storage_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterStorageSettings')
        vc_storage_settings.datastores = ds_settings
        vc_storage_settings.useVSan = String.is_true(storage_opt_pars
                                                     ['use_vsan'])

        view_composer_storage_settings = self.sud \
            .get_object('ns0:DesktopViewComposerStorageSettings')
        view_composer_storage_settings.useSeparateDatastoresReplicaAndOSDisks \
            = \
            String.is_true(storage_opt_pars
                           [
                               'use_separate_datastore_4_replica_and_os_disks'])
        if view_composer_storage_settings \
                .useSeparateDatastoresReplicaAndOSDisks:
            view_composer_storage_settings.replicaDiskDatastore = self.vc \
                .get_replica_datastore_id(host_or_cluster_id, datastore_paths)

        adv_storage_opt_pars = params['advanced_storage_options']
        view_composer_storage_settings.useNativeSnapshots = String \
            .is_true(adv_storage_opt_pars['use_vaai'])

        space_reclaim_settings = self.sud \
            .get_object('ns0:DesktopSpaceReclamationSettings')
        space_reclaim_settings.reclaimVmDiskSpace = String \
            .is_true(adv_storage_opt_pars['use_sesparse_disk_format'])
        if space_reclaim_settings.reclaimVmDiskSpace:
            space_reclaim_settings.reclamationThresholdGB = \
                int(adv_storage_opt_pars['sesparse_threshold'])

        view_composer_storage_settings.spaceReclamationSettings = \
            space_reclaim_settings

        persistent_disk_settings = self.sud \
            .get_object('ns0:DesktopPersistentDiskSettings')
        view_compsr_pars = params['view_composer_disks']
        persistent_disk_settings.redirectWindowsProfile = String \
            .is_true(view_compsr_pars['use_user_data_disk'])
        if persistent_disk_settings.redirectWindowsProfile:
            persistent_disk_settings.diskDriveLetter = \
                view_compsr_pars['data_disk_letter']
            persistent_disk_settings.diskSizeMB = int(view_compsr_pars
                                                      ['data_disk_size'])
        persistent_disk_settings.useSeparateDatastoresPersistentAndOSDisks = \
            String.is_true(storage_opt_pars
                           ['use_separate_datastore_4_data_and_os_disks'])
        if persistent_disk_settings.useSeparateDatastoresPersistentAndOSDisks:
            persistent_disk_settings.persistentDiskDatastores = self.vc \
                .get_persistent_datastores(host_or_cluster_id, datastore_paths)

        view_composer_storage_settings.persistentDiskSettings = \
            persistent_disk_settings

        non_persistent_disk_settings = self.sud \
            .get_object('ns0:DesktopNonPersistentDiskSettings')
        non_persistent_disk_settings.redirectDisposableFiles = String \
            .is_true(view_compsr_pars['use_temp_disk'])
        if non_persistent_disk_settings.redirectDisposableFiles:
            non_persistent_disk_settings.diskDriveLetter = view_compsr_pars \
                ['temp_disk_letter']
            non_persistent_disk_settings.diskSizeMB = \
                int(view_compsr_pars['temp_disk_size'])

        view_composer_storage_settings.nonPersistentDiskSettings = \
            non_persistent_disk_settings

        vc_storage_settings.viewComposerStorageSettings = \
            view_composer_storage_settings

        view_storage_accel_settings = self.sud \
            .get_object('ns0:DesktopViewStorageAcceleratorSettings')
        view_storage_accel_settings.useViewStorageAccelerator = String \
            .is_true(adv_storage_opt_pars['use_cbrc'])
        if view_storage_accel_settings.useViewStorageAccelerator:
            view_storage_accel_settings.viewComposerDiskTypes = \
                adv_storage_opt_pars['disk_type_cbrc']
            view_storage_accel_settings.regenerateViewStorageAcceleratorDays = \
                int(adv_storage_opt_pars['regenerate_cbrc_cache'])

        vc_storage_settings.viewStorageAcceleratorSettings = \
            view_storage_accel_settings
        vc_provision_settings.virtualCenterStorageSettings = vc_storage_settings

        vc_network_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterNetworkingSettings')
        vc_provision_settings.virtualCenterNetworkingSettings = \
            vc_network_settings

        adt_spec.virtualCenterProvisioningSettings = vc_provision_settings

        guest_cust_pars = params['guest_customization']
        customize_settings = self.sud \
            .get_object('ns0:DesktopCustomizationSettings')
        customize_settings.customizationType = \
            guest_cust_pars['customization_type']
        if customize_settings.customizationType.lower() == 'none':
            no_cust_settings = self.sud \
                .get_object('ns0:DesktopNoCustomizationSettings')
            no_cust_settings.doNotPowerOnVMsAfterCreation = False
            customize_settings.noCustomizationSettings = no_cust_settings
        elif customize_settings.customizationType.lower() == 'quick_prep':
            quick_prep_cust_settings = self.sud \
                .get_object('ns0:DesktopQuickprepCustomizationSettings')
            quick_prep_cust_settings.powerOffScriptName = \
                guest_cust_pars['logoff_script']
            quick_prep_cust_settings.postSynchronizationScriptName = \
                guest_cust_pars['post_sync_script']
            customize_settings.quickprepCustomizationSettings = \
                quick_prep_cust_settings
        elif customize_settings.customizationType.lower() == 'sys_prep':
            sys_prep_cust_settings = self.sud \
                .get_object('ns0:DesktopSysprepCustomizationSettings')
            spec_name = guest_cust_pars['customization_spec_name']
            sys_prep_cust_settings.customizationSpec = self.vc \
                .get_customization_spec_id(vc_id, spec_name)
            customize_settings.sysprepCustomizationSettings = \
                sys_prep_cust_settings
        else:
            raise Exception('Invalid customization type '
                            + customize_settings.customizationType)

        customize_settings.domainAdministrator = self.vc \
            .get_view_composer_domain_admin_id(vc_id)

        customize_settings.reusePreExistingAccounts = String \
            .is_true(guest_cust_pars['reuse_existing_accounts'])
        adt_spec.customizationSettings = customize_settings

        vc_common_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterManagedCommonSettings')
        vc_common_settings.transparentPageSharingScope = \
            adv_storage_opt_pars['transparent_page_sharing_scope']
        adt_spec.virtualCenterManagedCommonSettings = vc_common_settings
        dt_spec.automatedDesktopSpec = adt_spec
        dt_base = self.sud.get_object('ns0:DesktopBase')
        dt_base.name = pl_settings_pars['pool_name']
        dt_base.displayName = pl_settings_pars['pool_name']
        dt_base.accessGroup = self.get_access_group_id()
        dt_spec.base = dt_base

        desktop_id = self.viewapi.Desktop_Create(self.mor, dt_spec)
        logging.debug(self.get_host() + ': Start creating pool '
                      + dt_base.name + ' ID = ' + desktop_id.id)
        return desktop_id

    def create_automated_full_desktop(self, params):
        '''
        Create an automated desktop with full clones
        :param params:
        :return:
        '''
        dt_spec = self.sud.get_object('ns0:DesktopSpec')
        dt_spec.type = 'AUTOMATED'

        dt_settings = self.sud.get_object('ns0:DesktopSettings')
        dt_settings.enabled = True
        dt_settings.deleting = False

        log_off_settings = self.sud.get_object('ns0:DesktopLogoffSettings')
        pl_settings_pars = params['pool_settings']
        log_off_settings.powerPolicy = pl_settings_pars['power_policy']
        try:
            tmp_time = int(pl_settings_pars['auto_logoff_time'])
            log_off_settings.automaticLogoffPolicy = 'AFTER'
            log_off_settings.automaticLogoffMinutes = tmp_time
        except:
            log_off_settings.automaticLogoffPolicy = \
                pl_settings_pars['auto_logoff_time']

        log_off_settings.deleteOrRefreshMachineAfterLogoff = \
            pl_settings_pars['delete_policy']
        log_off_settings.refreshOsDiskAfterLogoff = \
            pl_settings_pars['refresh_policy_type']
        log_off_settings.allowUsersToResetMachines = False
        log_off_settings.allowMultipleSessionsPerUser = False

        dt_settings.logoffSettings = log_off_settings

        display_protocol_settings = self.sud \
            .get_object('ns0:DesktopDisplayProtocolSettings')
        display_protocol_settings.supportedDisplayProtocols = ['BLAST', 'PCOIP', 'RDP']
        display_protocol_settings.defaultDisplayProtocol = \
            pl_settings_pars['default_protocol']
        display_protocol_settings.allowUsersToChooseProtocol = String \
            .is_true(pl_settings_pars['allow_protocol_override'])
        display_protocol_settings.enableHTMLAccess = String \
            .is_true(pl_settings_pars['enable_html_access'])
        dt_settings.flashSettings = self.sud.get_object(
            'ns0:DesktopAdobeFlashSettings')
        pcoip_display_settings = self.sud \
            .get_object('ns0:DesktopPCoIPDisplaySettings')
        pcoip_display_settings.renderer3D = 'DISABLED'
        pcoip_display_settings.enableGRIDvGPUs = False
        pcoip_display_settings.maxNumberOfMonitors = 2
        pcoip_display_settings.maxResolutionOfAnyOneMonitor = 'WUXGA'
        display_protocol_settings.pcoipDisplaySettings = pcoip_display_settings
        dt_settings.displayProtocolSettings = display_protocol_settings
        dt_settings.flashSettings.quality = pl_settings_pars['flash_quality']
        dt_settings.flashSettings.throttling = \
            pl_settings_pars['flash_throttling']
        dt_settings.mirageConfigurationOverrides = self.sud.get_object(
            'ns0:DesktopMirageConfigurationOverrides')
        dt_settings.mirageConfigurationOverrides.enabled = False
        dt_settings.mirageConfigurationOverrides.overrideGlobalSetting = False
        dt_spec.desktopSettings = dt_settings

        adt_spec = self.sud.get_object('ns0:DesktopAutomatedDesktopSpec')
        adt_spec.provisioningType = 'VIRTUAL_CENTER'

        pool_def_pars = params['pool_definition']
        vc = pool_def_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')
        adt_spec.virtualCenter = vc_id
        user_assignment = self.sud.get_object('ns0:DesktopUserAssignment')
        user_assignment.userAssignment = pool_def_pars['user_assignment']
        if user_assignment.userAssignment == 'DEDICATED':
            user_assignment.automaticAssignment = String \
                .is_true(pool_def_pars['automatic_assignment'])
        adt_spec.userAssignment = user_assignment

        vm_naming_spec = self.sud.get_object(
            'ns0:DesktopVirtualMachineNamingSpec')
        vm_naming_spec.namingMethod = 'PATTERN'

        prov_settings_pars = params['provisioning_settings']
        pattern_naming_settings = self.sud \
            .get_object('ns0:DesktopPatternNamingSettings')
        pattern_naming_settings.namingPattern = prov_settings_pars \
            ['name_prefix']
        pattern_naming_settings.maxNumberOfMachines = int(
            prov_settings_pars['maximum_count'])
        if prov_settings_pars.has_key('minimum_count'):
            pattern_naming_settings.minNumberOfMachines = int( \
                prov_settings_pars['minimum_count'])
        else:
            pattern_naming_settings.minNumberOfMachines = int( \
                prov_settings_pars['maximum_count'])
        if prov_settings_pars.has_key('headroom_count'):
            pattern_naming_settings.numberOfSpareMachines = int( \
                prov_settings_pars['headroom_count'])
        else:
            pattern_naming_settings.numberOfSpareMachines = int( \
                prov_settings_pars['maximum_count'])
        pattern_naming_settings.provisioningTime = \
            prov_settings_pars['provisioning_time']

        vm_naming_spec.patternNamingSettings = pattern_naming_settings
        adt_spec.vmNamingSpec = vm_naming_spec

        vc_provision_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterProvisioningSettings')
        vc_provision_settings.enableProvisioning = String.is_true(
            prov_settings_pars['provisioning_enabled'])
        vc_provision_settings.stopProvisioningOnError = String.is_true(
            prov_settings_pars['stop_provision_on_error'])
        vc_provision_settings.minReadyVMsOnVComposerMaintenance = \
            prov_settings_pars['min_ready_vms']

        vc_setting_pars = params['vc_settings']
        base_template = vc_setting_pars['template_name']
        base_template_id = self.vc.get_template_id(vc_id, base_template)
        Validation.validate_param(base_template_id, 'Template ' + base_template + ' is not found')
        vc_provision_data = self.sud.get_object('ns0:DesktopVirtualCenterProvisioningData')
        vc_provision_data.template = base_template_id
        base_template_dc_id = self.vc.get_template_dc_id(vc_id, base_template)
        Validation.validate_param(base_template_dc_id, 'Datacenter for base '
                                                       'template '
                                  + base_template + ' is not found.')
        vc_provision_data.datacenter = base_template_dc_id

        vm_folder = vc_setting_pars['folder_name']
        vm_folder_id = self.vc.get_vm_folder_id(base_template_dc_id, vm_folder)
        Validation.validate_param(vm_folder_id, 'Folder ' + vm_folder
                                  + ' is not found.')
        vc_provision_data.vmFolder = vm_folder_id

        host_or_cluster_name = vc_setting_pars['host_or_cluster_name']
        host_or_cluster_id = self.vc.get_host_or_cluster_id(base_template_dc_id,
                                                            host_or_cluster_name)
        Validation.validate_param(host_or_cluster_id, 'Host or cluster '
                                  + host_or_cluster_name + ' is not found.')
        vc_provision_data.hostOrCluster = host_or_cluster_id

        resource_pool_name = vc_setting_pars['resource_pool_name']
        resource_pool_id = self.vc.get_resource_pool_id(host_or_cluster_id,
                                                        resource_pool_name)
        Validation.validate_param(resource_pool_id, 'Resource pool '
                                  + resource_pool_name + ' is not found.')
        vc_provision_data.resourcePool = resource_pool_id
        vc_provision_settings.virtualCenterProvisioningData = vc_provision_data

        datastore_paths = vc_setting_pars['datastores']
        ds_settings = self.vc.get_os_datastores(host_or_cluster_id,
                                                datastore_paths)
        Validation.validate_param(ds_settings, 'datastores '
                                  + datastore_paths + ' are not found.')

        storage_opt_pars = params['storage_optimization']
        vc_storage_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterStorageSettings')
        vc_storage_settings.datastores = ds_settings
        vc_storage_settings.useVSan = String.is_true(storage_opt_pars
                                                     ['use_vsan'])
        adv_storage_opt_pars = params['advanced_storage_options']
        view_storage_accel_settings = self.sud \
            .get_object('ns0:DesktopViewStorageAcceleratorSettings')
        view_storage_accel_settings.useViewStorageAccelerator = String \
            .is_true(adv_storage_opt_pars['use_cbrc'])
        if view_storage_accel_settings.useViewStorageAccelerator:
            view_storage_accel_settings.regenerateViewStorageAcceleratorDays = \
                int(adv_storage_opt_pars['regenerate_cbrc_cache'])

        vc_storage_settings.viewStorageAcceleratorSettings = \
            view_storage_accel_settings
        vc_provision_settings.virtualCenterStorageSettings = vc_storage_settings

        vc_network_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterNetworkingSettings')
        vc_provision_settings.virtualCenterNetworkingSettings = \
            vc_network_settings

        adt_spec.virtualCenterProvisioningSettings = vc_provision_settings

        guest_cust_pars = params['guest_customization']
        customize_settings = self.sud \
            .get_object('ns0:DesktopCustomizationSettings')
        customize_settings.customizationType = \
            guest_cust_pars['customization_type']
        if customize_settings.customizationType.lower() == 'none':
            no_cust_settings = self.sud \
                .get_object('ns0:DesktopNoCustomizationSettings')
            no_cust_settings.doNotPowerOnVMsAfterCreation = False
            customize_settings.noCustomizationSettings = no_cust_settings
        elif customize_settings.customizationType.lower() == 'sys_prep':
            sys_prep_cust_settings = self.sud \
                .get_object('ns0:DesktopSysprepCustomizationSettings')
            spec_name = guest_cust_pars['customization_spec_name']
            sys_prep_cust_settings.customizationSpec = self.vc \
                .get_customization_spec_id(vc_id, spec_name)
            customize_settings.sysprepCustomizationSettings = \
                sys_prep_cust_settings
        else:
            raise Exception('Invalid customization type '
                            + customize_settings.customizationType)

        customize_settings.reusePreExistingAccounts = String \
            .is_true(guest_cust_pars['reuse_existing_accounts'])
        adt_spec.customizationSettings = customize_settings

        vc_common_settings = self.sud \
            .get_object('ns0:DesktopVirtualCenterManagedCommonSettings')
        vc_common_settings.transparentPageSharingScope = \
            adv_storage_opt_pars['transparent_page_sharing_scope']
        adt_spec.virtualCenterManagedCommonSettings = vc_common_settings
        dt_spec.automatedDesktopSpec = adt_spec
        dt_base = self.sud.get_object('ns0:DesktopBase')
        dt_base.name = pl_settings_pars['pool_name']
        dt_base.displayName = pl_settings_pars['pool_name']
        dt_base.accessGroup = self.get_access_group_id()
        dt_spec.base = dt_base

        desktop_id = self.viewapi.Desktop_Create(self.mor, dt_spec)
        return desktop_id

    def create_rds_desktop(self, params):
        '''
        Create a rds desktop from the farm
        :param params:
        :return:
        '''
        dt_spec = self.sud.get_object('ns0:DesktopSpec')
        dt_spec.type = 'RDS'

        dt_base = self.sud.get_object('ns0:DesktopBase')
        dt_pool_settings_pars = params['pool_settings']
        dt_base.name = dt_pool_settings_pars['pool_name']
        dt_base.displayName = dt_base.name
        dt_base.description = dt_base.name
        dt_base.accessGroup = self.get_access_group_id()
        dt_spec.base = dt_base

        dt_settings = self.sud.get_object('ns0:DesktopSettings')
        dt_settings.enabled = True
        dt_settings.deleting = False

        flash_settings = self.sud.get_object('ns0:DesktopAdobeFlashSettings')
        flash_settings.quality = dt_pool_settings_pars['flash_quality']
        flash_settings.throttling = dt_pool_settings_pars['flash_throttling']
        dt_settings.flashSettings = flash_settings

        dt_spec.desktopSettings = dt_settings

        dt_rds_spec = self.sud.get_object('ns0:DesktopRDSDesktopSpec')
        farm_name = dt_pool_settings_pars['farm_name']
        dt_rds_spec.farm = self.farms.get_farm_id_by_name(farm_name)
        dt_spec.rdsDesktopSpec = dt_rds_spec

        desktop_id = self.viewapi.Desktop_Create(self.mor, dt_spec)
        return desktop_id

    def delete(self, desktop_id):
        '''
        Destroy a desktop given its ID
        :param desktop_id:
        :return:
        '''
        spec = self.sud.get_object('ns0:DesktopDeleteSpec')
        spec.archivePersistentDisk = False
        self.viewapi.Desktop_Delete(self.mor, desktop_id, spec)

    def delete_by_name(self, desktop_name):
        '''
        Destroy a desktop given its name
        :param desktop_name:
        :return:
        '''
        logging.debug(self.get_host() + ': deleting pool ' + desktop_name)
        self.delete(self.get_desktop_id_by_name(desktop_name))

    def delete_all(self, desktop_type):
        '''
        Destroy all desktops of given type
        :param desktop_type:
        :return:
        '''
        d_filter = None
        if desktop_type:
            d_filter = self.queries.get_equal_filter(
                'desktopSummaryData.type', desktop_type)
        ret = self.query_desktop(d_filter)

        if not ret or not hasattr(ret, 'results'):
            return

        for desktop in ret.results:
            spec = self.sud.get_object('ns0:DesktopDeleteSpec')
            spec.archivePersistentDisk = False
            d_source = desktop.desktopSummaryData.source
            d_type = desktop.desktopSummaryData.type
            d_name = desktop.desktopSummaryData.name
            del_from_disk = d_type.lower() == 'automated' or \
                            (d_type.lower() == 'manual' and
                             d_source.lower() == 'virtual_center')
            spec.deleteFromDisk = del_from_disk
            logging.debug(self.get_host() + ': deleting pool ' + d_name + ' with id '
                          + String.to_string(desktop.id))
            self.viewapi.Desktop_Delete(self.mor, desktop.id, spec)

    def refresh(self, desktop_name):
        '''
        Refresh given desktop
        :param desktop_name:
        :return:
        '''
        spec = self.sud.get_object('ns0:DesktopRefreshSpec')
        spec.logoffSetting = 'FORCE_LOGOFF'
        spec.machines = self.get_machines(desktop_name)
        spec.stopOnFirstError = True
        desktop_id = self.get_desktop_id_by_name(desktop_name)
        logging.debug(self.get_host() + ': refresh ' + desktop_name)
        self.viewapi.Desktop_Refresh(self.mor, desktop_id, spec)

    def rebalance(self, desktop_name):
        '''
        Rebalance given desktop
        :param desktop_name:
        :return:
        '''
        spec = self.sud.get_object('ns0:DesktopRebalanceSpec')
        spec.logoffSetting = 'FORCE_LOGOFF'
        spec.machines = self.get_machines(desktop_name)
        desktop_id = self.get_desktop_id_by_name(desktop_name)
        logging.debug(self.get_host() + ': rebalance ' + desktop_name)
        self.viewapi.Desktop_Rebalance(self.mor, desktop_id, spec)

    def recompose(self, desktop_name, vc_host, parent_vm, parent_snapshot,stopOnFirstError):
        '''
        Recomposer given desktop
        :param desktop_name:
        :param vc_host:
        :param parent_vm:
        :param parent_snapshot:
        :return:
        '''
        spec = self.sud.get_object('ns0:DesktopRecomposeSpec')
        spec.logoffSetting = 'FORCE_LOGOFF'
        spec.machines = self.get_machines(desktop_name)
        spec.stopOnFirstError = stopOnFirstError

        vc_id = self.vc.get_id(vc_host)
        Validation.validate_param(vc_id, 'VC ' + vc_host + ' is not found')
        parent_vm_id = self.vc.get_vm_id(vc_id, parent_vm)
        Validation.validate_param(parent_vm_id, 'Parent VM ' + parent_vm
                                  + ' is not found')
        spec.parentVm = parent_vm_id
        parent_snapshot_id = self.vc.get_vm_ss_id(vc_id, parent_vm,
                                                  parent_snapshot)
        Validation.validate_param(parent_vm_id, 'Parent snapshot '
                                  + parent_snapshot + ' is not found')
        spec.snapshot = parent_snapshot_id
        desktop_id = self.get_desktop_id_by_name(desktop_name)
        logging.debug(self.get_host() + ': recompose ' + desktop_name)
        self.viewapi.Desktop_Recompose(self.mor, desktop_id, spec)

    def create_instant_clone_pool(self, params, view_param):
        desktop_spec = self.sud.get_object('ns0:DesktopSpec')
        desktop_spec.type = 'AUTOMATED'

        desktop_settings = self.sud.get_object('ns0:DesktopSettings')
        desktop_settings.enabled = True
        desktop_settings.deleting = False

        log_off_settings = self.sud.get_object('ns0:DesktopLogoffSettings')
        pl_settings_pars = params['pool_settings']
        log_off_settings.powerPolicy = 'ALWAYS_POWERED_ON'
        try:
            tmp_time = int(pl_settings_pars['auto_logoff_time'])
            log_off_settings.automaticLogoffPolicy = 'AFTER'
            log_off_settings.automaticLogoffMinutes = tmp_time
        except:
            log_off_settings.automaticLogoffPolicy = \
                        pl_settings_pars['auto_logoff_time']
        log_off_settings.allowUsersToResetMachines = False
        log_off_settings.allowMultipleSessionsPerUser = False
        log_off_settings.deleteOrRefreshMachineAfterLogoff = 'DELETE'
        log_off_settings.refreshOsDiskAfterLogoff = 'NEVER'

        desktop_settings.logoffSettings = log_off_settings

        display_protocol_settings = self.sud\
                        .get_object('ns0:DesktopDisplayProtocolSettings')
        display_protocol_settings.supportedDisplayProtocols = ['PCOIP','RDP','BLAST']
        display_protocol_settings.defaultDisplayProtocol = pl_settings_pars\
                        ['default_protocol']
        display_protocol_settings.allowUsersToChooseProtocol = String\
                        .is_true(pl_settings_pars['allow_protocol_override'])
        display_protocol_settings.enableHTMLAccess = String\
                        .is_true(pl_settings_pars['enable_html_access'])
        desktop_settings.flashSettings = self.sud .get_object(\
                                                'ns0:DesktopAdobeFlashSettings')
        pcoip_display_settings = self.sud\
                        .get_object('ns0:DesktopPCoIPDisplaySettings')
        pcoip_display_settings.renderer3D = 'DISABLED'
        pcoip_display_settings.enableGRIDvGPUs = False
        pcoip_display_settings.maxNumberOfMonitors = 2
        pcoip_display_settings.maxResolutionOfAnyOneMonitor = 'WUXGA'
        display_protocol_settings.pcoipDisplaySettings = pcoip_display_settings
        desktop_settings.displayProtocolSettings = display_protocol_settings
        desktop_settings.flashSettings.quality = pl_settings_pars['flash_quality']
        desktop_settings.flashSettings.throttling = \
                        pl_settings_pars['flash_throttling']
        desktop_settings.mirageConfigurationOverrides =self.sud .get_object(\
                                    'ns0:DesktopMirageConfigurationOverrides')
        desktop_settings.mirageConfigurationOverrides.enabled = False
        desktop_settings.mirageConfigurationOverrides.overrideGlobalSetting = False
        desktop_spec.desktopSettings = desktop_settings

        adt_spec = self.sud.get_object('ns0:DesktopAutomatedDesktopSpec')
        adt_spec.provisioningType = 'INSTANT_CLONE_ENGINE'

        pool_def_pars = params['pool_definition']
        vc = pool_def_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')
        adt_spec.virtualCenter = vc_id
        user_assignment = self.sud.get_object('ns0:DesktopUserAssignment')
        user_assignment.userAssignment = 'FLOATING'
        adt_spec.userAssignment = user_assignment

        vm_naming_spec = self.sud.get_object('ns0:DesktopVirtualMachineNamingSpec')
        vm_naming_spec.namingMethod = 'PATTERN'

        prov_settings_pars = params['provisioning_settings']
        pattern_naming_settings = self.sud\
                            .get_object('ns0:DesktopPatternNamingSettings')
        pattern_naming_settings.namingPattern = prov_settings_pars\
                        ['name_prefix']
        pattern_naming_settings.maxNumberOfMachines = int(\
                        prov_settings_pars['maximum_count'])
        if prov_settings_pars.has_key('minimum_count'):
            pattern_naming_settings.minNumberOfMachines = int(\
                        prov_settings_pars['minimum_count'])
        else:
            pattern_naming_settings.minNumberOfMachines = int(\
                        prov_settings_pars['maximum_count'])
        if prov_settings_pars.has_key('headroom_count'):
            pattern_naming_settings.numberOfSpareMachines = int(\
                        prov_settings_pars['headroom_count'])
        else:
            pattern_naming_settings.numberOfSpareMachines = int(\
                        prov_settings_pars['maximum_count'])
        pattern_naming_settings.provisioningTime = \
                        prov_settings_pars['provisioning_time']

        vm_naming_spec.patternNamingSettings = pattern_naming_settings
        adt_spec.vmNamingSpec = vm_naming_spec

        vc_provision_settings = self.sud\
                    .get_object('ns0:DesktopVirtualCenterProvisioningSettings')
        vc_provision_settings.enableProvisioning = String.is_true(\
                        prov_settings_pars['provisioning_enabled'])
        vc_provision_settings.stopProvisioningOnError = String.is_true(\
                        prov_settings_pars['stop_provision_on_error'])
        vc_provision_settings.minReadyVMsOnVComposerMaintenance = 0

        vc_setting_pars = params['vc_settings']
        base_image = vc_setting_pars['vm_name']
        base_image_id = self.vc.get_vm_id(vc_id, base_image)
        Validation.validate_param(base_image_id, 'Base image ' + base_image \
                                  + ' is not found.')
        vc_provision_data = self.sud\
                    .get_object('ns0:DesktopVirtualCenterProvisioningData')
        vc_provision_data.parentVm = base_image_id

        base_image_ss_path = vc_setting_pars['snapshot_path']
        base_image_ss_id = self.vc.get_vm_ss_id(vc_id, base_image, \
                                                base_image_ss_path)
        Validation.validate_param(base_image_ss_id, 'Snapshot ' \
                            + base_image_ss_path + ' for base image '
                            + base_image + ' is not found.')

        vc_provision_data.snapshot = base_image_ss_id
        base_image_dc_id = self.vc.get_vm_dc_id(vc_id, base_image)
        Validation.validate_param(base_image_dc_id, 'Datacenter for base image ' \
                                  + base_image + ' is not found.')
        vc_provision_data.datacenter = base_image_dc_id

        vm_folder = vc_setting_pars['folder_name']
        vm_folder_id = self.vc.get_vm_folder_id(base_image_dc_id, vm_folder)
        Validation.validate_param(vm_folder_id, 'Folder ' + vm_folder \
                                  + ' is not found.')
        vc_provision_data.vmFolder = vm_folder_id

        host_or_cluster_name = vc_setting_pars['host_or_cluster_name']
        host_or_cluster_id = self.vc.get_host_or_cluster_id(base_image_dc_id, \
                                                        host_or_cluster_name)
        Validation.validate_param(host_or_cluster_id, 'Cluster ' \
                                  + host_or_cluster_name + ' is not found.')
        vc_provision_data.hostOrCluster = host_or_cluster_id

        resource_pool_name = vc_setting_pars['resource_pool_name']
        resource_pool_id = self.vc.get_resource_pool_id(host_or_cluster_id, \
                                                        resource_pool_name)
        Validation.validate_param(resource_pool_id, 'Resource pool ' \
                                  + resource_pool_name + ' is not found.')
        vc_provision_data.resourcePool = resource_pool_id
        vc_provision_settings.virtualCenterProvisioningData = vc_provision_data

        datastore_paths = vc_setting_pars['datastores']
        ds_settings = self.vc.get_os_datastores(host_or_cluster_id, datastore_paths)
        Validation.validate_param(ds_settings, 'datastores ' \
                                  + datastore_paths + ' are not found.')

        storage_opt_pars = params['storage_optimization']
        vc_storage_settings = self.sud\
                    .get_object('ns0:DesktopVirtualCenterStorageSettings')
        vc_storage_settings.datastores = ds_settings
        vc_storage_settings.useVSan = String.is_true(storage_opt_pars\
                                                         ['use_vsan'])

        view_composer_storage_settings = self.sud\
                    .get_object('ns0:DesktopViewComposerStorageSettings')
        view_composer_storage_settings.useSeparateDatastoresReplicaAndOSDisks = \
                String.is_true(storage_opt_pars
                            ['use_separate_datastore_4_replica_and_os_disks'])
        if view_composer_storage_settings.useSeparateDatastoresReplicaAndOSDisks:
            view_composer_storage_settings.replicaDiskDatastore = self.vc\
                    .get_replica_datastore_id(host_or_cluster_id, datastore_paths)
        view_composer_storage_settings.useNativeSnapshots = False
        space_reclaim_settings = self.sud\
                            .get_object('ns0:DesktopSpaceReclamationSettings')
        space_reclaim_settings.reclaimVmDiskSpace = False
        view_composer_storage_settings.spaceReclamationSettings = \
                        space_reclaim_settings

        persistent_disk_settings = self.sud\
                            .get_object('ns0:DesktopPersistentDiskSettings')
        persistent_disk_settings.redirectWindowsProfile = False

        view_composer_storage_settings.persistentDiskSettings = \
                        persistent_disk_settings

        non_persistent_disk_settings = self.sud\
                            .get_object('ns0:DesktopNonPersistentDiskSettings')
        non_persistent_disk_settings.redirectDisposableFiles = False

        view_composer_storage_settings.nonPersistentDiskSettings = \
                        non_persistent_disk_settings

        vc_storage_settings.viewComposerStorageSettings = \
                        view_composer_storage_settings

        view_storage_accel_settings = self.sud\
                        .get_object('ns0:DesktopViewStorageAcceleratorSettings')
        view_storage_accel_settings. useViewStorageAccelerator = False
        vc_storage_settings.viewStorageAcceleratorSettings = \
                        view_storage_accel_settings
        vc_provision_settings.virtualCenterStorageSettings = vc_storage_settings

        vc_network_settings = self.sud\
                        .get_object('ns0:DesktopVirtualCenterNetworkingSettings')
        networks = vc_setting_pars['networks']
        if networks:
            nic = vc_setting_pars['nic']
            vc_network_settings.nics = self.vc.get_networks(host_or_cluster_id, networks, base_image_ss_id, nic)
        vc_provision_settings.virtualCenterNetworkingSettings = vc_network_settings

        adt_spec.virtualCenterProvisioningSettings = vc_provision_settings

        customize_settings = self.sud\
                        .get_object('ns0:DesktopCustomizationSettings')
        customize_settings.customizationType = "CLONE_PREP"
        customize_settings.reusePreExistingAccounts = False

        domain_name = view_param['domain']
        ad_domain_id = self.instantclonedomain.get_ad_domain_id(domain_name)
        Validation.validate_param(ad_domain_id, 'ADDomainId for ' \
                                  + domain_name + ' is not found.')
        ad_container_infos = self.viewapi.ADContainer_ListByDomain(MOR\
                                .get_mor('ADContainer'), ad_domain_id)
        for ad_container_info in ad_container_infos:
            if ad_container_info.rdn == "CN=Computers":
                ad_container_id = ad_container_info.id
                break
        Validation.validate_param(ad_container_id, 'ADContainerId for ' \
                                  + domain_name + ' is not found.')
        customize_settings.adContainer = ad_container_id
        cloneprep_customize_settings = self.sud\
                        .get_object('ns0:DesktopCloneprepCustomizationSettings')
        instant_clone_domain_admin_id = self.instantclonedomain\
                        .get_instant_clone_domain_admin_id(domain_name)
        if instant_clone_domain_admin_id is None:
            user = view_param['user']
            password = view_param['password']
            logging.info('Adding Instant clone engine domain admin')
            instant_clone_domain_admin_id = self.instantclonedomain\
                .add_instant_clone_domain_admin(domain_name, user, password)
            logging.debug('Instant Clone domain id = ' \
                + str(instant_clone_domain_admin_id))
        cloneprep_customize_settings.instantCloneEngineDomainAdministrator = \
                         instant_clone_domain_admin_id
        customize_settings.cloneprepCustomizationSettings = \
                         cloneprep_customize_settings
        adt_spec.customizationSettings = customize_settings

        desktop_spec.automatedDesktopSpec = adt_spec
        desktop_base = self.sud.get_object('ns0:DesktopBase')
        desktop_base.name = pl_settings_pars['pool_name']
        desktop_base.displayName = pl_settings_pars['pool_name']
        desktop_base.accessGroup = self.get_access_group_id()
        desktop_spec.base = desktop_base

        desktop_id = self.viewapi.Desktop_Create(self.mor, desktop_spec)
        logging.debug('Start creating instant clone pool ' + desktop_base.name + ' ID = ' \
                     + desktop_id.id)
        return desktop_id

    def push_image(self, params):
        '''
        Push image for instant clone desktops
        '''
        pool_settings_pars = params['pool_settings']
        pool_name = pool_settings_pars['pool_name']
        desktop_id = self.get_desktop_id_by_name(pool_name)
        push_image_spec = self.sud.get_object('ns0:DesktopPushImageSpec')

        pool_def_pars = params['pool_definition']
        vc = pool_def_pars['vc']
        vc_id = self.vc.get_id(vc)
        Validation.validate_param(vc_id, 'VC ' + vc + ' is not found')

        vc_setting_pars = params['vc_settings']
        base_image = vc_setting_pars['vm_name']
        base_image_id = self.vc.get_vm_id(vc_id, base_image)
        Validation.validate_param(base_image_id, 'Base image ' + base_image \
                                  + ' is not found.')
        push_image_spec.parentVm = base_image_id

        base_image_ss_path = vc_setting_pars['snapshot_path']
        base_image_ss_id = self.vc.get_vm_ss_id(vc_id, base_image, \
                                                base_image_ss_path)
        Validation.validate_param(base_image_ss_id, 'Snapshot ' \
                                  + base_image_ss_path + ' for base image '
                                  + base_image + ' is not found.')
        push_image_spec.snapshot = base_image_ss_id

        push_image_settings = self.sud.get_object('ns0:DesktopPushImageSettings')
        push_image_settings.logoffSetting = "FORCE_LOGOFF"
        push_image_settings.stopOnFirstError = True
        push_image_spec.settings = push_image_settings
        logging.debug('Start pushing image to the pool ' + pool_name)
        self.viewapi.Desktop_SchedulePushImage(self.mor, desktop_id, push_image_spec)

    def get_all_machines_in_pool(self, pool_name):
        '''
        Queries View for pool name and get selective machine properties like
        agent state, dns name etc
        :param pool_name: Desktop Pool name
        :return: Machine properties in the form of a dictionary
        Key- Machine Name
        Attributes include View Agent State, Computer FQDN
        '''
        desktop_id = self.get_desktop_id_by_name(pool_name)
        query_filter = self.queries.get_equal_filter('base.desktop', desktop_id)
        machines = self.query_machine_names_view(query_filter)
        machine_properties = {}
        for machine in machines:
            machine_name = str(machine.base.name)
            machine_properties[machine_name] = {}
            if hasattr(machine.base, 'basicState'):
                machine_properties[machine_name]['agent_state'] \
                    = str(machine.base.basicState)
            else:
                machine_properties[machine_name]['agent_state'] = 'NULL'
            if hasattr(machine.base, 'dnsName'):
                machine_properties[machine_name]['dns_name'] = \
                    str(machine.base.dnsName)
            else:
                machine_properties[machine_name]['dns_name'] = 'NULL'
        return machine_properties


class Queries(ViewBase):
    '''
    Helper for View Query service APIs
    '''

    def get_mor_type(self):
        return 'QueryService'

    def get_query_def(self, query_filter, entity_type):
        '''
        Create a query definition
        :param query_filter:
        :param entity_type:
        :return:
        '''
        query_def = self.sud.get_object('ns0:QueryDefinition')
        query_def.queryEntityType = entity_type
        query_def.filter = query_filter
        return query_def

    def get_filter(self, filter_type, entity_name, entity_value):
        '''
        Create a filter
        :param filter_type:
        :param entity_name:
        :param entity_value:
        :return:
        '''
        if 'name' in entity_name.lower():
            self.sud.set_value_type('xsd:string')
        query_filter = self.sud.get_object(filter_type)
        query_filter.memberName = entity_name
        query_filter.value = entity_value
        return query_filter

    def get_equal_filter(self, entity_name, entity_value):
        '''
        Create an EQUAL filter
        :param entity_name:
        :param entity_value:
        :return:
        '''
        return self.get_filter('ns0:QueryFilterEquals', entity_name,
                               entity_value)

    def get_and_filter(self, filters):
        '''
        Create an AND filter
        :param filters:
        :return:
        '''
        and_filter = self.sud.get_object('ns0:QueryFilterAnd')
        and_filter.filters = filters
        return and_filter

    def get_or_filter(self, filters):
        '''
        Create an OR filter
        :param filters:
        :return:
        '''
        or_filter = self.sud.get_object('ns0:QueryFilterOr')
        or_filter.filters = filters
        return or_filter

    def query(self, query_filter, entity_type):
        '''
        Search for entities matching given type and filter
        :param query_filter:
        :param entity_type:
        :return:
        '''
        query_def = self.get_query_def(query_filter, entity_type)
        query_def.limit = 1000
        return self.viewapi.QueryService_Query(self.mor, query_def)

    def create(self, query_filter, entity_type):
        '''
        Create the query object for entities matching type and filter
        :param query_filter:
        :param entity_type:
        :return:
        '''
        query_def = self.get_query_def(query_filter, entity_type)
        return self.viewapi.QueryService_Create(self.mor, query_def)

    def get_query_def_without_filter(self, entity_type):
        '''
        Get the query definition without filter
        :param entity_type:
        :return:
        '''
        query_def = self.sud.get_object('ns0:QueryDefinition')
        query_def.queryEntityType = entity_type
        return query_def

    def create_without_filter(self, entity_type):
        '''
        Create a query definition without filter
        :param entity_type:
        :return:
        '''
        query_def = self.get_query_def_without_filter(entity_type)
        return self.viewapi.QueryService_Create(self.mor, query_def)

    def next(self, query_id):
        '''
        Move to the next result in the equery result list
        :param query_id:
        :return:
        '''
        return self.viewapi.QueryService_GetNext(self.mor, query_id)

    def delete(self, query_id):
        '''
        Destroy the query
        :param query_id:
        :return:
        '''
        self.viewapi.QueryService_Delete(self.mor, query_id)


class GlobalSettings(ViewBase):
    '''
    Helper for View global settings APIs
    '''

    def get_mor_type(self):
        return 'GlobalSettings'

    def get_settings(self):
        '''
        Fetch global settings
        :return:
        '''
        return self.viewapi.GlobalSettings_Get(self.mor)

    def update_settings(self, setting_name, setting_val, setting_val_type):
        '''
        Update global settings
        :param setting_name:
        :param setting_val:
        :param setting_val_type:
        :return:
        '''
        self.set_value_type(setting_val_type)
        entry = self.get_object('ns0:MapEntry')
        entry.key = setting_name
        entry.value = setting_val
        self.viewapi.GlobalSettings_Update(self.mor, entry)

    def update_desktopSSOTimeoutMinutes(self, value):
        '''
        Update the SSO timeout
        :param value: timeout in minutes
        :return:
        '''
        self.update_settings('generalData.desktopSSOTimeoutMinutes', value,
                             'xsd:int')


class Misc(ViewBase):
    '''
    Helper for misc View APIs
    '''

    def __init__(self, sud):
        super(Misc, self).__init__(sud)
        self.queries = Queries(sud)

    def get_user_or_group_id(self, login_name, domain_name=None):
        '''
        Fetch the user or group ID object given the name
        :param login_name:
        :param domain_name:
        :return:
        '''
        q_filter = None
        if domain_name:
            filters = []
            filters.append(
                self.queries.get_equal_filter('base.loginName', login_name))
            filters.append(
                self.queries.get_equal_filter('base.domain', domain_name))
            q_filter = self.queries.get_and_filter(filters)
        else:
            q_filter = self.queries.get_equal_filter('base.loginName',
                                                     login_name)

        rt = self.query_user_or_group(q_filter)
        logging.debug(self.get_host() + ': user/group ' + login_name
                      + ' = ' + String.to_string(rt))
        return rt

    def query_user_or_group(self, query_filter):
        '''
        Search for the user or group given a filter
        :param query_filter:
        :return:
        '''
        ret = self.queries.create(query_filter, 'ADUserOrGroupSummaryView')
        query_id = ret.id
        rets = []
        while 'results' in ret:
            for res in ret.results:
                rets.append(res.id)
            ret = self.queries.next(query_id)
        return rets

    def entitle_user_or_group(self, desktop_id, login_name, domain_name=None):
        '''
        Entitle user or group to given desktop
        :param desktop_id:
        :param login_name:
        :param domain_name:
        :return:
        '''
        uog_id = self.get_user_or_group_id(login_name, domain_name)
        ue_base = self.sud.get_object('ns0:UserEntitlementBase')
        ue_base.resource = desktop_id
        ue_base.userOrGroup = uog_id
        logging.debug(self.get_host() + ': entitle ' + login_name
                      + ' to desktop ' + String.to_string(desktop_id))
        self.viewapi.UserEntitlement_Create(MOR.get_mor('UserEntitlement'),
                                            ue_base)

    def entitle_user_or_group_to_app(self, app_id, login_name, domain_name=None):
        '''
        Entitle user or group to given app pool
        :param app_id:
        :param login_name:
        :param domain_name:
        :return:
        '''
        uog_id = self.get_user_or_group_id(login_name, domain_name)
        ue_base = self.sud.get_object('ns0:UserEntitlementBase')
        ue_base.resource = app_id
        ue_base.userOrGroup = uog_id
        logging.debug(self.get_host() + ': Entitle ' + login_name
                      + ' to app ' + String.to_string(app_id))
        self.viewapi.UserEntitlement_Create(MOR.get_mor('UserEntitlement'),
                                            ue_base)

    def update_auto_recovery_disabled(self, desktop_id, val):
        '''
        Update autorecovery disabled attribute
        :param desktop_id:
        :param val:
        :return:
        '''
        self.sud.set_value_type('xsd:boolean')
        entry = self.get_object('ns0:MapEntry')
        entry.key = 'autoRecoveryDisabled'
        entry.value = val
        self.viewapi.AdvancedSettings_Set(MOR.get_mor('AdvancedSettings'),
                                          desktop_id, entry)


class Sessions(ViewBase):
    '''
    Helper for View session APIs
    '''

    def __init__(self, sud):
        super(Sessions, self).__init__(sud)
        self.queries = Queries(sud)
        self.desktops = Desktops(sud)
        self.apps = Apps(sud)

    def get_mor_type(self):
        return 'Session'

    def get_local_session(self, session_type, session_state, query_filters):
        '''
        Fetch a list of sessions matching given type, state, and filters
        :param session_type:
        :param session_state:
        :param query_filters:
        :return:
        '''
        filters = []
        if session_type in ('DESKTOP', 'APPLICATION'):
            query_filter = self.queries \
                .get_equal_filter('sessionData.sessionType', session_type)
            filters.append(query_filter)

        if session_state in ('CONNECTED', 'DISCONNECTED'):
            query_filter = self.queries \
                .get_equal_filter('sessionData.sessionState', session_state)
            filters.append(query_filter)

        if query_filters:
            if query_filters is list:
                filters.extend(query_filters)
            else:
                filters.extend([query_filters])

        filter_tmp = None
        if len(filters) == 1:
            filter_tmp = filters[0]
        elif len(filters) > 1:
            filter_tmp = self.queries.get_and_filter(filters)

        query_id = None
        try:
            ret = self.queries.create(filter_tmp, 'SessionLocalSummaryView')
            query_id = ret.id
            sessions = []
            while 'results' in ret:
                for session in ret.results:
                    sessions.append(session)
                ret = self.queries.next(query_id)
            return sessions
        finally:
            if query_id:
                self.queries.delete(query_id)

    def get_desktop_sessions(self, session_state, desktop_name):
        '''
        Fetch desktop sessions matching given state and desktop name
        :param session_state:
        :param desktop_name:
        :return:
        '''
        desktop_id = self.desktops.get_desktop_id_by_name(desktop_name)
        query_filter = self.queries.get_equal_filter('referenceData.desktop',
                                                     desktop_id)
        return self.get_local_session('DESKTOP', session_state, query_filter)

    def get_desktop_session_count(self, session_state, desktop_name):
        '''
        Fetch the count of desktop sessions matching given state and desktop
        name
        :param session_state:
        :param desktop_name:
        :return:
        '''
        sessions = self.get_desktop_sessions(session_state, desktop_name)
        return len(sessions)

    def get_app_sessions(self, session_state, app_name):
        '''
        Fetch application sessions matching given state and app name
        :param session_state:
        :param app_name:
        :return:
        '''
        farm_id = self.apps.get_farm_id_by_app_name(app_name)
        query_filter = self.queries.get_equal_filter('referenceData.farm',
                                                     farm_id)
        return self.get_local_session('APPLICATION', session_state, query_filter)

    def get_app_session_count(self, session_state, app_name):
        '''
        Fetch the count of app sessions matching given state and app
        name
        :param session_state:
        :param app_name:
        :return:
        '''
        sessions = self.get_app_sessions(session_state, app_name)
        return len(sessions)


class View(ISession):
    '''
    Wrapper for all View APIs
    '''

    def __init__(self, host, user, password, domain, wsdl_file):
        '''
        Constructor
        '''
        self.host = host
        self.user = user
        self.password = password
        self.domain = domain
        self.wsdl_file = wsdl_file
        if self.wsdl_file.startswith('/'):
            self.wsdl_file = self.wsdl_file[1:]
        self.wsdl_file = 'file:///' + self.wsdl_file
        self.wsdl_file = self.wsdl_file.replace('\\', '/')
        print("No error: WSDL: {0}".format(self.wsdl_file))

        self.sud = Suds(self.wsdl_file, 'https://' + host + '/view-vlsi/sdk')
        self.viewapi = self.sud.get_svc()

        self.global_settings = GlobalSettings(self.sud)
        self.desktops = Desktops(self.sud)
        self.sessions = Sessions(self.sud)
        self.vc = VC(self.sud)
        self.misc = Misc(self.sud)
        self.connection_servers = ConnectionServer(self.sud)
        self.instantclonedomain = InstantCloneDomain(self.sud)
        self.farms = Farms(self.sud)
        self.apps = Apps(self.sud)

    def get_session_key(self):
        return 'ViewAPI|' + self.host + '|' + self.user

    def is_logged_in(self):
        # temporarily disable error logging from suds.client while checking
        from logging import NullHandler
        handler = NullHandler()
        logger = logging.getLogger('suds.client')
        propagate = logger.propagate
        logger.addHandler(handler)
        logger.propagate = False
        ret = False
        try:
            self.get_settings()
            ret = True
        except:
            pass
        finally:
            logger.removeHandler(handler)
            logger.propagate = propagate

        return ret

    def login(self):
        '''
        Login to View API
        :return:
        '''
        if self.is_logged_in():
            return
        ss = self.sud.get_object('ns0:SecureString')
        ss.utf8String = base64.b64encode(self.password.encode('utf-8'))
        self.viewapi \
            .AuthenticationManager_Login(MOR.get_mor('AuthenticationManager'),
                                         self.user, ss, self.domain)

    def logout(self):
        '''
        Logout of View API
        :return:
        '''
        self.viewapi \
            .AuthenticationManager_Logout(MOR.get_mor('AuthenticationManager'))

    def get_settings(self):
        '''
        Fetch global settings
        :return:
        '''
        return self.global_settings.get_settings()

    def update_desktopSSOTimeoutMinutes(self, value):
        '''
        Update desktop SSO timeout
        :param value:
        :return:
        '''
        self.global_settings.update_desktopSSOTimeoutMinutes(value)

    def get_machines_in_state(self, desktop_name, machine_state):
        '''
        Fetch machines in given state and given desktop
        :param desktop_name:
        :param machine_state:
        :return:
        '''
        self.login()
        return self.desktops.get_machines_in_state(desktop_name, machine_state)

    def get_rds_machines_in_state(self, rds_name, machine_state):
        '''
        Fetch rds servers in the given state
        :param rds_name:
        :param machine_state:
        :return:
        '''
        self.login()
        return self.desktops.get_rds_machines_in_state(rds_name, machine_state)

    def get_farm_rdsh_in_state(self,farm_name, rdsh_state):
        '''
        Fetch RDSH state in the given farm
        :param farm_name:
        :param rdsh_state:
        :return:
        '''
        self.login()
        return self.farms.get_farm_rdsh_in_state(farm_name,rdsh_state)

    def get_desktop_session_count(self, session_state, desktop_name):
        '''
        Fetch the count of desktop sessions matching given state and desktop
        name
        :param session_state:
        :param desktop_name:
        :return:
        '''
        return self.sessions.get_desktop_session_count(session_state,
                                                       desktop_name)

    def get_desktop_sessions(self, session_state, desktop_name):
        '''
        Fetch desktop session objects matching given state and desktop name
        :param session_state:
        :param desktop_name:
        :return:
        '''
        self.login()
        return self.sessions.get_desktop_sessions(session_state, desktop_name)

    def get_app_session_count(self, session_state, app_name):
        '''
        Fetch the count of app sessions matching given state and app pool
        name
        :param session_state:
        :param app_name:
        :return:
        '''
        return self.sessions.get_app_session_count(session_state,
                                                   app_name)

    def get_app_sessions(self, session_state, app_name):
        '''
        Fetch app session objects matching given state and app pool name
        :param session_state:
        :param app_name:
        :return:
        '''
        self.login()
        return self.sessions.get_app_sessions(session_state, app_name)

    def create_automated_desktop(self, pool_params):
        '''
        Create automated desktop
        :param pool_params:
        :return:
        '''
        return self.desktops.create_automated_desktop(pool_params)

    def create_automated_full_desktop(self, pool_params):
        '''
        Create automated full clone desktop
        :param pool_params:
        :return:
        '''
        return self.desktops.create_automated_full_desktop(pool_params)

    def create_linked_clone_farm(self, pool_params):
        '''
        Create automated Farm with linked clones
        :param pool_params:
        :return:
        '''
        return self.farms.create_linked_clone_farm(pool_params)

    def create_instant_clone_farm(self, pool_params, view_param):
        '''
        Create automated Farm with instant clones
        :param pool_params:
        :param view_param
        :return:
        '''
        return self.farms.create_instant_clone_farm(pool_params,view_param)

    def create_rds_desktop(self, pool_params):
        '''
        Create rds desktop
        :param pool_params:
        :return:
        '''
        return self.desktops.create_rds_desktop(pool_params)

    def create_app(self, pool_params):
        '''
        Create application pool
        :param pool_params:
        :return:
        '''
        return self.apps.create_app(pool_params)

    def delete_desktop(self, desktop_name):
        '''
        Destroy given desktop
        :param desktop_name:
        :return:
        '''
        self.desktops.delete_by_name(desktop_name)

    def delete_all_desktops(self):
        '''
        Destroy all desktops
        :return:
        '''
        self.desktops.delete_all(None)

    def delete_all_rds_desktops(self):
        '''
        Destroy all RDS desktops
        :return:
        '''
        self.desktops.delete_all('RDS')

    def app_delete(self, app_name):
        '''
        Delete app pool
        :param app_name:
        :return:
        '''
        self.apps.app_delete_by_name(app_name)

    def refresh_desktop(self, desktop_name):
        '''
        Refresh given desktop
        :param desktop_name:
        :return:
        '''
        self.desktops.refresh(desktop_name)

    def rebalance_desktop(self, desktop_name):
        '''
        Rebalance given desktop
        :param desktop_name:
        :return:
        '''
        self.desktops.rebalance(desktop_name)

    def recompose_desktop(self, desktop_name, vc_host, parent_vm,
                          parent_snapshot,stopOnFirstError):
        '''
        Recomposer given desktop
        :param desktop_name:
        :param vc_host:
        :param parent_vm:
        :param parent_snapshot:
        :return:
        '''
        self.desktops.recompose(desktop_name, vc_host, parent_vm,
                                parent_snapshot,stopOnFirstError)

    def recompose_farm(self,pool_params):
        '''
        Recompose given farm
        :param pool_params:
        :return:
        '''
        self.farms.recompose_farm(pool_params)

    def farm_maintenance(self, pool_params, ss_name=None):
        '''
        Maintain the given IC farm
        :param pool_params:
        :return:
        '''
        self.farms.farm_maintenance(pool_params, ss_name)

    def delete_farm(self, farm_params):
        '''
        Delete the given farm
        :param farm_params:
        :return:
        '''
        self.farms.delete_farm(farm_params)

    def push_image(self, pool_params):
        '''
        Push image to instant clone pools
        :param pool_params:
        :return:
        '''
        self.desktops.push_image(pool_params)

    def get_ad_user_or_group(self, user_or_group_login_name):
        '''
        Fetch the user or group given the name
        :param user_or_group_login_name:
        :return:
        '''
        return self.misc.get_user_or_group_id(user_or_group_login_name)

    def entitle_user_or_group(self, desktop_name, user_or_group_login_name,
                              domain_name=None):
        '''
        Entitle the given user or group to given desktop
        :param desktop_name:
        :param user_or_group_login_name:
        :param domain_name:
        :return:
        '''
        desktop_id = self.desktops.get_desktop_id_by_name(desktop_name)
        return self.misc.entitle_user_or_group(desktop_id,
                                               user_or_group_login_name,
                                               domain_name)

    def entitle_user_or_group_to_app(self, app_name, user_or_group_login_name, domain_name=None):
        '''
        Entitle the given user or group to the app pool
        :param app_name:
        :param user_or_group_login_name:
        :param domain_name:
        :return:
        '''
        app_id = self.apps.get_app_id_by_name(app_name)
        return self.misc.entitle_user_or_group_to_app(app_id, user_or_group_login_name, domain_name)

    def update_auto_recovery_disabled(self, desktop_id, val):
        '''
        Update the auto-recovery-disabled attribute of given desktop
        :param desktop_id:
        :param val:
        :return:
        '''
        self.misc.update_auto_recovery_disabled(desktop_id, val)
        logging.debug('auto recovery disabled is now ' + str(val))

    def add_vc(self, vc_host, vc_port, vc_user, vc_password, composer_host,
               composer_port, composer_user, composer_pwd, composer_type):
        '''
        Add VC to view
        :param vc_host:
        :param vc_port:
        :param vc_user:
        :param vc_password:
        :param composer_host:
        :param composer_port:
        :param composer_user:
        :param composer_pwd:
        :param composer_type:
        :return:
        '''
        return self.vc.create(vc_host, vc_port, vc_user, vc_password,
                              composer_host,
                              composer_port, composer_user, composer_pwd,
                              composer_type)

    def get_vc(self, vc_host):
        '''
        Get VC details
        :param vc_host:
        :return:
        '''
        return self.vc.get_id(vc_host)

    def add_composer_domain(self, domain_name, user_name, password, vc_id):
        '''
        Add view composer domain
        :param domain_name:
        :param user_name:
        :param password:
        :param vc_id:
        :return:
        '''
        return self.vc.add_composer_domain(domain_name, user_name, password,
                                           vc_id)

    def desktop_pool_exists(self, desktop_name):
        '''
        Determine if given desktop exists
        :param desktop_name:
        :return:
        '''
        return self.desktops.get_desktop_id_by_name(desktop_name) != None

    def set_ss_pairing_password(self, cs_name, password,
                                timeout_mins=600):
        self.connection_servers.set_pairing_password(cs_name, password,
                                                     timeout_mins)

    def create_instant_clone_pool(self, pool_params, view_param):
        '''
        Create instant clone pool
        :param pool_params:
        :return: pool_id
        '''
        return self.desktops.create_instant_clone_pool(pool_params, view_param)

    def farm_exists(self, farm_name):
        '''
        Check if the given farm exists
        :param farm_name:
        :return:
        '''
        return self.farms.get_farm_id_by_name(farm_name)

    def app_pool_exists(self, app_pool_name):
        '''
        Determine if given app pool exists
        :param app_pool_name:
        :return:
        '''
        return self.apps.get_app_id_by_name(app_pool_name) != None

    def get_desktop_type(self, pool_name):
        '''
        Get the desktop pool type (AUTOMATED/MANUAL/RDS)
        :param pool_name:
        :return:
        '''
        return self.desktops.get_desktop_type(pool_name)

    def get_farm_id_by_app_name(self, app_pool_name):
        '''
        Get the farm id of the farm to which app_ppol_name belongs to
        :param app_pool_name:
        :return:
        '''
        return self.apps.get_farm_id_by_app_name(app_pool_name)

    def get_farm_id_by_name(self,farm_name):
        '''
        Get the farm id given its name
        :param farm_name:
        :return:
        '''
        return self.farms.get_farm_id_by_name(farm_name)

    def get_desktop_id_by_name(self, desktop_name):
        '''
        Get the desktop id given its name
        :param desktop_name:
        :return:
        '''
        return self.desktops.get_desktop_id_by_name(desktop_name)

    def get_machine_props_in_pool(self, pool_name):
        '''
        Calls get_all_machines_in_pool() from Desktop Class
        :param pool_name:
        :return: Machine properties in the form of a dictionary
        Key- Machine Name
        Attributes include View Agent State, Computer FQDN
        '''
        return self.desktops.get_all_machines_in_pool(pool_name)

    def enable_saml(self,name):
        '''
        Calls enable_saml in the connectionserver class
        This will allow the broker to do saml auth
        returns None
        '''
        return self.connection_servers.enable_saml(name)


class ConnectionServer(ViewBase):
    '''
    Helper for View Connection Server APIs
    '''

    def get_mor_type(self):
        return 'ConnectionServer'

    def wait_server(self, name):
        MAX_WAIT_SEC = Timings().get_timeout_sec_4()
        start_time = datetime.now()
        elapsed = 0
        msg = self.get_host() + ': waiting for connection server [' + name \
              + '] to be ready'

        while elapsed < MAX_WAIT_SEC:
            svr = self.get_server_by_name(name)
            if svr:
                return svr
            time.sleep(Timings().get_task_wait_interval_sec_3())
            elapsed = (datetime.now() - start_time).total_seconds()
            logging.debug(msg)

    def get_server_by_name(self, name):
        '''
        Fetch a connection server object given its name
        :param name: this is the name displayed in the View admin UI under
        View configuration/Servers/Connection Servers
        :return:
        '''
        name = name.lower()
        servers = self.viewapi.ConnectionServer_List(self.mor)
        for server in servers:
            if server.general.name.lower() == name:
                return server
        logging.debug(self.get_host() + ': connection server [' + name
                      + '] is not found')

    def set_pairing_password(self, name, password, timeout_min):
        '''
        Set the security server pairing password for the given connection server
        :param name: this is the name displayed in the View admin UI under
        View configuration/Servers/Connection Servers
        :param password:
        :param timeout_min:
        :return:
        '''

        server = self.wait_server(name)
        if not server:
            raise Exception(self.get_host() + ': connection server '
                            + name + ' is not found!')

        entry = self.get_object('ns0:MapEntry')
        entry.key = 'securityServerPairing'

        pairing_data = self.sud.get_object(
            'ns0:ConnectionServerSecurityServerPairingData')
        ss = self.sud.get_object('ns0:SecureString')
        ss.utf8String = base64.b64encode(password.encode('utf-8'))
        pairing_data.pairingPassword = ss
        pairing_data.timeoutMinutes = timeout_min
        entry.value = pairing_data

        logging.debug(self.get_host()
                      + ': setting security server pairing password [password='
                      + password + ', timeout minutes=' + str(
            timeout_min) + ']')
        self.viewapi.ConnectionServer_Update(self.mor, server.id, entry)

    def enable_saml(self,name):
        server = self.wait_server(name)
        if not server:
            raise Exception(self.get_host() + ': connection server '
                            + name + ' is not found!')
        entry = self.get_object('ns0:MapEntry')
        entry.key = 'authentication.samlConfig.samlSupport'
        entry.value = 'MULTI_ENABLED'
        self.viewapi.ConnectionServer_Update(self.mor, server.id, entry)


