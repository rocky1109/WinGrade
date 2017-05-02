/**
 * NewVDIController
 * @namespace wingrade.vdis.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vdis.controllers')
    .controller('NewVDIController', NewVDIController);

  NewVDIController.$inject = ['$rootScope', '$scope', 'Authentication', 'Snackbar', 'VDIs'];

  /**
   * @namespace NewVDIController
   */
  function NewVDIController($rootScope, $scope, Authentication, Snackbar, VDIs) {
    var vm = this;

    vm.submit = submit;

    /**
     * @name submit
     * @desc Create a new VDI
     * @memberOf wingrade.vdis.controllers.NewVDIController
     */
    function submit() {
      $rootScope.$broadcast('vdi.created', {
        address: vm.address,
        user: vm.user,
        password: vm.password,
        domain: vm.domain,
        author: {
          username: Authentication.getAuthenticatedAccount().username
        }
      });

      $scope.closeThisDialog();

      VDIs.create(vm.address, vm.user, vm.password, vm.domain).then(createVDISuccessFn, createVDIErrorFn);


      /**
       * @name createVDISuccessFn
       * @desc Show snackbar with success message
       */
      function createVDISuccessFn(data, status, headers, config) {
        Snackbar.show('Success! VDI created.');
      }

      
      /**
       * @name createVDIErrorFn
       * @desc Propogate error event and show snackbar with error message
       */
      function createVDIErrorFn(data, status, headers, config) {
        $rootScope.$broadcast('vdi.created.error');
        Snackbar.error(data.error);
      }
    }
  }
})();
