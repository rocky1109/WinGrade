(function () {
  'use strict';

  angular
    .module('wingrade.authentication', [
      'wingrade.authentication.controllers',
      'wingrade.authentication.services'
    ]);

  angular
    .module('wingrade.authentication.controllers', []);

  angular
    .module('wingrade.authentication.services', ['ngCookies']);
})();
