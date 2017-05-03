/**
 * IndexController
 * @namespace wingrade.layout.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.layout.controllers')
    .controller('VDIHomeController', VDIHomeController);

  VDIHomeController.$inject = ['$scope', 'VDIs', 'VCenters', 'Snackbar'];

  /**
   * @namespace IndexController
   */
  function VDIHomeController($scope, VDIs, VCenters, Snackbar) {
    var vm = this;

    vm.isAuthenticated = true; //Authentication.isAuthenticated();
    vm.vcenters = [];

    activate();

    /**
     * @name activate
     * @desc Actions to be performed when this controller is instantiated
     * @memberOf wingrade.layout.controllers.IndexController
     */
    function activate() {
      VCenters.all().then(vcentersSuccessFn, vcentersErrorFn);

      $scope.$on('vcenter.created', function (event, vcenter) {
        vm.vcenters.unshift(vcenter);
      });

      $scope.$on('vcenter.created.error', function () {
        vm.vcenters.shift();
      });


      /**
       * @name vdisSuccessFn
       * @desc Update thoughts array on view
       */
      function vcentersSuccessFn(data, status, headers, config) {
        vm.vcenters = data.data;
      }


      /**
       * @name vdisErrorFn
       * @desc Show snackbar with error
       */
      function vcentersErrorFn(data, status, headers, config) {
        Snackbar.error(data.error);
      }
    }
  }
})();
