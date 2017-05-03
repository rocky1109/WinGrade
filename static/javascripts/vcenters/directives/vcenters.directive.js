/**
 * VCenters
 * @namespace wingrade.vcenters.directives
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vcenters.directives')
    .directive('vcenters', vcenters);

  /**
   * @namespace VCenters
   */
  function vcenters() {
    /**
     * @name directive
     * @desc The directive to be returned
     * @memberOf wingrade.vcenters.directives.VCenters
     */
    var directive = {
      controller: 'VCentersController',
      controllerAs: 'vm',
      restrict: 'E',
      scope: {
        vcenters: '='
      },
      templateUrl: '/static/templates/vcenters/vcenters.html'
    };

    return directive;
  }
})();
