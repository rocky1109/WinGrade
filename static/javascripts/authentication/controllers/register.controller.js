/**
 * Register controller
 * @namespace wingrade.authentication.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.authentication.controllers')
    .controller('RegisterController', RegisterController);

  RegisterController.$inject = ['$location', '$scope', 'Authentication'];

  /**
   * @namespace RegisterController
   */
  function RegisterController($location, $scope, Authentication) {
    var vm = this;

    vm.register = register;

    activate();

    /**
     * @name activate
     * @desc Actions to be performed when this controller is instantiated
     * @memberOf wingrade.authentication.controllers.RegisterController
     */
    function activate() {
      // If the user is authenticated, they should not be here.
      if (Authentication.isAuthenticated()) {
        $location.url('/');
      }
    }

    /**
     * @name register
     * @desc Register a new user
     * @memberOf wingrade.authentication.controllers.RegisterController
     */
    function register() {
      Authentication.register(vm.email, vm.password, vm.username);
    }
  }
})();
