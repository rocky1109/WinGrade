
/**
 * AccountSettingsController
 * @namespace wingrade.accounts.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vcenters.controllers')
    .controller('EditVCenterController', EditVCenterController);

  EditVCenterController.$inject = [
    '$location', '$routeParams', 'Authentication', 'VCenters', 'Snackbar'
  ];

  /**
   * @namespace AccountSettingsController
   */
  function EditVCenterController($location, $routeParams, Authentication ,VCenters, Snackbar) {
    var vm = this;

    vm.update = update;

    activate();


    /**
     * @name activate
     * @desc Actions to be performed when this controller is instantiated.
     * @memberOf wingrade.accounts.controllers.AccountSettingsController
     */
    function activate() {
    var authenticatedAccount = Authentication.getAuthenticatedAccount();
      var id = $routeParams.id;

      // Redirect if not logged in
      if (!authenticatedAccount) {
        $location.url('/');
        Snackbar.error('You are not authorized to view this page.');
      }

      VCenters.get(id).then(detailsSuccessFn, detailsErrorFn);

      /**
       * @name accountSuccessFn
       * @desc Update `account` for view
       */
      function detailsSuccessFn(data, status, headers, config) {
        vm.vcenter = data.data;
      }

      /**
       * @name accountErrorFn
       * @desc Redirect to index
       */
      function detailsErrorFn(data, status, headers, config) {
        $location.url('/');
        Snackbar.error('That Virtual Center does not exist.');
      }
    }

    /**
     * @name update
     * @desc Update this account
     * @memberOf wingrade.accounts.controllers.AccountSettingsController
     */
    function update() {
      var id = vm.vcenter.id;

      VCenters.update(id, vm.vcenter).then(detailsSuccessFn, detailsErrorFn);

      //Account.update(username, vm.account).then(accountSuccessFn, accountErrorFn);

      /**
       * @name accountSuccessFn
       * @desc Show success snackbar
       */
      function detailsSuccessFn(data, status, headers, config) {
        $location.url('/vcenters');
        Snackbar.show('Virtual Center has been updated.');
      }


      /**
       * @name accountErrorFn
       * @desc Show error snackbar
       */
      function detailsErrorFn(data, status, headers, config) {
        Snackbar.error(data.error);
      }
    }
  }
})();
