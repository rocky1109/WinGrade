(function () {
  'use strict';

  angular
    .module('wingrade.vdis', [
      'wingrade.vdis.controllers',
      'wingrade.vdis.directives',
      'wingrade.vdis.services'
    ]);

  angular
    .module('wingrade.vdis.controllers', []);

  angular
    .module('wingrade.vdis.directives', ['ngDialog']);

  angular
    .module('wingrade.vdis.services', []);
})();
