/**
 * VCenters
 * @namespace wingrade.vcenters.services
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vcenters.services')
    .factory('VCenters', VCenters);

  VCenters.$inject = ['$http'];

  /**
   * @namespace VCenters
   * @returns {Factory}
   */
  function VCenters($http) {
    var VCenters = {
      all: all,
      get: get,
      create: create,
      update: update
    };

    return VCenters;

    ////////////////////
    
    /**
     * @name all
     * @desc Get all VCenters
     * @returns {Promise}
     * @memberOf wingrade.vcenters.services.VCenters
     */
    function all() {
      return $http.get('/api/v1/vcenters/');
    }


    /**
     * @name create
     * @desc Create a new VCenter
     * @param {string} content The content of the new VCenter
     * @returns {Promise}
     * @memberOf wingrade.vcenters.services.VCenters
     */
    function create(address, user, password, domain) {
      return $http.post('/api/v1/vcenters/', {
        address: address,
        user: user,
        password: password,
        domain: domain
      });
    }


    /**
     * @name get
     * @desc Get the VCenters of a given user
     * @param {string} username The username to get VCenters for
     * @returns {Promise}
     * @memberOf wingrade.vcenters.services.VCenters
     */
    function get(id) {
      return $http.get('/api/v1/vcenters/' + id + '/');
      //return $http.get('/api/v1/vdis/' + id + '/vcenters/');
    }

    function update(id, vcenter) {
      return $http.put('/api/v1/vcenters/' + id + '/', vcenter);
    }
  }
})();
