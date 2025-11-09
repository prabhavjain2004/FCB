#!/usr/bin/env python
"""
QR Security Deployment Script
Automates the deployment of QR verification security enhancements

Usage:
    python deploy_qr_security.py --check      # Check readiness
    python deploy_qr_security.py --deploy     # Deploy changes
    python deploy_qr_security.py --rollback   # Rollback if needed
"""

import os
import sys
import subprocess
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def run_command(command, description):
    """Run a shell command and return success status"""
    print_info(f"{description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print_success(f"{description} - Done")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print_error(f"{description} - Failed")
        print(f"Error: {e.stderr}")
        return False, e.stderr


def check_file_exists(filepath):
    """Check if a file exists"""
    return Path(filepath).exists()


def check_readiness():
    """Check if system is ready for deployment"""
    print_header("QR Security Deployment - Readiness Check")
    
    all_checks_passed = True
    
    # Check 1: Required files exist
    print_info("Checking required files...")
    required_files = [
        'booking/models.py',
        'booking/qr_service_enhanced.py',
        'booking/verification_views_enhanced.py',
        'booking/models_qr_verification_audit.py',
        'booking/migrations/0001_add_qr_security_fields.py',
        'booking/management/commands/fix_qr_tokens.py',
    ]
    
    for filepath in required_files:
        if check_file_exists(filepath):
            print_success(f"Found: {filepath}")
        else:
            print_error(f"Missing: {filepath}")
            all_checks_passed = False
    
    # Check 2: Django project structure
    print_info("\nChecking Django project...")
    if check_file_exists('manage.py'):
        print_success("Django project detected")
    else:
        print_error("manage.py not found - not a Django project?")
        all_checks_passed = False
    
    # Check 3: Database connection
    print_info("\nChecking database connection...")
    success, output = run_command(
        'python manage.py check --database default',
        'Database connection test'
    )
    if not success:
        all_checks_passed = False
    
    # Check 4: Migrations status
    print_info("\nChecking migrations...")
    success, output = run_command(
        'python manage.py showmigrations booking',
        'Checking booking app migrations'
    )
    
    # Summary
    print_header("Readiness Check Summary")
    if all_checks_passed:
        print_success("All checks passed! Ready for deployment.")
        print_info("\nNext step: Run with --deploy flag")
        return True
    else:
        print_error("Some checks failed. Please fix issues before deploying.")
        return False


def deploy():
    """Deploy the QR security enhancements"""
    print_header("QR Security Deployment - Starting")
    
    # Step 1: Backup database
    print_info("Step 1: Database Backup")
    print_warning("Please ensure you have a database backup before proceeding!")
    response = input("Do you have a database backup? (yes/no): ").lower()
    if response != 'yes':
        print_error("Deployment cancelled. Please backup your database first.")
        return False
    
    # Step 2: Run migrations
    print_info("\nStep 2: Creating migrations...")
    success, output = run_command(
        'python manage.py makemigrations booking',
        'Creating migrations'
    )
    if not success:
        print_error("Migration creation failed. Aborting deployment.")
        return False
    
    print_info("\nStep 3: Applying migrations...")
    success, output = run_command(
        'python manage.py migrate booking',
        'Applying migrations'
    )
    if not success:
        print_error("Migration failed. Please check the error and fix manually.")
        return False
    
    # Step 3: Fix existing bookings
    print_info("\nStep 4: Fixing existing bookings...")
    print_info("Running dry-run first...")
    success, output = run_command(
        'python manage.py fix_qr_tokens --dry-run',
        'Dry-run token fix'
    )
    
    if success:
        print(output)
        response = input("\nProceed with actual token fix? (yes/no): ").lower()
        if response == 'yes':
            success, output = run_command(
                'python manage.py fix_qr_tokens',
                'Fixing QR tokens'
            )
            if not success:
                print_warning("Token fix had issues, but deployment can continue.")
    
    # Step 4: Run checks
    print_info("\nStep 5: Running Django checks...")
    success, output = run_command(
        'python manage.py check',
        'Django system check'
    )
    if not success:
        print_warning("System check found issues. Please review.")
    
    # Summary
    print_header("Deployment Complete!")
    print_success("QR Security enhancements have been deployed successfully!")
    
    print_info("\nNext steps:")
    print("  1. Restart your application server")
    print("  2. Test QR verification: /booking/qr-scanner/")
    print("  3. Check audit log: /booking/verification-audit/")
    print("  4. Monitor for any errors in the first 24 hours")
    
    print_info("\nDocumentation:")
    print("  - Quick Start: QR_SECURITY_QUICK_START.md")
    print("  - Full Docs: QR_VERIFICATION_SECURITY_IMPLEMENTATION.md")
    print("  - Summary: QR_SECURITY_IMPLEMENTATION_SUMMARY.md")
    
    return True


def rollback():
    """Rollback the deployment"""
    print_header("QR Security Deployment - Rollback")
    
    print_warning("This will rollback the database migration.")
    print_warning("Make sure you have a backup before proceeding!")
    
    response = input("\nAre you sure you want to rollback? (yes/no): ").lower()
    if response != 'yes':
        print_info("Rollback cancelled.")
        return False
    
    # Get the migration to rollback to
    print_info("\nFinding previous migration...")
    success, output = run_command(
        'python manage.py showmigrations booking',
        'Listing migrations'
    )
    
    if success:
        print(output)
        migration_name = input("\nEnter the migration name to rollback to (or 'zero' for complete rollback): ")
        
        print_info(f"\nRolling back to: {migration_name}")
        success, output = run_command(
            f'python manage.py migrate booking {migration_name}',
            'Rolling back migration'
        )
        
        if success:
            print_success("Rollback completed successfully!")
            print_warning("Remember to restart your application server.")
            return True
        else:
            print_error("Rollback failed. Please check the error.")
            return False
    
    return False


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print_header("QR Security Deployment Script")
        print("Usage:")
        print("  python deploy_qr_security.py --check      # Check readiness")
        print("  python deploy_qr_security.py --deploy     # Deploy changes")
        print("  python deploy_qr_security.py --rollback   # Rollback if needed")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == '--check':
        success = check_readiness()
        sys.exit(0 if success else 1)
    
    elif command == '--deploy':
        success = deploy()
        sys.exit(0 if success else 1)
    
    elif command == '--rollback':
        success = rollback()
        sys.exit(0 if success else 1)
    
    else:
        print_error(f"Unknown command: {command}")
        print("Use --check, --deploy, or --rollback")
        sys.exit(1)


if __name__ == '__main__':
    main()
