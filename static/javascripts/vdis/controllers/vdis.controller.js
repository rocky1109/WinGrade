/**
 * VDIsController
 * @namespace wingrade.vdis.controllers
 */
(function () {
  'use strict';

  angular
    .module('wingrade.vdis.controllers')
    .controller('VDIsController', VDIsController);

  VDIsController.$inject = ['$scope'];

  /**
   * @namespace VDIsController
   */
  function VDIsController($scope) {
    var vm = this;

    vm.columns = [];

    activate();


    /**
     * @name activate
     * @desc Actions to be performed when this controller is instantiated
     * @memberOf wingrade.vdis.controllers.VDIsController
     */
    function activate() {
      $scope.$watchCollection(function () { return $scope.vdis; }, render);
      $scope.$watch(function () { return $(window).width(); }, render);
    }
    

    /**
     * @name calculateNumberOfColumns
     * @desc Calculate number of columns based on screen width
     * @returns {Number} The number of columns containing VDIs
     * @memberOf wingrade.vdis.controllers.VDIsControllers
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
     * @memberOf wingrade.vdis.controllers.VDIsController
     */
    function approximateShortestColumn() {
      var scores = vm.columns.map(columnMapFn);

      return scores.indexOf(Math.min.apply(this, scores));

      
      /**
       * @name columnMapFn
       * @desc A map function for scoring column heights
       * @returns The approximately normalized height of a given column
       */
      function columnMapFn(column) {
        var lengths = column.map(function (element) {
          console.log(element.address.length);
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
     * @desc Renders VDIs into columns of approximately equal height
     * @param {Array} current The current value of `vm.vdis`
     * @param {Array} original The value of `vm.vdis` before it was updated
     * @memberOf wingrade.vdis.controllers.VDIsController
     */
    function render(current, original) {
      if (current !== original) {
        vm.columns = [];

        for (var i = 0; i < calculateNumberOfColumns(); ++i) {
          vm.columns.push([]);
        }

        for (var i = 0; i < current.length; ++i) {
          var column = approximateShortestColumn();

          vm.columns[column].push(current[i]);
        }
      }
    }
  }
})();
