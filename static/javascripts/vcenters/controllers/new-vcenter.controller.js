/**
 * NewVCenterController
 * @namespace wingrade.vcenters.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vcenters.controllers')
    .controller('NewVCenterController', NewVCenterController);

  NewVCenterController.$inject = ['$rootScope', '$scope', 'Authentication', 'Snackbar', 'VCenters'];

  /**
   * @namespace NewVCenterController
   */
  function NewVCenterController($rootScope, $scope, Authentication, Snackbar, VCenters) {
    var vm = this;

    vm.submit = submit;

    /**
     * @name submit
     * @desc Create a new VCenter
     * @memberOf wingrade.vcenters.controllers.NewVCenterController
     */
    function submit() {
      $rootScope.$broadcast('vcenter.created', {
        address: vm.address,
        user: vm.user,
        password: vm.password,
        author: {
          username: Authentication.getAuthenticatedAccount().username
        }
      });

      $scope.closeThisDialog();

      VCenters.create(vm.address, vm.user, vm.password).then(createVCenterSuccessFn, createVCenterErrorFn);


      /**
       * @name createVCenterSuccessFn
       * @desc Show snackbar with success message
       */
      function createVCenterSuccessFn(data, status, headers, config) {
        Snackbar.show('Success! VCenter created.');
      }

      
      /**
       * @name createVCenterErrorFn
       * @desc Propogate error event and show snackbar with error message
       */
      function createVCenterErrorFn(data, status, headers, config) {
        $rootScope.$broadcast('vcenter.created.error');
        Snackbar.error(data.error);
      }
    }
  }
})();
