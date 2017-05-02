/**
 * VDIs
 * @namespace wingrade.vdis.directives
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vdis.directives')
    .directive('vdis', vdis);

  /**
   * @namespace VDIs
   */
  function vdis() {
    /**
     * @name directive
     * @desc The directive to be returned
     * @memberOf wingrade.vdis.directives.VDIs
     */
    var directive = {
      controller: 'VDIsController',
      controllerAs: 'vm',
      restrict: 'E',
      scope: {
        vdis: '='
      },
      templateUrl: '/static/templates/vdis/vdis.html'
    };

    return directive;
  }
})();
