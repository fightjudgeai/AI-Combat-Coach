#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class FightJudgeProTester:
    def __init__(self, base_url="https://dreamy-buck-5.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, auth_required=True):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {method} {url}")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers)
            elif method == 'PATCH':
                response = self.session.patch(url, json=data, headers=test_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, list):
                        print(f"   Response: List with {len(response_data)} items")
                    elif isinstance(response_data, dict):
                        print(f"   Response keys: {list(response_data.keys())}")
                except:
                    print(f"   Response: {response.text[:100]}...")
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                self.failed_tests.append({
                    'name': name,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'response': response.text[:200]
                })

            return success, response.json() if response.text and response.status_code < 500 else {}

        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            self.failed_tests.append({
                'name': name,
                'error': str(e)
            })
            return False, {}

    def test_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@fightpromo.com", "password": "Admin123!"},
            auth_required=False
        )
        return success

    def test_public_events(self):
        """Test public events endpoint (no auth required)"""
        success, response = self.run_test(
            "Public Events (No Auth)",
            "GET",
            "public/events",
            200,
            auth_required=False
        )
        return success, response

    def test_dashboard_stats(self):
        """Test dashboard stats"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        return success, response

    def test_officials_crud(self):
        """Test officials CRUD operations"""
        print("\n📋 Testing Officials CRUD...")
        
        # List officials
        success, officials = self.run_test(
            "List Officials",
            "GET",
            "officials",
            200
        )
        
        if success:
            print(f"   Found {len(officials)} officials")
            if len(officials) >= 5:
                print("✅ Expected 5+ seeded officials found")
            else:
                print(f"⚠️  Expected 5+ officials, found {len(officials)}")
        
        # Create new official
        new_official = {
            "name": "Test Official",
            "role": "referee",
            "email": "test@example.com",
            "phone": "555-0123",
            "rating": 4,
            "status": "active"
        }
        
        create_success, created = self.run_test(
            "Create Official",
            "POST",
            "officials",
            200,
            data=new_official
        )
        
        official_id = None
        if create_success and created.get('_id'):
            official_id = created['_id']
            print(f"   Created official with ID: {official_id}")
        
        # Test filter by role
        filter_success, filtered = self.run_test(
            "Filter Officials by Role",
            "GET",
            "officials?role=referee",
            200
        )
        
        if filter_success:
            print(f"   Found {len(filtered)} referees")
        
        # Clean up - delete test official
        if official_id:
            self.run_test(
                "Delete Test Official",
                "DELETE",
                f"officials/{official_id}",
                200
            )
        
        return success and create_success and filter_success

    def test_venues_crud(self):
        """Test venues CRUD operations"""
        print("\n🏢 Testing Venues CRUD...")
        
        # List venues
        success, venues = self.run_test(
            "List Venues",
            "GET",
            "venues",
            200
        )
        
        if success:
            print(f"   Found {len(venues)} venues")
            if len(venues) >= 3:
                print("✅ Expected 3+ seeded venues found")
            else:
                print(f"⚠️  Expected 3+ venues, found {len(venues)}")
        
        # Create new venue
        new_venue = {
            "name": "Test Arena",
            "city": "Test City",
            "state": "TS",
            "capacity": 5000,
            "rental_cost": 25000,
            "status": "available"
        }
        
        create_success, created = self.run_test(
            "Create Venue",
            "POST",
            "venues",
            200,
            data=new_venue
        )
        
        venue_id = None
        if create_success and created.get('_id'):
            venue_id = created['_id']
            print(f"   Created venue with ID: {venue_id}")
        
        # Clean up - delete test venue
        if venue_id:
            self.run_test(
                "Delete Test Venue",
                "DELETE",
                f"venues/{venue_id}",
                200
            )
        
        return success and create_success

    def test_compliance_dashboard(self):
        """Test compliance dashboard"""
        success, dashboard = self.run_test(
            "Compliance Dashboard",
            "GET",
            "compliance/dashboard",
            200
        )
        
        if success:
            expected_keys = ['total_licenses', 'expired_licenses', 'active_suspensions', 'expiring_count']
            for key in expected_keys:
                if key in dashboard:
                    print(f"   {key}: {dashboard[key]}")
                else:
                    print(f"⚠️  Missing key: {key}")
        
        return success

    def test_licenses_crud(self):
        """Test licenses CRUD"""
        print("\n📜 Testing Licenses CRUD...")
        
        # List licenses
        success, licenses = self.run_test(
            "List Licenses",
            "GET",
            "licenses",
            200
        )
        
        # Create license
        new_license = {
            "entity_type": "promoter",
            "entity_name": "Test Promoter",
            "license_type": "Professional",
            "state": "CA",
            "license_number": "TEST123",
            "issue_date": "2024-01-01",
            "expiry_date": "2025-01-01",
            "status": "active"
        }
        
        create_success, created = self.run_test(
            "Create License",
            "POST",
            "licenses",
            200,
            data=new_license
        )
        
        license_id = None
        if create_success and created.get('_id'):
            license_id = created['_id']
        
        # Clean up
        if license_id:
            self.run_test(
                "Delete Test License",
                "DELETE",
                f"licenses/{license_id}",
                200
            )
        
        return success and create_success

    def test_suspensions_crud(self):
        """Test medical suspensions CRUD"""
        print("\n🚫 Testing Medical Suspensions CRUD...")
        
        # List suspensions
        success, suspensions = self.run_test(
            "List Suspensions",
            "GET",
            "suspensions",
            200
        )
        
        # Create suspension (need a fighter first)
        fighters_success, fighters = self.run_test(
            "List Fighters for Suspension",
            "GET",
            "fighters",
            200
        )
        
        if fighters_success and len(fighters) > 0:
            fighter_id = fighters[0]['_id']
            new_suspension = {
                "fighter_id": fighter_id,
                "fighter_name": fighters[0]['name'],
                "type": "no_contact",
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
                "reason": "Test suspension"
            }
            
            create_success, created = self.run_test(
                "Create Medical Suspension",
                "POST",
                "suspensions",
                200,
                data=new_suspension
            )
            
            suspension_id = None
            if create_success and created.get('_id'):
                suspension_id = created['_id']
                
                # Test clear suspension
                clear_success, cleared = self.run_test(
                    "Clear Suspension",
                    "PATCH",
                    f"suspensions/{suspension_id}/clear",
                    200
                )
            
            return success and create_success
        else:
            print("⚠️  No fighters found for suspension test")
            return success

    def test_messages_crud(self):
        """Test messages CRUD"""
        print("\n💬 Testing Messages CRUD...")
        
        # List messages
        success, messages = self.run_test(
            "List Messages",
            "GET",
            "messages",
            200
        )
        
        # Create broadcast message
        new_message = {
            "to_type": "broadcast",
            "subject": "Test Broadcast",
            "body": "This is a test broadcast message",
            "priority": "normal"
        }
        
        create_success, created = self.run_test(
            "Create Broadcast Message",
            "POST",
            "messages",
            200,
            data=new_message
        )
        
        return success and create_success

    def test_documents_crud(self):
        """Test documents CRUD"""
        print("\n📄 Testing Documents CRUD...")
        
        # List documents
        success, documents = self.run_test(
            "List Documents",
            "GET",
            "documents",
            200
        )
        
        # Create manual document
        new_document = {
            "name": "Test Document",
            "type": "bout_agreement",
            "content": "This is a test document content",
            "status": "draft"
        }
        
        create_success, created = self.run_test(
            "Create Manual Document",
            "POST",
            "documents",
            200,
            data=new_document
        )
        
        doc_id = None
        if create_success and created.get('_id'):
            doc_id = created['_id']
        
        # Test AI document generation (should exist but may fail due to API key)
        events_success, events = self.run_test(
            "List Events for Doc Generation",
            "GET",
            "events",
            200
        )
        
        if events_success and len(events) > 0:
            event_id = events[0]['_id']
            gen_success, generated = self.run_test(
                "Generate AI Document",
                "POST",
                f"documents/generate?type=bout_agreement&event_id={event_id}",
                200
            )
            print(f"   AI Generation: {'✅ Success' if gen_success else '⚠️  Failed (expected if no LLM key)'}")
        
        # Clean up
        if doc_id:
            self.run_test(
                "Delete Test Document",
                "DELETE",
                f"documents/{doc_id}",
                200
            )
        
        return success and create_success

    def test_campaigns_crud(self):
        """Test marketing campaigns CRUD"""
        print("\n📢 Testing Marketing Campaigns CRUD...")
        
        # List campaigns
        success, campaigns = self.run_test(
            "List Campaigns",
            "GET",
            "campaigns",
            200
        )
        
        # Create campaign
        new_campaign = {
            "name": "Test Campaign",
            "type": "email",
            "content": "Test campaign content",
            "target_audience": "all",
            "status": "draft"
        }
        
        create_success, created = self.run_test(
            "Create Campaign",
            "POST",
            "campaigns",
            200,
            data=new_campaign
        )
        
        campaign_id = None
        if create_success and created.get('_id'):
            campaign_id = created['_id']
            
            # Test AI content generation
            gen_success, generated = self.run_test(
                "Generate Campaign Content",
                "POST",
                f"campaigns/{campaign_id}/generate-content",
                200
            )
            print(f"   AI Content Generation: {'✅ Success' if gen_success else '⚠️  Failed (expected if no LLM key)'}")
        
        # Clean up
        if campaign_id:
            self.run_test(
                "Delete Test Campaign",
                "DELETE",
                f"campaigns/{campaign_id}",
                200
            )
        
        return success and create_success

    def test_previous_features(self):
        """Test that previous features still work"""
        print("\n🔄 Testing Previous Features...")
        
        # Test events
        events_success, events = self.run_test(
            "List Events",
            "GET",
            "events",
            200
        )
        
        # Test fighters
        fighters_success, fighters = self.run_test(
            "List Fighters",
            "GET",
            "fighters",
            200
        )
        
        # Test sponsors
        sponsors_success, sponsors = self.run_test(
            "List Sponsors",
            "GET",
            "sponsors",
            200
        )
        
        # Test tasks
        tasks_success, tasks = self.run_test(
            "List Tasks",
            "GET",
            "tasks",
            200
        )
        
        # Test financials
        financials_success, financials = self.run_test(
            "List Financials",
            "GET",
            "financials",
            200
        )
        
        return all([events_success, fighters_success, sponsors_success, tasks_success, financials_success])

def main():
    print("🥊 FightJudge Pro Phase 4 Backend API Testing")
    print("=" * 50)
    
    tester = FightJudgeProTester()
    
    # Test login first
    if not tester.test_login():
        print("\n❌ Login failed - cannot continue with authenticated tests")
        return 1
    
    # Test public endpoint (no auth)
    public_success, public_events = tester.test_public_events()
    
    # Test dashboard
    dashboard_success = tester.test_dashboard_stats()
    
    # Test new Phase 4 modules
    officials_success = tester.test_officials_crud()
    venues_success = tester.test_venues_crud()
    compliance_success = tester.test_compliance_dashboard()
    licenses_success = tester.test_licenses_crud()
    suspensions_success = tester.test_suspensions_crud()
    messages_success = tester.test_messages_crud()
    documents_success = tester.test_documents_crud()
    campaigns_success = tester.test_campaigns_crud()
    
    # Test previous features
    previous_success = tester.test_previous_features()
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%")
    
    if tester.failed_tests:
        print("\n❌ FAILED TESTS:")
        for test in tester.failed_tests:
            error_msg = test.get('error', f"Expected {test.get('expected')}, got {test.get('actual')}")
            print(f"  - {test['name']}: {error_msg}")
    
    # Module summary
    modules = {
        'Authentication': tester.test_login(),
        'Public Events': public_success,
        'Dashboard': dashboard_success,
        'Officials': officials_success,
        'Venues': venues_success,
        'Compliance': compliance_success,
        'Licenses': licenses_success,
        'Suspensions': suspensions_success,
        'Messages': messages_success,
        'Documents': documents_success,
        'Campaigns': campaigns_success,
        'Previous Features': previous_success
    }
    
    print(f"\n📋 MODULE STATUS:")
    for module, status in modules.items():
        print(f"  {module}: {'✅ PASS' if status else '❌ FAIL'}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())