
(function () {
  'use strict';

  angular
    .module('wingrade', [
      'wingrade.config',
      'wingrade.routes',
      'wingrade.accounts',
      'wingrade.authentication',
      'wingrade.layout',
      'wingrade.utils',
      'wingrade.vdis',
      'wingrade.vcenters'
    ]);

  angular
    .module('wingrade.config', []);

  angular
    .module('wingrade.routes', ['ngRoute']);

  angular
    .module('wingrade')
    .run(run);

  run.$inject = ['$http'];

  /**
   * @name run
   * @desc Update xsrf $http headers to align with Django's defaults
   */
  function run($http) {
    $http.defaults.xsrfHeaderName = 'X-CSRFToken';
    $http.defaults.xsrfCookieName = 'csrftoken';
  }
})();
