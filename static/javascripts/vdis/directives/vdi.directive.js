/**
 * VDI
 * @namespace wingrade.vdis.directives
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vdis.directives')
    .directive('vdi', vdi);

  /**
   * @namespace VDI
   */
  function vdi() {
    /**
     * @name directive
     * @desc The directive to be returned
     * @memberOf wingrade.vdis.directives.VDI
     */
    var directive = {
      restrict: 'E',
      scope: {
        vdi: '='
      },
      templateUrl: '/static/templates/vdis/vdi.html'
    };

    return directive;
  }
})();
