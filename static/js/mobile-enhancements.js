/**
 * TapNex Arena - Mobile Enhancements
 * JavaScript utilities for better mobile experience
 */

(function () {
    'use strict';

    // ============================================
    // MOBILE DETECTION
    // ============================================
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isAndroid = /Android/.test(navigator.userAgent);

    // Add mobile class to body
    if (isMobile) {
        document.body.classList.add('is-mobile');
    }
    if (isIOS) {
        document.body.classList.add('is-ios');
    }
    if (isAndroid) {
        document.body.classList.add('is-android');
    }

    // ============================================
    // PREVENT DOUBLE-TAP ZOOM ON IOS
    // ============================================
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function (event) {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, { passive: false });

    // ============================================
    // SMOOTH SCROLL POLYFILL FOR MOBILE
    // ============================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;

            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                const offsetTop = target.offsetTop - 80; // Account for fixed navbar
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });

    // ============================================
    // VIEWPORT HEIGHT FIX FOR MOBILE BROWSERS
    // ============================================
    function setVH() {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }

    setVH();
    window.addEventListener('resize', setVH);
    window.addEventListener('orientationchange', setVH);

    // ============================================
    // TOUCH RIPPLE EFFECT
    // ============================================
    function createRipple(event) {
        const button = event.currentTarget;

        // Only apply to elements with btn-ripple class
        if (!button.classList.contains('btn-ripple')) return;

        const circle = document.createElement('span');
        const diameter = Math.max(button.clientWidth, button.clientHeight);
        const radius = diameter / 2;

        const rect = button.getBoundingClientRect();
        circle.style.width = circle.style.height = `${diameter}px`;
        circle.style.left = `${event.clientX - rect.left - radius}px`;
        circle.style.top = `${event.clientY - rect.top - radius}px`;
        circle.classList.add('ripple');

        const ripple = button.getElementsByClassName('ripple')[0];
        if (ripple) {
            ripple.remove();
        }

        button.appendChild(circle);
    }

    // Add ripple effect to buttons
    document.querySelectorAll('.btn-ripple').forEach(button => {
        button.addEventListener('click', createRipple);
    });

    // Add ripple styles
    const style = document.createElement('style');
    style.textContent = `
    .btn-ripple {
      position: relative;
      overflow: hidden;
    }
    
    .ripple {
      position: absolute;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.3);
      transform: scale(0);
      animation: ripple-animation 0.6s ease-out;
      pointer-events: none;
    }
    
    @keyframes ripple-animation {
      to {
        transform: scale(4);
        opacity: 0;
      }
    }
  `;
    document.head.appendChild(style);

    // ============================================
    // LAZY LOADING IMAGES
    // ============================================
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                    observer.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }

    // ============================================
    // PULL TO REFRESH INDICATOR (Optional)
    // ============================================
    let startY = 0;
    let isPulling = false;

    document.addEventListener('touchstart', function (e) {
        if (window.scrollY === 0) {
            startY = e.touches[0].pageY;
            isPulling = true;
        }
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (!isPulling) return;

        const currentY = e.touches[0].pageY;
        const pullDistance = currentY - startY;

        if (pullDistance > 100 && window.scrollY === 0) {
            // Optional: Add pull-to-refresh functionality here
            // For now, we'll just prevent the default behavior
        }
    }, { passive: true });

    document.addEventListener('touchend', function () {
        isPulling = false;
    }, { passive: true });

    // ============================================
    // ORIENTATION CHANGE HANDLER
    // ============================================
    window.addEventListener('orientationchange', function () {
        // Close mobile menu on orientation change
        const mobileMenu = document.querySelector('.mobile-menu');
        const mobileMenuOverlay = document.querySelector('.mobile-menu-overlay');

        if (mobileMenu && !mobileMenu.classList.contains('translate-x-full')) {
            mobileMenu.classList.add('translate-x-full');
            if (mobileMenuOverlay) {
                mobileMenuOverlay.classList.add('hidden');
            }
            document.body.style.overflow = '';
        }
    });

    // ============================================
    // PREVENT SCROLL WHEN MODAL IS OPEN
    // ============================================
    const preventScroll = (e) => {
        e.preventDefault();
    };

    window.disableScroll = function () {
        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.width = '100%';
        document.addEventListener('touchmove', preventScroll, { passive: false });
    };

    window.enableScroll = function () {
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.width = '';
        document.removeEventListener('touchmove', preventScroll);
    };

    // ============================================
    // SAFE AREA INSETS FOR NOTCHED DEVICES
    // ============================================
    if (isIOS) {
        // Add padding for safe areas on iOS devices with notches
        const safeAreaStyle = document.createElement('style');
        safeAreaStyle.textContent = `
      @supports (padding: max(0px)) {
        body {
          padding-left: max(0px, env(safe-area-inset-left));
          padding-right: max(0px, env(safe-area-inset-right));
        }
        
        .navbar {
          padding-left: max(1rem, env(safe-area-inset-left));
          padding-right: max(1rem, env(safe-area-inset-right));
        }
        
        footer {
          padding-bottom: max(1rem, env(safe-area-inset-bottom));
        }
      }
    `;
        document.head.appendChild(safeAreaStyle);
    }

    // ============================================
    // NETWORK STATUS INDICATOR
    // ============================================
    function updateOnlineStatus() {
        const isOnline = navigator.onLine;

        if (!isOnline) {
            // Show offline indicator
            const offlineIndicator = document.createElement('div');
            offlineIndicator.id = 'offline-indicator';
            offlineIndicator.className = 'fixed top-16 left-0 right-0 bg-error text-white text-center py-2 text-sm z-50';
            offlineIndicator.textContent = 'No internet connection';
            document.body.appendChild(offlineIndicator);
        } else {
            // Remove offline indicator
            const indicator = document.getElementById('offline-indicator');
            if (indicator) {
                indicator.remove();
            }
        }
    }

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    // ============================================
    // PERFORMANCE MONITORING
    // ============================================
    if (isMobile && 'performance' in window) {
        window.addEventListener('load', function () {
            setTimeout(function () {
                const perfData = window.performance.timing;
                const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
            }, 0);
        });
    }

    // ============================================
    // TOUCH FEEDBACK FOR LINKS
    // ============================================
    document.querySelectorAll('a, button').forEach(element => {
        element.addEventListener('touchstart', function () {
            this.style.opacity = '0.7';
        }, { passive: true });

        element.addEventListener('touchend', function () {
            this.style.opacity = '';
        }, { passive: true });

        element.addEventListener('touchcancel', function () {
            this.style.opacity = '';
        }, { passive: true });
    });

    // ============================================
    // INITIALIZE ON DOM READY
    // ============================================
    document.addEventListener('DOMContentLoaded', function () {
        // Add loaded class to body
        document.body.classList.add('mobile-enhanced');
    });

})();
