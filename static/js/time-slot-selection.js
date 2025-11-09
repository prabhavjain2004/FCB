/**
 * Enhanced Time Slot Selection Interface
 * Provides calendar widget with availability heatmap and interactive time slots
 */

class TimeSlotSelection {
    constructor(gameId, containerId = 'timeSlotContainer') {
        this.gameId = gameId;
        this.container = document.getElementById(containerId);
        this.selectedDate = new Date();
        this.selectedSlot = null;
        this.availabilityData = {};
        this.currentMonth = new Date();
        this.updateInterval = null;
        
        this.init();
    }
    
    init() {
        if (!this.container) {
            return;
        }
        
        this.render();
        this.bindEvents();
        this.loadAvailabilityData();
        this.startRealTimeUpdates();
    }
    
    render() {
        this.container.innerHTML = `
            <div class="time-slot-selection">
                <!-- Calendar Widget -->
                <div class="calendar-widget">
                    <div class="calendar-header">
                        <h3 class="calendar-title">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                <line x1="16" y1="2" x2="16" y2="6"></line>
                                <line x1="8" y1="2" x2="8" y2="6"></line>
                                <line x1="3" y1="10" x2="21" y2="10"></line>
                            </svg>
                            Select Date
                        </h3>
                        <div class="calendar-nav">
                            <button class="calendar-nav-button" id="prevMonth" aria-label="Previous month">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="15,18 9,12 15,6"></polyline>
                                </svg>
                            </button>
                            <button class="calendar-nav-button" id="nextMonth" aria-label="Next month">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="9,18 15,12 9,6"></polyline>
                                </svg>
                            </button>
                        </div>
                    </div>
                    
                    <div id="calendarGrid" class="calendar-grid">
                        <!-- Calendar will be rendered here -->
                    </div>
                    
                    <!-- Availability Legend -->
                    <div class="availability-legend">
                        <div class="legend-item">
                            <div class="legend-dot high"></div>
                            <span>High availability</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dot medium"></div>
                            <span>Limited availability</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dot low"></div>
                            <span>Low availability</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dot none"></div>
                            <span>No availability</span>
                        </div>
                    </div>
                </div>
                
                <!-- Time Slots -->
                <div class="time-slots-container">
                    <div class="time-slots-header">
                        <h3 class="time-slots-title">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12,6 12,12 16,14"></polyline>
                            </svg>
                            Available Time Slots
                        </h3>
                        <div class="time-slots-date" id="selectedDateDisplay">
                            ${this.formatDate(this.selectedDate)}
                        </div>
                    </div>
                    
                    <div id="timeSlotsContent">
                        <div class="time-slots-loading">
                            <div class="loading-spinner-large"></div>
                            <span>Loading available time slots...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    bindEvents() {
        // Calendar navigation
        document.getElementById('prevMonth').addEventListener('click', () => {
            this.currentMonth.setMonth(this.currentMonth.getMonth() - 1);
            this.renderCalendar();
        });
        
        document.getElementById('nextMonth').addEventListener('click', () => {
            this.currentMonth.setMonth(this.currentMonth.getMonth() + 1);
            this.renderCalendar();
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.target.classList.contains('calendar-day')) {
                this.handleCalendarKeyboard(e);
            }
        });
    }
    
    handleCalendarKeyboard(e) {
        const currentDate = new Date(e.target.dataset.date);
        let newDate = new Date(currentDate);
        
        switch (e.key) {
            case 'ArrowLeft':
                newDate.setDate(newDate.getDate() - 1);
                break;
            case 'ArrowRight':
                newDate.setDate(newDate.getDate() + 1);
                break;
            case 'ArrowUp':
                newDate.setDate(newDate.getDate() - 7);
                break;
            case 'ArrowDown':
                newDate.setDate(newDate.getDate() + 7);
                break;
            case 'Enter':
            case ' ':
                this.selectDate(currentDate);
                e.preventDefault();
                return;
            default:
                return;
        }
        
        e.preventDefault();
        this.selectDate(newDate);
        
        // Focus the new date
        setTimeout(() => {
            const newDateElement = document.querySelector(`[data-date="${this.formatDateISO(newDate)}"]`);
            if (newDateElement) {
                newDateElement.focus();
            }
        }, 100);
    }
    
    renderCalendar() {
        const grid = document.getElementById('calendarGrid');
        const year = this.currentMonth.getFullYear();
        const month = this.currentMonth.getMonth();
        
        // Clear grid
        grid.innerHTML = '';
        
        // Day headers
        const dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        dayHeaders.forEach(day => {
            const header = document.createElement('div');
            header.className = 'calendar-day-header';
            header.textContent = day;
            grid.appendChild(header);
        });
        
        // Get first day of month and number of days
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const startDate = new Date(firstDay);
        startDate.setDate(startDate.getDate() - firstDay.getDay());
        
        // Render 6 weeks
        for (let week = 0; week < 6; week++) {
            for (let day = 0; day < 7; day++) {
                const currentDate = new Date(startDate);
                currentDate.setDate(startDate.getDate() + (week * 7) + day);
                
                const dayElement = this.createDayElement(currentDate, month);
                grid.appendChild(dayElement);
            }
        }
    }
    
    createDayElement(date, currentMonth) {
        const dayElement = document.createElement('div');
        const today = new Date();
        const isToday = this.isSameDate(date, today);
        const isSelected = this.isSameDate(date, this.selectedDate);
        const isCurrentMonth = date.getMonth() === currentMonth;
        const isPast = date < today && !isToday;
        const dateISO = this.formatDateISO(date);
        
        dayElement.className = 'calendar-day';
        dayElement.textContent = date.getDate();
        dayElement.dataset.date = dateISO;
        dayElement.tabIndex = 0;
        dayElement.setAttribute('role', 'button');
        dayElement.setAttribute('aria-label', this.formatDate(date));
        
        if (isToday) dayElement.classList.add('today');
        if (isSelected) dayElement.classList.add('selected');
        if (!isCurrentMonth) dayElement.classList.add('other-month');
        if (isPast) dayElement.classList.add('disabled');
        
        // Add availability indicator
        const availability = this.getDateAvailability(dateISO);
        if (availability && !isPast) {
            const indicator = document.createElement('div');
            indicator.className = `availability-indicator ${availability.level}`;
            dayElement.appendChild(indicator);
        }
        
        // Click handler
        if (!isPast) {
            dayElement.addEventListener('click', () => this.selectDate(date));
        }
        
        return dayElement;
    }
    
    selectDate(date) {
        if (date < new Date() && !this.isSameDate(date, new Date())) {
            return; // Don't allow past dates
        }
        
        this.selectedDate = new Date(date);
        
        // Update calendar display
        this.renderCalendar();
        
        // Update selected date display
        document.getElementById('selectedDateDisplay').textContent = this.formatDate(this.selectedDate);
        
        // Load time slots for selected date
        this.loadTimeSlots();
        
        // Emit event
        this.emit('dateSelected', { date: this.selectedDate });
    }
    
    loadAvailabilityData() {
        // Load availability data for the current month
        const startDate = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth(), 1);
        const endDate = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() + 1, 0);
        
        fetch(`/booking/api/game-availability/${this.gameId}/?start=${this.formatDateISO(startDate)}&end=${this.formatDateISO(endDate)}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.availabilityData = data.availability;
                    this.renderCalendar();
                }
            })
            .catch(error => {
                // Silently handle availability loading errors
            });
    }
    
    getDateAvailability(dateISO) {
        const availability = this.availabilityData[dateISO];
        if (!availability) return null;
        
        const totalSlots = availability.total_slots;
        const availableSlots = availability.available_slots;
        const percentage = availableSlots / totalSlots;
        
        let level;
        if (percentage > 0.7) level = 'high';
        else if (percentage > 0.3) level = 'medium';
        else if (percentage > 0) level = 'low';
        else level = 'none';
        
        return { level, totalSlots, availableSlots, percentage };
    }
    
    loadTimeSlots() {
        const content = document.getElementById('timeSlotsContent');
        
        // Show loading state
        content.innerHTML = `
            <div class="time-slots-loading">
                <div class="loading-spinner-large"></div>
                <span>Loading available time slots...</span>
            </div>
        `;
        
        const dateISO = this.formatDateISO(this.selectedDate);
        
        fetch(`/booking/api/game-slots/${this.gameId}/?date=${dateISO}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.renderTimeSlots(data.slots);
                } else {
                    this.showEmptyState('Failed to load time slots');
                }
            })
            .catch(error => {
                this.showEmptyState('Error loading time slots');
            });
    }
    
    renderTimeSlots(slots) {
        const content = document.getElementById('timeSlotsContent');
        
        if (!slots || slots.length === 0) {
            this.showEmptyState('No time slots available for this date');
            return;
        }
        
        const grid = document.createElement('div');
        grid.className = 'time-slots-grid';
        
        slots.forEach(slot => {
            const slotElement = this.createTimeSlotElement(slot);
            grid.appendChild(slotElement);
        });
        
        content.innerHTML = '';
        content.appendChild(grid);
    }
    
    createTimeSlotElement(slot) {
        const slotElement = document.createElement('div');
        slotElement.className = 'time-slot';
        slotElement.dataset.slotId = slot.id;
        
        const isAvailable = slot.availability.available_spots > 0;
        const availabilityPercentage = slot.availability.available_spots / slot.availability.total_capacity;
        
        if (!isAvailable) {
            slotElement.classList.add('unavailable');
        }
        
        // Status indicator
        let statusClass = 'full';
        if (availabilityPercentage > 0.7) statusClass = 'available';
        else if (availabilityPercentage > 0.3) statusClass = 'limited';
        
        slotElement.innerHTML = `
            <div class="status-indicator ${statusClass}"></div>
            
            <div class="time-slot-time">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12,6 12,12 16,14"></polyline>
                </svg>
                ${slot.start_time} - ${slot.end_time}
            </div>
            
            <div class="time-slot-duration">
                ${slot.duration} minutes
            </div>
            
            <div class="time-slot-capacity">
                <div class="capacity-visualization-mini">
                    ${Array.from({length: slot.availability.total_capacity}, (_, i) => 
                        `<div class="capacity-dot-mini ${i < slot.availability.booked_spots ? 'booked' : 'available'}"></div>`
                    ).join('')}
                </div>
                <div class="capacity-text">
                    ${slot.availability.available_spots}/${slot.availability.total_capacity} available
                </div>
            </div>
            
            <div class="time-slot-price">
                <div>
                    ${slot.booking_options.map(option => 
                        `<div class="price-amount">₹${option.price}</div>
                         <div class="price-type">${option.type.toLowerCase()}</div>`
                    ).join('')}
                </div>
            </div>
        `;
        
        // Click handler
        if (isAvailable) {
            slotElement.addEventListener('click', () => this.selectTimeSlot(slot));
            slotElement.setAttribute('role', 'button');
            slotElement.setAttribute('tabindex', '0');
            slotElement.setAttribute('aria-label', `Book ${slot.start_time} to ${slot.end_time}, ${slot.availability.available_spots} spots available`);
            
            // Keyboard support
            slotElement.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.selectTimeSlot(slot);
                }
            });
        } else {
            slotElement.setAttribute('aria-label', `${slot.start_time} to ${slot.end_time} - Fully booked`);
        }
        
        return slotElement;
    }
    
    selectTimeSlot(slot) {
        // Remove previous selection
        document.querySelectorAll('.time-slot.selected').forEach(el => {
            el.classList.remove('selected');
        });
        
        // Add selection to clicked slot
        const slotElement = document.querySelector(`[data-slot-id="${slot.id}"]`);
        if (slotElement) {
            slotElement.classList.add('selected');
        }
        
        this.selectedSlot = slot;
        
        // Emit event
        this.emit('slotSelected', { slot: slot });
        
        // Show booking options modal
        if (window.selectBookingOption) {
            // Determine booking type and available spots
            const availableSpots = slot.availability.available_spots;
            const bookingType = slot.booking_options.length > 1 ? 'HYBRID' : slot.booking_options[0].type;
            
            window.selectBookingOption(slot.id, bookingType, availableSpots);
        }
    }
    
    showEmptyState(message) {
        const content = document.getElementById('timeSlotsContent');
        content.innerHTML = `
            <div class="time-slots-empty">
                <div class="empty-icon">📅</div>
                <div style="font-weight: 600; margin-bottom: 0.5rem;">No Time Slots Available</div>
                <div>${message}</div>
            </div>
        `;
    }
    
    startRealTimeUpdates() {
        // Update every 30 seconds
        this.updateInterval = setInterval(() => {
            this.updateAvailability();
        }, 30000);
    }
    
    stopRealTimeUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    updateAvailability() {
        // Update current time slots
        const dateISO = this.formatDateISO(this.selectedDate);
        
        fetch(`/booking/api/game-slots/${this.gameId}/?date=${dateISO}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.updateTimeSlotAvailability(data.slots);
                }
            })
            .catch(error => {
                // Silently handle availability update errors
            });
    }
    
    updateTimeSlotAvailability(slots) {
        slots.forEach(slot => {
            const slotElement = document.querySelector(`[data-slot-id="${slot.id}"]`);
            if (!slotElement) return;
            
            // Add update animation
            slotElement.classList.add('updating');
            setTimeout(() => slotElement.classList.remove('updating'), 500);
            
            // Update capacity visualization
            const capacityDots = slotElement.querySelectorAll('.capacity-dot-mini');
            capacityDots.forEach((dot, index) => {
                dot.className = `capacity-dot-mini ${index < slot.availability.booked_spots ? 'booked' : 'available'}`;
            });
            
            // Update capacity text
            const capacityText = slotElement.querySelector('.capacity-text');
            if (capacityText) {
                capacityText.textContent = `${slot.availability.available_spots}/${slot.availability.total_capacity} available`;
            }
            
            // Update status indicator
            const statusIndicator = slotElement.querySelector('.status-indicator');
            const availabilityPercentage = slot.availability.available_spots / slot.availability.total_capacity;
            
            let statusClass = 'full';
            if (availabilityPercentage > 0.7) statusClass = 'available';
            else if (availabilityPercentage > 0.3) statusClass = 'limited';
            
            statusIndicator.className = `status-indicator ${statusClass}`;
            
            // Update availability state
            const isAvailable = slot.availability.available_spots > 0;
            if (isAvailable) {
                slotElement.classList.remove('unavailable');
            } else {
                slotElement.classList.add('unavailable');
            }
        });
    }
    
    // Utility methods
    formatDate(date) {
        return date.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }
    
    formatDateISO(date) {
        return date.toISOString().split('T')[0];
    }
    
    isSameDate(date1, date2) {
        return this.formatDateISO(date1) === this.formatDateISO(date2);
    }
    
    // Event system
    emit(eventName, data) {
        const event = new CustomEvent(`timeSlot:${eventName}`, { detail: data });
        document.dispatchEvent(event);
    }
    
    on(eventName, callback) {
        document.addEventListener(`timeSlot:${eventName}`, callback);
    }
    
    // Cleanup
    destroy() {
        this.stopRealTimeUpdates();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export for use in other scripts
window.TimeSlotSelection = TimeSlotSelection;