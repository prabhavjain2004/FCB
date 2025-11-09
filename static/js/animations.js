/**
 * TapNex Arena - Interactive Animations & UI Enhancements
 * Modern JavaScript for smooth interactions and animations
 */

(function() {
  'use strict';

  // ============================================
  // SCROLL REVEAL ANIMATIONS
  // ============================================
  function initScrollReveal() {
    const revealElements = document.querySelectorAll('[data-reveal]');
    
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            // Optionally unobserve after revealing
            // revealObserver.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
      }
    );

    revealElements.forEach(el => {
      revealObserver.observe(el);
    });
  }

  // ============================================
  // PARALLAX EFFECT
  // ============================================
  function initParallax() {
    const parallaxElements = document.querySelectorAll('.parallax');
    
    window.addEventListener('scroll', () => {
      const scrolled = window.pageYOffset;
      
      parallaxElements.forEach(el => {
        const speed = el.dataset.speed || 0.5;
        const yPos = -(scrolled * speed);
        el.style.transform = `translateY(${yPos}px)`;
      });
    });
  }

  // ============================================
  // SMOOTH SCROLL FOR ANCHOR LINKS
  // ============================================
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href === '#') return;
        
        e.preventDefault();
        const target = document.querySelector(href);
        
        if (target) {
          const offsetTop = target.offsetTop - 80; // Account for fixed header
          
          window.scrollTo({
            top: offsetTop,
            behavior: 'smooth'
          });
        }
      });
    });
  }

  // ============================================
  // NAVBAR SCROLL EFFECT
  // ============================================
  function initNavbarScroll() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    let lastScroll = 0;
    
    window.addEventListener('scroll', () => {
      const currentScroll = window.pageYOffset;
      
      // Add background on scroll
      if (currentScroll > 100) {
        navbar.classList.add('navbar-scrolled');
      } else {
        navbar.classList.remove('navbar-scrolled');
      }
      
      // Hide navbar on scroll down, show on scroll up
      if (currentScroll > lastScroll && currentScroll > 500) {
        navbar.style.transform = 'translateY(-100%)';
      } else {
        navbar.style.transform = 'translateY(0)';
      }
      
      lastScroll = currentScroll;
    });
  }

  // ============================================
  // MOBILE MENU TOGGLE
  // ============================================
  function initMobileMenu() {
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const mobileMenu = document.querySelector('.mobile-menu');
    const menuClose = document.querySelector('.mobile-menu-close');
    const menuOverlay = document.querySelector('.mobile-menu-overlay');
    
    if (!menuToggle || !mobileMenu) return;

    const openMenu = () => {
      mobileMenu.classList.add('active');
      document.body.style.overflow = 'hidden';
    };

    const closeMenu = () => {
      mobileMenu.classList.remove('active');
      document.body.style.overflow = '';
    };

    menuToggle.addEventListener('click', openMenu);
    
    if (menuClose) {
      menuClose.addEventListener('click', closeMenu);
    }
    
    if (menuOverlay) {
      menuOverlay.addEventListener('click', closeMenu);
    }

    // Close on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && mobileMenu.classList.contains('active')) {
        closeMenu();
      }
    });
  }

  // ============================================
  // BUTTON RIPPLE EFFECT
  // ============================================
  function initRippleEffect() {
    document.addEventListener('click', function(e) {
      const button = e.target.closest('.btn-ripple');
      if (!button) return;

      const ripple = document.createElement('span');
      const rect = button.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;

      ripple.style.width = ripple.style.height = size + 'px';
      ripple.style.left = x + 'px';
      ripple.style.top = y + 'px';
      ripple.classList.add('ripple');

      button.appendChild(ripple);

      setTimeout(() => ripple.remove(), 600);
    });
  }

  // ============================================
  // TOOLTIP INITIALIZATION
  // ============================================
  function initTooltips() {
    const tooltipTriggers = document.querySelectorAll('[data-tooltip]');
    
    tooltipTriggers.forEach(trigger => {
      const tooltipText = trigger.dataset.tooltip;
      const tooltip = document.createElement('div');
      tooltip.className = 'tooltip';
      tooltip.textContent = tooltipText;
      document.body.appendChild(tooltip);

      trigger.addEventListener('mouseenter', () => {
        const rect = trigger.getBoundingClientRect();
        tooltip.style.left = rect.left + rect.width / 2 + 'px';
        tooltip.style.top = rect.top - 10 + 'px';
        tooltip.classList.add('show');
      });

      trigger.addEventListener('mouseleave', () => {
        tooltip.classList.remove('show');
      });
    });
  }

  // ============================================
  // LAZY LOAD IMAGES
  // ============================================
  function initLazyLoad() {
    const lazyImages = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          img.removeAttribute('data-src');
          imageObserver.unobserve(img);
        }
      });
    });

    lazyImages.forEach(img => imageObserver.observe(img));
  }

  // ============================================
  // COUNTDOWN TIMER (for bookings)
  // ============================================
  function initCountdownTimers() {
    const countdowns = document.querySelectorAll('[data-countdown]');
    
    countdowns.forEach(countdown => {
      const endTime = new Date(countdown.dataset.countdown).getTime();
      
      const updateCountdown = () => {
        const now = new Date().getTime();
        const distance = endTime - now;

        if (distance < 0) {
          countdown.innerHTML = 'EXPIRED';
          return;
        }

        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        countdown.innerHTML = `${hours}h ${minutes}m ${seconds}s`;
      };

      updateCountdown();
      setInterval(updateCountdown, 1000);
    });
  }

  // ============================================
  // FORM VALIDATION ENHANCEMENT
  // ============================================
  function initFormEnhancements() {
    const forms = document.querySelectorAll('form[data-validate]');
    
    forms.forEach(form => {
      const inputs = form.querySelectorAll('input, textarea, select');
      
      inputs.forEach(input => {
        // Add floating label effect
        input.addEventListener('focus', () => {
          input.parentElement.classList.add('focused');
        });

        input.addEventListener('blur', () => {
          if (!input.value) {
            input.parentElement.classList.remove('focused');
          }
        });

        // Real-time validation
        input.addEventListener('input', () => {
          if (input.validity.valid) {
            input.classList.remove('invalid');
            input.classList.add('valid');
          } else {
            input.classList.remove('valid');
            input.classList.add('invalid');
          }
        });
      });
    });
  }

  // ============================================
  // COPY TO CLIPBOARD
  // ============================================
  function initCopyToClipboard() {
    document.addEventListener('click', function(e) {
      const copyBtn = e.target.closest('[data-copy]');
      if (!copyBtn) return;

      const textToCopy = copyBtn.dataset.copy;
      
      navigator.clipboard.writeText(textToCopy).then(() => {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        copyBtn.classList.add('success');
        
        setTimeout(() => {
          copyBtn.textContent = originalText;
          copyBtn.classList.remove('success');
        }, 2000);
      });
    });
  }

  // ============================================
  // TABS FUNCTIONALITY
  // ============================================
  function initTabs() {
    const tabGroups = document.querySelectorAll('[data-tabs]');
    
    tabGroups.forEach(tabGroup => {
      const tabs = tabGroup.querySelectorAll('[data-tab]');
      const panels = tabGroup.querySelectorAll('[data-panel]');
      
      tabs.forEach(tab => {
        tab.addEventListener('click', () => {
          const targetPanel = tab.dataset.tab;
          
          // Remove active class from all tabs and panels
          tabs.forEach(t => t.classList.remove('active'));
          panels.forEach(p => p.classList.remove('active'));
          
          // Add active class to clicked tab and corresponding panel
          tab.classList.add('active');
          const panel = tabGroup.querySelector(`[data-panel="${targetPanel}"]`);
          if (panel) {
            panel.classList.add('active');
          }
        });
      });
    });
  }

  // ============================================
  // ACCORDION FUNCTIONALITY
  // ============================================
  function initAccordions() {
    const accordions = document.querySelectorAll('[data-accordion]');
    
    accordions.forEach(accordion => {
      const triggers = accordion.querySelectorAll('[data-accordion-trigger]');
      
      triggers.forEach(trigger => {
        trigger.addEventListener('click', () => {
          const content = trigger.nextElementSibling;
          const isOpen = trigger.classList.contains('active');
          
          // Close all items in this accordion (optional - for exclusive mode)
          const allTriggers = accordion.querySelectorAll('[data-accordion-trigger]');
          allTriggers.forEach(t => {
            t.classList.remove('active');
            t.nextElementSibling.style.maxHeight = null;
          });
          
          // Toggle current item
          if (!isOpen) {
            trigger.classList.add('active');
            content.style.maxHeight = content.scrollHeight + 'px';
          }
        });
      });
    });
  }

  // ============================================
  // MODAL FUNCTIONALITY
  // ============================================
  function initModals() {
    // Open modal
    document.addEventListener('click', function(e) {
      const modalTrigger = e.target.closest('[data-modal]');
      if (!modalTrigger) return;

      const modalId = modalTrigger.dataset.modal;
      const modal = document.getElementById(modalId);
      
      if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
      }
    });

    // Close modal
    document.addEventListener('click', function(e) {
      const modalClose = e.target.closest('[data-modal-close]');
      const modalBackdrop = e.target.closest('.modal-backdrop');
      
      if (modalClose || modalBackdrop) {
        const modal = e.target.closest('.modal') || document.querySelector('.modal.active');
        if (modal) {
          modal.classList.remove('active');
          document.body.style.overflow = '';
        }
      }
    });

    // Close on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const activeModal = document.querySelector('.modal.active');
        if (activeModal) {
          activeModal.classList.remove('active');
          document.body.style.overflow = '';
        }
      }
    });
  }

  // ============================================
  // PRELOADER
  // ============================================
  function initPreloader() {
    window.addEventListener('load', () => {
      const preloader = document.getElementById('preloader');
      if (preloader) {
        setTimeout(() => {
          preloader.classList.add('fade-out');
          setTimeout(() => {
            preloader.style.display = 'none';
          }, 500);
        }, 300);
      }
    });
  }

  // ============================================
  // NUMBER COUNTER ANIMATION
  // ============================================
  function initCounters() {
    const counters = document.querySelectorAll('[data-counter]');
    
    const counterObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const counter = entry.target;
          const target = parseInt(counter.dataset.counter);
          const duration = parseInt(counter.dataset.duration) || 2000;
          const increment = target / (duration / 16); // 60fps
          let current = 0;

          const updateCounter = () => {
            current += increment;
            if (current < target) {
              counter.textContent = Math.floor(current);
              requestAnimationFrame(updateCounter);
            } else {
              counter.textContent = target;
            }
          };

          updateCounter();
          counterObserver.unobserve(counter);
        }
      });
    });

    counters.forEach(counter => counterObserver.observe(counter));
  }

  // ============================================
  // INITIALIZE ALL FEATURES
  // ============================================
  function init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }

    // Initialize all features
    initScrollReveal();
    initParallax();
    initSmoothScroll();
    initNavbarScroll();
    initMobileMenu();
    initRippleEffect();
    initTooltips();
    initLazyLoad();
    initCountdownTimers();
    initFormEnhancements();
    initCopyToClipboard();
    initTabs();
    initAccordions();
    initModals();
    initPreloader();
    initCounters();
  }

  // Auto-initialize
  init();

  // Expose utilities globally if needed
  window.TapNexUI = {
    initScrollReveal,
    initParallax,
    initSmoothScroll,
    initNavbarScroll,
    initMobileMenu,
    initTooltips,
    initModals
  };

})();
