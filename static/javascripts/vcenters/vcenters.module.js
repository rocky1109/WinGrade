(function () {
  'use strict';

  angular
    .module('wingrade.vcenters', [
      'wingrade.vcenters.controllers',
      'wingrade.vcenters.directives',
      'wingrade.vcenters.services'
    ]);

  angular
    .module('wingrade.vcenters.controllers', []);

  angular
    .module('wingrade.vcenters.directives', ['ngDialog']);

  angular
    .module('wingrade.vcenters.services', []);
})();
