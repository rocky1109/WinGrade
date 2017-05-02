/**
 * IndexController
 * @namespace wingrade.layout.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.layout.controllers')
    .controller('IndexController', IndexController);

  IndexController.$inject = ['$scope', 'Authentication', 'VDIs', 'Snackbar'];

  /**
   * @namespace IndexController
   */
  function IndexController($scope, Authentication, VDIs, Snackbar) {
    var vm = this;

    vm.isAuthenticated = Authentication.isAuthenticated();
    vm.vdis = [];

    activate();

    /**
     * @name activate
     * @desc Actions to be performed when this controller is instantiated
     * @memberOf wingrade.layout.controllers.IndexController
     */
    function activate() {
      VDIs.all().then(vdisSuccessFn, vdisErrorFn);

      $scope.$on('vdi.created', function (event, vdi) {
        vm.vdis.unshift(vdi);
      });

      $scope.$on('vdi.created.error', function () {
        vm.vdis.shift();
      });


      /**
       * @name vdisSuccessFn
       * @desc Update thoughts array on view
       */
      function vdisSuccessFn(data, status, headers, config) {
        vm.vdis = data.data;
      }


      /**
       * @name vdisErrorFn
       * @desc Show snackbar with error
       */
      function vdisErrorFn(data, status, headers, config) {
        Snackbar.error(data.error);
      }
    }
  }
})();
