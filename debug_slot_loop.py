"""
Debug script to identify the infinite loop issue
"""
from datetime import datetime, time, timedelta, date

# Test data from the game
opening_time = time(0, 0)  # 00:00:00
closing_time = time(23, 59)  # 23:59:00
slot_duration_minutes = 120  # 2 hours

target_date = date.today()
current_time = opening_time

iteration = 0
max_iterations = 30  # Safety limit

print(f"Opening: {opening_time}")
print(f"Closing: {closing_time}")
print(f"Slot Duration: {slot_duration_minutes} minutes")
print("\nSimulating slot generation loop:\n")

while current_time < closing_time and iteration < max_iterations:
    iteration += 1
    
    # Calculate end time
    start_datetime = datetime.combine(target_date, current_time)
    end_datetime = start_datetime + timedelta(minutes=slot_duration_minutes)
    end_time = end_datetime.time()
    
    print(f"Iteration {iteration:2d}: {current_time} -> {end_time}")
    
    # Check if end time exceeds closing
    if end_time > closing_time:
        print(f"   BREAK: {end_time} > {closing_time}")
        break
    
    # Check for time wraparound (this is the BUG!)
    if end_time < current_time:
        print(f"   ⚠️  TIME WRAPAROUND DETECTED: {end_time} < {current_time}")
        print(f"   This means the slot goes into the next day!")
        break
    
    # Move to next slot
    current_time = end_time
    
print(f"\nTotal iterations: {iteration}")

if iteration >= max_iterations:
    print("\n❌ INFINITE LOOP DETECTED! Hit max iterations.")
else:
    print("\n✅ Loop terminated normally")
