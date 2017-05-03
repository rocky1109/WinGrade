/**
 * VCentersController
 * @namespace wingrade.vcenters.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vcenters.controllers')
    .controller('VCentersController', VCentersController);

  VCentersController.$inject = ['$scope'];

  /**
   * @namespace VCentersController
   */
  function VCentersController($scope) {
    var vm = this;

    vm.columns_vc = [];

    activate();


    /**
     * @name activate
     * @desc Actions to be performed when this controller is instantiated
     * @memberOf wingrade.vcenters.controllers.VCentersController
     */
    function activate() {
      $scope.$watchCollection(function () { return $scope.vcenters; }, render);
      $scope.$watch(function () { return $(window).width(); }, render);
    }
    

    /**
     * @name calculateNumberOfColumns
     * @desc Calculate number of columns_vc based on screen width
     * @returns {Number} The number of columns_vc containing VCenters
     * @memberOf wingrade.vcenters.controllers.VCentersControllers
     */
    function calculateNumberOfColumns() {
      var width = $(window).width();

      if (width >= 1200) {
        return 8;
      } else if (width >= 992) {
        return 6;
      } else if (width >= 768) {
        return 4;
      } else {
        return 2;
      }
    }


    /**
     * @name approximateShortestColumn
     * @desc An algorithm for approximating which column is shortest
     * @returns The index of the shortest column
     * @memberOf wingrade.vcenters.controllers.VCentersController
     */
    function approximateShortestColumn() {
      var scores = vm.columns_vc.map(columnMapFn);

      return scores.indexOf(Math.min.apply(this, scores));

      
      /**
       * @name columnMapFn
       * @desc A map function for scoring column heights
       * @returns The approximately normalized height of a given column
       */
      function columnMapFn(column) {
        var lengths = column.map(function (element) {
          return element.address.length;
        });

        return lengths.reduce(sum, 0) * column.length;
      }


      /**
       * @name sum
       * @desc Sums two numbers
       * @params {Number} m The first number to be summed
       * @params {Number} n The second number to be summed
       * @returns The sum of two numbers
       */
      function sum(m, n) {
        return m + n;
      }
    }


    /**
     * @name render
     * @desc Renders VCenters into columns_vc of approximately equal height
     * @param {Array} current The current value of `vm.vcenters`
     * @param {Array} original The value of `vm.vcenters` before it was updated
     * @memberOf wingrade.vcenters.controllers.VCentersController
     */
    function render(current, original) {
      if (current !== original) {
        vm.columns_vc = [];

        for (var i = 0; i < calculateNumberOfColumns(); ++i) {
          vm.columns_vc.push([]);
        }

        for (var i = 0; i < current.length; ++i) {
          var column = approximateShortestColumn();

          vm.columns_vc[column].push(current[i]);
        }
      }
    }
  }
})();
