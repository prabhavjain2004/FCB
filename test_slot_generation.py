"""
Comprehensive test suite for slot generation functionality
Tests the slot generator in isolation and with database operations
"""
import os
import django
import sys
from datetime import date, time, timedelta
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gaming_cafe.settings')
django.setup()

from django.db import transaction
from booking.models import Game, GameSlot, SlotAvailability
from booking.slot_generator import SlotGenerator
from authentication.models import CafeOwner, TapNexSuperuser
from django.contrib.auth.models import User


class SlotGeneratorTester:
    """Test class for slot generation"""
    
    def __init__(self):
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        self.test_game = None
        
    def print_header(self, text):
        """Print a formatted header"""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}{text.center(70)}")
        print(f"{Fore.CYAN}{'='*70}\n")
    
    def print_test(self, test_name):
        """Print test name"""
        print(f"{Fore.YELLOW}🧪 Testing: {test_name}")
    
    def print_success(self, message):
        """Print success message"""
        print(f"{Fore.GREEN}✅ {message}")
        self.test_results['passed'] += 1
    
    def print_failure(self, message):
        """Print failure message"""
        print(f"{Fore.RED}❌ {message}")
        self.test_results['failed'] += 1
        self.test_results['errors'].append(message)
    
    def print_info(self, message):
        """Print info message"""
        print(f"{Fore.BLUE}ℹ️  {message}")
    
    def cleanup(self):
        """Clean up test data"""
        try:
            if self.test_game and self.test_game.name == 'Test Game - Auto Generated':
                # Only delete if we created it (not an existing game)
                # Delete all slots first
                GameSlot.objects.filter(game=self.test_game).delete()
                # Delete the game
                self.test_game.delete()
                self.print_info("Test data cleaned up")
            else:
                self.print_info("Using existing game - not cleaning up")
        except Exception as e:
            self.print_info(f"Cleanup warning: {str(e)}")
    
    def create_test_game(self):
        """Create a test game for testing"""
        self.print_test("Creating Test Game")
        
        try:
            # Try to use an existing game first
            existing_games = Game.objects.filter(is_active=True)
            if existing_games.exists():
                self.test_game = existing_games.first()
                self.print_success(f"Using existing game: {self.test_game.name} (ID: {self.test_game.id})")
                self.print_info(f"  - Opening: {self.test_game.opening_time}")
                self.print_info(f"  - Closing: {self.test_game.closing_time}")
                self.print_info(f"  - Slot Duration: {self.test_game.slot_duration_minutes} minutes")
                self.print_info(f"  - Available Days: {len(self.test_game.available_days)} days")
                return True
            
            # If no existing game, try to create one
            # Get or create a cafe owner for testing
            owner_user = User.objects.filter(cafeowner__isnull=False).first()
            
            if not owner_user:
                self.print_failure("No cafe owner found in database. Please create a game through the web interface first.")
                return False
            
            cafe_owner = CafeOwner.objects.get(user=owner_user)
            
            # Create test game
            self.test_game = Game.objects.create(
                name='Test Game - Auto Generated',
                cafe_owner=cafe_owner,
                capacity=4,
                booking_type='SHARED',
                opening_time=time(10, 0),  # 10:00 AM
                closing_time=time(22, 0),   # 10:00 PM
                slot_duration_minutes=60,    # 1 hour slots
                private_price=500.00,
                shared_price=150.00,
                available_days=['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'],
                is_active=True
            )
            
            self.print_success(f"Test game created: {self.test_game.name} (ID: {self.test_game.id})")
            self.print_info(f"  - Opening: {self.test_game.opening_time}")
            self.print_info(f"  - Closing: {self.test_game.closing_time}")
            self.print_info(f"  - Slot Duration: {self.test_game.slot_duration_minutes} minutes")
            self.print_info(f"  - Available Days: {len(self.test_game.available_days)} days")
            return True
            
        except Exception as e:
            self.print_failure(f"Failed to create test game: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_single_day_generation(self):
        """Test slot generation for a single day"""
        self.print_test("Single Day Slot Generation")
        
        try:
            target_date = date.today()
            
            # Generate slots
            result = SlotGenerator.generate_slots_for_game(
                self.test_game,
                target_date,
                target_date
            )
            
            # Check results
            if result['created'] > 0:
                self.print_success(f"Generated {result['created']} slots for {target_date}")
                
                # Verify slots in database
                db_slots = GameSlot.objects.filter(
                    game=self.test_game,
                    date=target_date
                ).count()
                
                if db_slots == result['created']:
                    self.print_success(f"Database verification: {db_slots} slots found")
                else:
                    self.print_failure(f"Database mismatch: Created {result['created']}, found {db_slots}")
                
                # Check expected slot count
                # (22:00 - 10:00) = 12 hours = 720 minutes / 60 = 12 slots
                expected_slots = 12
                if result['created'] == expected_slots:
                    self.print_success(f"Expected slot count matches: {expected_slots}")
                else:
                    self.print_info(f"Expected {expected_slots} slots, got {result['created']}")
                
            else:
                self.print_failure(f"No slots created. Errors: {result['errors']}")
                
        except Exception as e:
            self.print_failure(f"Exception during single day generation: {str(e)}")
    
    def test_multiple_day_generation(self):
        """Test slot generation for multiple days"""
        self.print_test("Multiple Day Slot Generation (7 days)")
        
        try:
            start_date = date.today() + timedelta(days=1)  # Tomorrow
            end_date = start_date + timedelta(days=6)       # Next 7 days
            
            # Generate slots
            result = SlotGenerator.generate_slots_for_game(
                self.test_game,
                start_date,
                end_date
            )
            
            if result['created'] > 0:
                self.print_success(f"Generated {result['created']} slots for {start_date} to {end_date}")
                
                # Verify database
                db_slots = GameSlot.objects.filter(
                    game=self.test_game,
                    date__range=[start_date, end_date]
                ).count()
                
                if db_slots == result['created']:
                    self.print_success(f"Database verification: {db_slots} slots found")
                else:
                    self.print_failure(f"Database mismatch: Created {result['created']}, found {db_slots}")
                
                # Expected: 7 days × 12 slots/day = 84 slots
                expected_slots = 7 * 12
                if result['created'] == expected_slots:
                    self.print_success(f"Expected slot count matches: {expected_slots}")
                else:
                    self.print_info(f"Expected {expected_slots} slots, got {result['created']}")
                    
            else:
                self.print_failure(f"No slots created. Errors: {result['errors']}")
                
        except Exception as e:
            self.print_failure(f"Exception during multiple day generation: {str(e)}")
    
    def test_slot_availability_creation(self):
        """Test that SlotAvailability objects are created correctly"""
        self.print_test("Slot Availability Creation")
        
        try:
            # Count slots and availabilities
            slot_count = GameSlot.objects.filter(game=self.test_game).count()
            availability_count = SlotAvailability.objects.filter(
                game_slot__game=self.test_game
            ).count()
            
            if slot_count == availability_count:
                self.print_success(f"All slots have availability tracking: {availability_count}/{slot_count}")
                
                # Check a sample availability
                sample_availability = SlotAvailability.objects.filter(
                    game_slot__game=self.test_game
                ).first()
                
                if sample_availability:
                    self.print_info(f"Sample availability: Capacity={sample_availability.total_capacity}, Booked={sample_availability.booked_spots}")
                    
                    if sample_availability.total_capacity == self.test_game.capacity:
                        self.print_success("Availability capacity matches game capacity")
                    else:
                        self.print_failure(f"Capacity mismatch: Game={self.test_game.capacity}, Availability={sample_availability.total_capacity}")
                        
            else:
                self.print_failure(f"Availability mismatch: {slot_count} slots, {availability_count} availabilities")
                
        except Exception as e:
            self.print_failure(f"Exception during availability check: {str(e)}")
    
    def test_duplicate_prevention(self):
        """Test that duplicate slots are not created"""
        self.print_test("Duplicate Slot Prevention")
        
        try:
            target_date = date.today() + timedelta(days=10)
            
            # Generate slots first time
            result1 = SlotGenerator.generate_slots_for_game(
                self.test_game,
                target_date,
                target_date
            )
            
            initial_count = result1['created']
            self.print_info(f"First generation: {initial_count} slots created")
            
            # Try to generate again
            result2 = SlotGenerator.generate_slots_for_game(
                self.test_game,
                target_date,
                target_date
            )
            
            duplicate_count = result2['created']
            
            if duplicate_count == 0:
                self.print_success("Duplicate prevention working: 0 duplicates created")
            else:
                self.print_failure(f"Duplicate prevention failed: {duplicate_count} duplicates created")
                
        except Exception as e:
            self.print_failure(f"Exception during duplicate test: {str(e)}")
    
    def test_performance(self):
        """Test performance of slot generation"""
        self.print_test("Performance Test (30 days generation)")
        
        import time as time_module
        
        try:
            start_date = date.today() + timedelta(days=15)
            end_date = start_date + timedelta(days=29)  # 30 days
            
            # Measure time
            start_time = time_module.time()
            
            result = SlotGenerator.generate_slots_for_game(
                self.test_game,
                start_date,
                end_date
            )
            
            end_time = time_module.time()
            duration = end_time - start_time
            
            if result['created'] > 0:
                slots_per_second = result['created'] / duration
                self.print_success(f"Generated {result['created']} slots in {duration:.2f} seconds")
                self.print_info(f"Performance: {slots_per_second:.1f} slots/second")
                
                # Check if fast enough (should be > 100 slots/second with bulk_create)
                if slots_per_second > 100:
                    self.print_success("Performance is optimal (using bulk_create)")
                else:
                    self.print_info("Performance could be improved (may be using legacy method)")
                    
            else:
                self.print_failure(f"No slots created. Errors: {result['errors']}")
                
        except Exception as e:
            self.print_failure(f"Exception during performance test: {str(e)}")
    
    def test_invalid_scenarios(self):
        """Test handling of invalid scenarios"""
        self.print_test("Invalid Scenario Handling")
        
        try:
            # Test 1: Past date generation
            past_date = date.today() - timedelta(days=1)
            result = SlotGenerator.generate_slots_for_game(
                self.test_game,
                past_date,
                past_date
            )
            
            if result['created'] == 0:
                self.print_success("Past date handling: No slots created (correct)")
            else:
                self.print_failure(f"Past date handling failed: {result['created']} slots created")
            
            # Test 2: Inactive game
            self.test_game.is_active = False
            self.test_game.save()
            
            result = SlotGenerator.generate_slots_for_game(
                self.test_game,
                date.today() + timedelta(days=50),
                date.today() + timedelta(days=50)
            )
            
            if result['created'] == 0:
                self.print_success("Inactive game handling: No slots created (correct)")
            else:
                self.print_failure(f"Inactive game handling failed: {result['created']} slots created")
            
            # Reactivate for other tests
            self.test_game.is_active = True
            self.test_game.save()
            
        except Exception as e:
            self.print_failure(f"Exception during invalid scenario test: {str(e)}")
    
    def run_all_tests(self):
        """Run all tests"""
        self.print_header("SLOT GENERATION COMPREHENSIVE TEST SUITE")
        
        # Create test game
        if not self.create_test_game():
            self.print_failure("Cannot continue without test game")
            return
        
        try:
            # Run all tests
            self.test_single_day_generation()
            self.test_multiple_day_generation()
            self.test_slot_availability_creation()
            self.test_duplicate_prevention()
            self.test_performance()
            self.test_invalid_scenarios()
            
        finally:
            # Cleanup
            self.cleanup()
        
        # Print summary
        self.print_header("TEST SUMMARY")
        total_tests = self.test_results['passed'] + self.test_results['failed']
        
        print(f"{Fore.CYAN}Total Tests: {total_tests}")
        print(f"{Fore.GREEN}Passed: {self.test_results['passed']}")
        print(f"{Fore.RED}Failed: {self.test_results['failed']}")
        
        if self.test_results['failed'] == 0:
            print(f"\n{Fore.GREEN}{Style.BRIGHT}🎉 ALL TESTS PASSED! 🎉")
        else:
            print(f"\n{Fore.RED}{Style.BRIGHT}⚠️  SOME TESTS FAILED")
            print(f"\n{Fore.YELLOW}Errors:")
            for error in self.test_results['errors']:
                print(f"  - {error}")


if __name__ == '__main__':
    tester = SlotGeneratorTester()
    tester.run_all_tests()
