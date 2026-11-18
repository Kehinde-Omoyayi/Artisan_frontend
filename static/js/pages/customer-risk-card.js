/* Account standing ring: count the percentage up to its target once the card
 * is on screen. Honours prefers-reduced-motion (jumps straight to the value)
 * and runs at most once. */
(function () {
  'use strict';

  var node = document.querySelector('[data-risk-countup]');
  if (!node) return;

  var target = parseFloat(node.getAttribute('data-risk-countup') || node.textContent || '0');
  if (!isFinite(target)) target = 0;
  target = Math.max(0, Math.min(100, target));

  var prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) {
    node.textContent = Math.round(target);
    return;
  }

  var DURATION = 1100;
  var start = null;

  function frame(timestamp) {
    if (start === null) start = timestamp;
    var progress = Math.min(1, (timestamp - start) / DURATION);
    var eased = 1 - Math.pow(1 - progress, 3); /* easeOutCubic */
    node.textContent = Math.round(target * eased);
    if (progress < 1) window.requestAnimationFrame(frame);
  }

  if (typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(frame);
  } else {
    node.textContent = Math.round(target);
  }
})();
