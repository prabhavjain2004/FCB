/**
 * Real-time Availability System
 * Handles WebSocket connections for live station updates
 */

class RealtimeAvailability {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isConnected = false;
        this.stationElements = new Map();

        this.init();
    }

    init() {
        this.cacheStationElements();
        this.setupWebSocket();
        this.setupFallbackPolling();
        this.setupConnectionIndicator();
    }

    cacheStationElements() {
        // Cache all station card elements for efficient updates
        const stationCards = document.querySelectorAll('.station-card');
        stationCards.forEach(card => {
            const stationId = card.dataset.stationId;
            if (stationId) {
                this.stationElements.set(stationId, {
                    card: card,
                    availabilityBadge: card.querySelector('[data-availability-badge]'),
                    bookButton: card.querySelector('button[onclick*="bookStation"]'),
                    progressBar: card.querySelector('[data-capacity-bar]'),
                    timeRemaining: card.querySelector('[data-time-remaining]')
                });
            }
        });
    }

    setupWebSocket() {
        // Check if WebSocket is supported
        if (!window.WebSocket) {
            return;
        }

        try {
            // Use secure WebSocket in production
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/stations/`;

            this.socket = new WebSocket(wsUrl);
            this.setupWebSocketEvents();
        } catch (error) {
            this.fallbackToPolling();
        }
    }

    setupWebSocketEvents() {
        this.socket.onopen = () => {
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.updateConnectionStatus(true);

            // Request initial station data
            this.sendMessage({
                type: 'get_all_stations'
            });
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                // Silently handle parse errors
            }
        };

        this.socket.onclose = (event) => {
            this.isConnected = false;
            this.updateConnectionStatus(false);

            // Attempt to reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => {
                    this.reconnectAttempts++;
                    this.setupWebSocket();
                }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts));
            } else {
                this.fallbackToPolling();
            }
        };

        this.socket.onerror = (error) => {
            // Silently handle WebSocket errors
        };
    }

    sendMessage(message) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(message));
        }
    }

    handleMessage(data) {
        switch (data.type) {
            case 'station_update':
                this.updateStation(data.station);
                break;
            case 'stations_list':
                data.stations.forEach(station => this.updateStation(station));
                break;
            case 'booking_update':
                this.handleBookingUpdate(data);
                break;
            case 'capacity_update':
                this.updateCapacity(data.station_id, data.capacity);
                break;
            default:
            // Unknown message type
        }
    }

    updateStation(stationData) {
        const elements = this.stationElements.get(stationData.id.toString());
        if (!elements) return;

        const { card, availabilityBadge, bookButton, progressBar, timeRemaining } = elements;

        // Update availability status with smooth transition
        this.updateAvailabilityStatus(card, stationData);

        // Update booking button
        this.updateBookingButton(bookButton, stationData);

        // Update capacity visualization
        if (progressBar && stationData.capacity !== undefined) {
            this.updateCapacityBar(progressBar, stationData.capacity);
        }

        // Update time remaining
        if (timeRemaining && stationData.time_remaining) {
            this.updateTimeRemaining(timeRemaining, stationData.time_remaining);
        }

        // Update card dataset for filtering
        card.dataset.availability = stationData.is_available ? 'available' :
            stationData.is_maintenance ? 'maintenance' : 'occupied';

        // Trigger a subtle animation to indicate update
        this.animateUpdate(card);
    }

    updateAvailabilityStatus(card, stationData) {
        const badge = card.querySelector('[data-availability-badge]') ||
            card.querySelector('.glass-strong');

        if (!badge) return;

        // Remove existing classes
        badge.classList.remove('border-success/30', 'text-success',
            'border-error/30', 'text-error',
            'border-warning/30', 'text-warning');

        let statusText, statusClasses, iconSvg;

        if (stationData.is_available) {
            statusText = 'Available';
            statusClasses = ['border-success/30', 'text-success'];
            iconSvg = `<svg class="w-3 h-3 animate-pulse" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.061L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
                      </svg>`;
        } else if (stationData.is_maintenance) {
            statusText = 'Maintenance';
            statusClasses = ['border-warning/30', 'text-warning'];
            iconSvg = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                      </svg>`;
        } else {
            statusText = 'Occupied';
            statusClasses = ['border-error/30', 'text-error'];
            iconSvg = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                        <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
                      </svg>`;
        }

        // Apply new classes with animation
        badge.classList.add(...statusClasses);

        // Update content
        const iconElement = badge.querySelector('svg');
        const textElement = badge.querySelector('span');

        if (iconElement) {
            iconElement.outerHTML = iconSvg;
        }

        if (textElement) {
            textElement.textContent = statusText;
        }
    }

    updateBookingButton(button, stationData) {
        if (!button) return;

        if (stationData.is_available) {
            button.disabled = false;
            button.className = 'btn-primary px-6 py-2.5 text-sm font-bold rounded-xl transition-all duration-300 transform hover:scale-105 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent-orange focus:ring-offset-2 focus:ring-offset-transparent group-hover:animate-pulse';
            button.innerHTML = `
                <span class="flex items-center gap-2">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492zM5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0z"/>
                        <path d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52l-.094-.319zm-2.633.283c.246-.835 1.428-.835 1.674 0l.094.319a1.873 1.873 0 0 0 2.693 1.115l.291-.16c.764-.415 1.6.42 1.184 1.185l-.159.292a1.873 1.873 0 0 0 1.116 2.692l.318.094c.835.246.835 1.428 0 1.674l-.319.094a1.873 1.873 0 0 0-1.115 2.693l.16.291c.415.764-.42 1.6-1.185 1.184l-.291-.159a1.873 1.873 0 0 0-2.693 1.116l-.094.318c-.246.835-1.428.835-1.674 0l-.094-.319a1.873 1.873 0 0 0-2.692-1.115l-.292.16c-.764.415-1.6-.42-1.184-1.185l.159-.291A1.873 1.873 0 0 0 1.945 8.93l-.319-.094c-.835-.246-.835-1.428 0-1.674l.319-.094A1.873 1.873 0 0 0 3.06 4.377l-.16-.292c-.415-.764.42-1.6 1.185-1.184l.292.159a1.873 1.873 0 0 0 2.692-1.115l.094-.319z"/>
                    </svg>
                    Book Now
                </span>
            `;
        } else {
            button.disabled = true;
            const statusText = stationData.is_maintenance ? 'Maintenance' : 'Occupied';
            const iconSvg = stationData.is_maintenance ?
                `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                </svg>` :
                `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                    <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                    <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
                </svg>`;

            button.className = 'px-6 py-2.5 text-sm font-bold rounded-xl bg-neutral-700 text-neutral-400 cursor-not-allowed flex items-center gap-2';
            button.innerHTML = `${iconSvg} ${statusText}`;
        }
    }

    updateCapacityBar(progressBar, capacity) {
        if (!progressBar) return;

        const percentage = Math.min(Math.max(capacity, 0), 100);
        const bar = progressBar.querySelector('.capacity-fill') || progressBar;

        // Animate the progress bar
        bar.style.transition = 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
        bar.style.width = `${percentage}%`;

        // Update color based on capacity
        bar.classList.remove('bg-success', 'bg-warning', 'bg-error');
        if (percentage <= 60) {
            bar.classList.add('bg-success');
        } else if (percentage <= 85) {
            bar.classList.add('bg-warning');
        } else {
            bar.classList.add('bg-error');
        }
    }

    updateTimeRemaining(element, timeRemaining) {
        if (!element) return;

        element.textContent = this.formatTimeRemaining(timeRemaining);

        // Add pulsing animation if time is running low
        if (timeRemaining < 300) { // Less than 5 minutes
            element.classList.add('animate-pulse', 'text-warning');
        } else {
            element.classList.remove('animate-pulse', 'text-warning');
        }
    }

    formatTimeRemaining(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    }

    animateUpdate(card) {
        // Add a subtle pulse animation to indicate update
        card.style.transform = 'scale(1.02)';
        card.style.transition = 'transform 0.2s ease-out';

        setTimeout(() => {
            card.style.transform = 'scale(1)';
        }, 200);
    }

    handleBookingUpdate(data) {
        // Handle real-time booking updates
        if (data.station_id) {
            this.updateStation(data.station_data);
        }

        // Show notification if needed
        if (data.show_notification) {
            this.showNotification(data.message, data.type || 'info');
        }
    }

    showNotification(message, type = 'info') {
        // Create and show a toast notification
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 z-50 glass rounded-xl p-4 max-w-sm transform translate-x-full transition-transform duration-300 ${type === 'success' ? 'border-success text-success' :
            type === 'error' ? 'border-error text-error' :
                type === 'warning' ? 'border-warning text-warning' :
                    'border-accent-cyan text-accent-cyan'
            }`;

        notification.innerHTML = `
            <div class="flex items-center gap-3">
                <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 16 16">
                    ${type === 'success' ?
                '<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.061L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>' :
                '<path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16zM5.354 4.646a.5.5 0 1 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293 5.354 4.646z"/>'
            }
                </svg>
                <span class="text-sm font-medium">${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-auto text-neutral-400 hover:text-white">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8 2.146 2.854Z"/>
                    </svg>
                </button>
            </div>
        `;

        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);

        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.style.transform = 'translateX(full)';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 5000);
    }

    setupFallbackPolling() {
        // Fallback polling for when WebSocket is not available
        // Real-time updates via polling every 5 seconds for instant updates
        this.pollingInterval = setInterval(() => {
            if (!this.isConnected) {
                this.fetchStationUpdates();
            }
        }, 5000); // Poll every 5 seconds for real-time updates
    }

    async fetchStationUpdates() {
        try {
            const response = await fetch('/api/stations/status/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const data = await response.json();
                data.stations.forEach(station => this.updateStation(station));
            }
        } catch (error) {
            // Silently handle fetch errors
        }
    }

    fallbackToPolling() {
        this.isConnected = false;
        this.updateConnectionStatus(false);

        // Use fast polling for real-time updates when WebSocket is not available
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }

        this.pollingInterval = setInterval(() => {
            this.fetchStationUpdates();
        }, 5000); // Poll every 5 seconds for real-time updates
    }

    setupConnectionIndicator() {
        // Create connection status indicator
        const indicator = document.createElement('div');
        indicator.id = 'connection-status';
        indicator.className = 'fixed bottom-4 left-4 z-40 glass rounded-full px-3 py-2 text-xs font-medium transition-all duration-300 opacity-0 pointer-events-none';
        indicator.innerHTML = `
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full bg-current"></div>
                <span>Connecting...</span>
            </div>
        `;

        document.body.appendChild(indicator);
    }

    updateConnectionStatus(isConnected) {
        const indicator = document.getElementById('connection-status');
        if (!indicator) return;

        if (isConnected) {
            indicator.className = 'fixed bottom-4 left-4 z-40 glass rounded-full px-3 py-2 text-xs font-medium transition-all duration-300 text-success border-success/30';
            indicator.innerHTML = `
                <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-current animate-pulse"></div>
                    <span>Live Updates</span>
                </div>
            `;

            // Show briefly then fade out
            indicator.style.opacity = '1';
            setTimeout(() => {
                indicator.style.opacity = '0';
            }, 3000);
        } else {
            indicator.className = 'fixed bottom-4 left-4 z-40 glass rounded-full px-3 py-2 text-xs font-medium transition-all duration-300 text-warning border-warning/30';
            indicator.innerHTML = `
                <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-current"></div>
                    <span>Reconnecting...</span>
                </div>
            `;
            indicator.style.opacity = '1';
        }
    }

    destroy() {
        // Clean up resources
        if (this.socket) {
            this.socket.close();
        }

        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }

        const indicator = document.getElementById('connection-status');
        if (indicator) {
            indicator.remove();
        }
    }
}

// Initialize real-time availability when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.realtimeAvailability = new RealtimeAvailability();
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (window.realtimeAvailability) {
        window.realtimeAvailability.destroy();
    }
});