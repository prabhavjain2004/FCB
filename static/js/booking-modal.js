/**
 * Enhanced Booking Modal System
 * Provides modern UX patterns for booking flow
 */

class BookingModal {
    constructor() {
        this.isOpen = false;
        this.currentStep = 1;
        this.selectedBooking = null;
        this.selectedSpots = 1;
        this.focusableElements = [];
        this.previousFocus = null;
        
        this.init();
    }
    
    init() {
        this.createModalHTML();
        this.bindEvents();
        this.setupAccessibility();
    }
    
    createModalHTML() {
        const modalHTML = `
            <div id="bookingModalOverlay" class="booking-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
                <div class="booking-modal-container">
                    <div class="booking-modal">
                        <!-- Modal Header -->
                        <div class="booking-modal-header">
                            <h2 id="modalTitle" class="booking-modal-title">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M9 11H5a2 2 0 0 0-2 2v3c0 1.1.9 2 2 2h4m6-6h4a2 2 0 0 1 2 2v3c0 1.1-.9 2-2 2h-4m-6 0V9a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2"/>
                                </svg>
                                Confirm Your Booking
                            </h2>
                            <button class="booking-modal-close" aria-label="Close modal">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </button>
                        </div>
                        
                        <!-- Modal Body -->
                        <div class="booking-modal-body">
                            <!-- Progress Indicator -->
                            <div class="booking-progress">
                                <div class="progress-step completed">
                                    <div class="progress-step-icon">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <polyline points="20,6 9,17 4,12"></polyline>
                                        </svg>
                                    </div>
                                    <span>Select Game</span>
                                </div>
                                <div class="progress-step active">
                                    <div class="progress-step-icon">2</div>
                                    <span>Booking Details</span>
                                </div>
                                <div class="progress-step">
                                    <div class="progress-step-icon">3</div>
                                    <span>Payment</span>
                                </div>
                            </div>
                            
                            <!-- Dynamic Content -->
                            <div id="modalContent">
                                <!-- Content will be dynamically inserted here -->
                            </div>
                        </div>
                        
                        <!-- Modal Footer -->
                        <div class="booking-modal-footer">
                            <button class="modal-button modal-button-secondary" id="cancelButton">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                                Cancel
                            </button>
                            <button class="modal-button modal-button-primary" id="confirmButton" disabled>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M9 11H5a2 2 0 0 0-2 2v3c0 1.1.9 2 2 2h4m6-6h4a2 2 0 0 1 2 2v3c0 1.1-.9 2-2 2h-4m-6 0V9a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2"/>
                                </svg>
                                Book Now
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('bookingModalOverlay');
    }
    
    bindEvents() {
        // Close button
        this.modal.querySelector('.booking-modal-close').addEventListener('click', () => this.close());
        
        // Cancel button
        document.getElementById('cancelButton').addEventListener('click', () => this.close());
        
        // Confirm button
        document.getElementById('confirmButton').addEventListener('click', () => this.confirmBooking());
        
        // Overlay click to close
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });
        
        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }
    
    setupAccessibility() {
        // Focus trap
        this.modal.addEventListener('keydown', (e) => {
            if (e.key === 'Tab' && this.isOpen) {
                this.handleTabKey(e);
            }
        });
    }
    
    handleTabKey(e) {
        const focusableElements = this.modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        
        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                lastElement.focus();
                e.preventDefault();
            }
        } else {
            if (document.activeElement === lastElement) {
                firstElement.focus();
                e.preventDefault();
            }
        }
    }
    
    open(bookingData) {
        this.selectedBooking = bookingData;
        this.previousFocus = document.activeElement;
        
        this.renderContent();
        this.modal.classList.add('active');
        this.isOpen = true;
        
        // Focus management
        setTimeout(() => {
            const firstFocusable = this.modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (firstFocusable) {
                firstFocusable.focus();
            }
        }, 100);
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }
    
    close() {
        this.modal.classList.remove('active');
        this.isOpen = false;
        
        // Restore focus
        if (this.previousFocus) {
            this.previousFocus.focus();
        }
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        // Reset state
        this.selectedBooking = null;
        this.selectedSpots = 1;
        this.currentStep = 1;
    }
    
    renderContent() {
        const content = document.getElementById('modalContent');
        const { slotData, bookingType, availableSpots } = this.selectedBooking;
        
        const option = slotData.booking_options.find(opt => opt.type === bookingType);
        if (!option) {
            this.showError('Booking option not available');
            return;
        }
        
        const isPrivate = bookingType === 'PRIVATE';
        const isShared = bookingType === 'SHARED';
        
        content.innerHTML = `
            <!-- Game Info Card -->
            <div class="game-info-card">
                <div class="game-info-content">
                    <h3 class="game-title">${slotData.game_info.name}</h3>
                    <div class="game-details">
                        ${slotData.slot_info.date} • ${slotData.slot_info.start_time} - ${slotData.slot_info.end_time}
                    </div>
                </div>
            </div>
            
            <!-- Booking Type Display -->
            <div class="booking-type-selector">
                <div class="booking-type-option selected">
                    <div class="booking-type-header">
                        <span class="booking-type-icon">${isPrivate ? '🔒' : '👥'}</span>
                        <div style="flex: 1;">
                            <div class="booking-type-title">${isPrivate ? 'Private Booking' : 'Shared Booking'}</div>
                            <div class="booking-type-price">₹${option.price}${isShared ? ' per person' : ''}</div>
                        </div>
                    </div>
                    <div class="booking-type-description">${option.description}</div>
                </div>
            </div>
            
            <!-- Capacity Visualization -->
            <div class="capacity-visualization">
                <div class="capacity-title">Capacity Overview</div>
                <div class="capacity-dots">
                    ${Array.from({length: slotData.availability.total_capacity}, (_, i) => {
                        let dotClass = 'capacity-dot available';
                        if (i < slotData.availability.booked_spots) {
                            dotClass = 'capacity-dot booked';
                        }
                        return `<div class="${dotClass}"></div>`;
                    }).join('')}
                </div>
                <div class="capacity-legend">
                    <div class="capacity-legend-item">
                        <div class="capacity-dot available"></div>
                        <span>Available</span>
                    </div>
                    <div class="capacity-legend-item">
                        <div class="capacity-dot booked"></div>
                        <span>Booked</span>
                    </div>
                    <div class="capacity-legend-item">
                        <div class="capacity-dot your-booking"></div>
                        <span>Your booking</span>
                    </div>
                </div>
                <div style="margin-top: 0.5rem; font-size: 0.875rem; color: #6b7280;">
                    ${slotData.availability.available_spots}/${slotData.availability.total_capacity} spots available
                </div>
            </div>
            
            ${isShared ? this.renderSpotsSelection(option) : ''}
            
            <!-- Pricing Summary -->
            <div class="pricing-summary">
                <div class="pricing-row">
                    <span>${isPrivate ? `Private booking (${option.capacity} players)` : `${this.selectedSpots} spot${this.selectedSpots > 1 ? 's' : ''} × ₹${option.price}`}</span>
                    <span id="subtotalAmount">₹${isPrivate ? option.price : (option.price * this.selectedSpots)}</span>
                </div>
                <div class="pricing-row">
                    <span>Platform fee</span>
                    <span>₹0.00</span>
                </div>
                <div class="pricing-row">
                    <span>Total Amount</span>
                    <span id="totalAmount">₹${isPrivate ? option.price : (option.price * this.selectedSpots)}</span>
                </div>
            </div>
            
            <!-- Benefits -->
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 1rem;">
                <div style="font-weight: 600; color: #166534; margin-bottom: 0.5rem;">What's included:</div>
                <ul style="color: #166534; font-size: 0.875rem; margin: 0; padding-left: 1rem;">
                    ${option.benefits.map(benefit => `<li>${benefit}</li>`).join('')}
                </ul>
            </div>
        `;
        
        // Enable confirm button
        document.getElementById('confirmButton').disabled = false;
        
        // Bind spots selection if shared booking
        if (isShared) {
            this.bindSpotsSelection();
        }
        
        // Update capacity visualization
        this.updateCapacityVisualization();
    }
    
    renderSpotsSelection(option) {
        const maxSpots = Math.min(this.selectedBooking.availableSpots, option.max_spots_per_booking || 4);
        
        return `
            <div class="spots-selection">
                <div style="font-weight: 600; color: #1f2937; margin-bottom: 0.75rem;">Number of spots to book:</div>
                <div class="spots-grid">
                    ${Array.from({length: maxSpots}, (_, i) => 
                        `<button type="button" class="spot-button ${i === 0 ? 'selected' : ''}" data-spots="${i + 1}">
                            ${i + 1} spot${i > 0 ? 's' : ''}
                        </button>`
                    ).join('')}
                </div>
            </div>
        `;
    }
    
    bindSpotsSelection() {
        const spotButtons = this.modal.querySelectorAll('.spot-button');
        spotButtons.forEach(button => {
            button.addEventListener('click', () => {
                const spots = parseInt(button.dataset.spots);
                this.selectSpots(spots);
            });
        });
    }
    
    selectSpots(spots) {
        this.selectedSpots = spots;
        
        // Update button states
        const spotButtons = this.modal.querySelectorAll('.spot-button');
        spotButtons.forEach(button => {
            const buttonSpots = parseInt(button.dataset.spots);
            if (buttonSpots === spots) {
                button.classList.add('selected');
            } else {
                button.classList.remove('selected');
            }
        });
        
        // Update pricing
        this.updatePricing();
        
        // Update capacity visualization
        this.updateCapacityVisualization();
    }
    
    updatePricing() {
        const { slotData, bookingType } = this.selectedBooking;
        const option = slotData.booking_options.find(opt => opt.type === bookingType);
        
        if (bookingType === 'SHARED') {
            const subtotal = option.price * this.selectedSpots;
            document.getElementById('subtotalAmount').textContent = `₹${subtotal}`;
            document.getElementById('totalAmount').textContent = `₹${subtotal}`;
        }
    }
    
    updateCapacityVisualization() {
        const dots = this.modal.querySelectorAll('.capacity-dot');
        const { slotData } = this.selectedBooking;
        
        dots.forEach((dot, index) => {
            dot.className = 'capacity-dot ';
            
            if (index < slotData.availability.booked_spots) {
                dot.className += 'booked';
            } else if (index < slotData.availability.booked_spots + this.selectedSpots) {
                dot.className += 'your-booking';
            } else {
                dot.className += 'available';
            }
        });
    }
    
    confirmBooking() {
        const confirmButton = document.getElementById('confirmButton');
        
        // Validation
        if (!this.selectedBooking) {
            this.showError('No booking selected. Please try again.');
            return;
        }
        
        const spotsRequested = this.selectedBooking.bookingType === 'SHARED' ? this.selectedSpots : this.selectedBooking.slotData.availability.total_capacity;
        
        if (!spotsRequested || spotsRequested < 1) {
            this.showError('Invalid number of spots selected');
            return;
        }
        
        const bookingData = {
            game_slot_id: this.selectedBooking.slotId,
            booking_type: this.selectedBooking.bookingType,
            spots_requested: spotsRequested
        };
        
        // Show loading state
        this.setButtonLoading(confirmButton, true);
        
        // Make booking request
        fetch('/booking/games/book/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(bookingData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.showSuccess(confirmButton);
                setTimeout(() => {
                    window.location.href = data.redirect_url;
                }, 1000);
            } else {
                this.setButtonLoading(confirmButton, false);
                this.showError(data.error + (data.details ? '\n\nDetails: ' + data.details : ''));
            }
        })
        .catch(error => {
            this.setButtonLoading(confirmButton, false);
            this.showError('Booking failed due to a network error. Please check your connection and try again.');
        });
    }
    
    setButtonLoading(button, loading) {
        if (loading) {
            button.innerHTML = `
                <div class="loading-spinner"></div>
                Creating Booking...
            `;
            button.disabled = true;
        } else {
            button.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 11H5a2 2 0 0 0-2 2v3c0 1.1.9 2 2 2h4m6-6h4a2 2 0 0 1 2 2v3c0 1.1-.9 2-2 2h-4m-6 0V9a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2"/>
                </svg>
                Book Now
            `;
            button.disabled = false;
        }
    }
    
    showSuccess(button) {
        button.innerHTML = `
            <div class="success-checkmark">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20,6 9,17 4,12"></polyline>
                </svg>
            </div>
            Success! Redirecting...
        `;
        button.style.background = '#10b981';
    }
    
    showError(message) {
        const content = document.getElementById('modalContent');
        const existingError = content.querySelector('.error-message');
        
        if (existingError) {
            existingError.remove();
        }
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        
        content.insertBefore(errorDiv, content.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }
    
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
}

// Initialize the booking modal system
let bookingModal;

document.addEventListener('DOMContentLoaded', () => {
    bookingModal = new BookingModal();
});

// Global function to open booking modal (called from game selection)
function selectBookingOption(slotId, bookingType, availableSpots) {
    // Check authentication first
    const isAuthenticated = document.body.dataset.authenticated === 'true';
    
    if (!isAuthenticated) {
        // Redirect to login with next parameter
        const loginUrl = document.body.dataset.loginUrl || '/accounts/login/';
        window.location.href = loginUrl + '?next=' + encodeURIComponent(window.location.pathname);
        return;
    }
    
    // Get slot details
    fetch(`/booking/api/slot-availability/${slotId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const bookingData = {
                    slotId: slotId,
                    bookingType: bookingType,
                    availableSpots: availableSpots,
                    slotData: data
                };
                bookingModal.open(bookingData);
            } else {
                alert('Error loading slot details: ' + data.error);
            }
        })
        .catch(error => {
            alert('Error loading slot details');
        });
}

// Export for use in other scripts
window.BookingModal = BookingModal;
window.selectBookingOption = selectBookingOption;