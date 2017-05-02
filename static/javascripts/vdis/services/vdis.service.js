/**
 * VDIs
 * @namespace wingrade.vdis.services
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vdis.services')
    .factory('VDIs', VDIs);

  VDIs.$inject = ['$http'];

  /**
   * @namespace VDIs
   * @returns {Factory}
   */
  function VDIs($http) {
    var VDIs = {
      all: all,
      get: get,
      create: create
    };

    return VDIs;

    ////////////////////
    
    /**
     * @name all
     * @desc Get all VDIs
     * @returns {Promise}
     * @memberOf wingrade.vdis.services.VDIs
     */
    function all() {
      return $http.get('/api/v1/vdis/');
    }


    /**
     * @name create
     * @desc Create a new VDI
     * @param {string} content The content of the new VDI
     * @returns {Promise}
     * @memberOf wingrade.vdis.services.VDIs
     */
    function create(address, user, password, domain) {
      return $http.post('/api/v1/vdis/', {
        address: address,
        user: user,
        password: password,
        domain: domain
      });
    }


    /**
     * @name get
     * @desc Get the VDIs of a given user
     * @param {string} username The username to get VDIs for
     * @returns {Promise}
     * @memberOf wingrade.vdis.services.VDIs
     */
    function get(id) {
      return $http.get('/api/v1/accounts/' + id + '/vdis/');
    }
  }
})();
