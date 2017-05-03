/**
 * VCenter
 * @namespace wingrade.vcenters.directives
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vcenters.directives')
    .directive('vcenter', vcenter);

  /**
   * @namespace VCenter
   */
  function vcenter() {
    /**
     * @name directive
     * @desc The directive to be returned
     * @memberOf wingrade.vcenters.directives.VCenter
     */
    var directive = {
      restrict: 'E',
      scope: {
        vcenter: '='
      },
      templateUrl: '/static/templates/vcenters/vcenter.html'
    };

    return directive;
  }
})();
