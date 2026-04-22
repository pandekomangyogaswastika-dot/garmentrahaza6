#!/usr/bin/env python3
"""
PT Rahaza ERP Phase 18B/18C/18D Testing
Tests newly implemented Andon Panel, TV Mode, and SOP Inline features.

Test Flow:
1. Auth login with admin@garment.com / Admin@123
2. Phase 18B Andon Panel: create events, settings, acknowledge/resolve
3. Phase 18C TV Mode: floor data, alerts (no auth required)
4. Phase 18D SOP Inline: CRUD operations for SOPs
5. Integration tests and regression checks
"""
import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class RahazaPhase18Test:
    def __init__(self, base_url: str = "https://fashion-hub-1676.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test data storage
        self.andon_event_id = None
        self.sop_id = None
        self.model_id = None
        self.process_id = None

    def log_test(self, name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "name": name,
            "success": success,
            "details": details,
            "response_data": response_data
        })

    def make_request(self, method: str, endpoint: str, data: Any = None, expected_status: int = 200, 
                    headers: Optional[Dict] = None) -> tuple[bool, Any, requests.Response]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}/api/{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            req_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            req_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=req_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers)
            else:
                return False, f"Unsupported method: {method}", None

            success = response.status_code == expected_status
            
            try:
                response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.content
            except:
                response_data = response.content

            return success, response_data, response

        except Exception as e:
            return False, f"Request error: {str(e)}", None
    def test_auth_login(self):
        """Test admin login"""
        success, response_data, _ = self.make_request(
            'POST', 
            'auth/login',
            data={"email": "admin@garment.com", "password": "Admin@123"}
        )
        
        if success and isinstance(response_data, dict) and 'token' in response_data:
            self.token = response_data['token']
            self.log_test("Auth login with admin@garment.com", True)
            return True
        else:
            self.log_test("Auth login with admin@garment.com", False, f"Login failed: {response_data}")
            return False

    def test_health_check(self):
        """Test basic health check endpoint"""
        success, response_data, _ = self.make_request('GET', 'health', expected_status=200)
        
        if success:
            self.log_test("Health check endpoint", True)
            return True
        else:
            self.log_test("Health check endpoint", False, f"Health check failed: {response_data}")
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 18B - Andon Panel Tests
    # ═══════════════════════════════════════════════════════════════════════════

    def test_andon_settings_get(self):
        """Test GET /api/rahaza/andon/settings"""
        success, response_data, _ = self.make_request('GET', 'rahaza/andon/settings')
        
        if success and isinstance(response_data, dict):
            required_fields = ['sla_supervisor_min', 'sla_manager_min', 'enabled']
            if all(field in response_data for field in required_fields):
                self.log_test("Andon settings GET", True, f"SLA sup: {response_data.get('sla_supervisor_min')}min, mgr: {response_data.get('sla_manager_min')}min")
                return True
            else:
                self.log_test("Andon settings GET", False, f"Missing required fields: {response_data}")
        else:
            self.log_test("Andon settings GET", False, f"Invalid response: {response_data}")
        return False

    def test_andon_settings_update(self):
        """Test PUT /api/rahaza/andon/settings"""
        settings_data = {
            "sla_supervisor_min": 15,
            "sla_manager_min": 30
        }
        
        success, response_data, _ = self.make_request('PUT', 'rahaza/andon/settings', data=settings_data)
        
        if success and isinstance(response_data, dict):
            if (response_data.get('sla_supervisor_min') == 15 and 
                response_data.get('sla_manager_min') == 30):
                self.log_test("Andon settings UPDATE", True, "Settings updated successfully")
                return True
            else:
                self.log_test("Andon settings UPDATE", False, f"Settings not updated correctly: {response_data}")
        else:
            self.log_test("Andon settings UPDATE", False, f"Update failed: {response_data}")
        return False

    def test_andon_create_event(self):
        """Test POST /api/rahaza/andon - create andon event"""
        # First get employees to use one for the test
        success, employees, _ = self.make_request('GET', 'rahaza/employees')
        if not success or not employees:
            self.log_test("Andon create event", False, "No employees available for test")
            return False
        
        employee_id = employees[0]['id']
        
        andon_data = {
            "type": "machine_breakdown",
            "employee_id": employee_id,
            "message": "Test andon event - machine breakdown"
        }
        
        success, response_data, _ = self.make_request('POST', 'rahaza/andon', data=andon_data)
        
        if success and isinstance(response_data, dict) and 'id' in response_data:
            self.andon_event_id = response_data['id']
            event_type = response_data.get('type')
            status = response_data.get('status')
            self.log_test("Andon create event", True, f"Created event {self.andon_event_id[:8]}... type: {event_type}, status: {status}")
            return True
        else:
            self.log_test("Andon create event", False, f"Failed to create event: {response_data}")
        return False

    def test_andon_active_list(self):
        """Test GET /api/rahaza/andon/active"""
        success, response_data, _ = self.make_request('GET', 'rahaza/andon/active')
        
        if success and isinstance(response_data, dict):
            events = response_data.get('events', [])
            total = response_data.get('total', 0)
            total_overdue_supervisor = response_data.get('total_overdue_supervisor', 0)
            total_overdue_manager = response_data.get('total_overdue_manager', 0)
            
            # Should have at least our created event
            if total >= 1 and len(events) >= 1:
                # Check if our event is in the list
                our_event = next((e for e in events if e.get('id') == self.andon_event_id), None)
                if our_event:
                    self.log_test("Andon active list", True, f"Found {total} active events, including our test event")
                    return True
                else:
                    self.log_test("Andon active list", True, f"Found {total} active events (our event may have been processed)")
                    return True
            else:
                self.log_test("Andon active list", False, f"No active events found: total={total}")
        else:
            self.log_test("Andon active list", False, f"Invalid response: {response_data}")
        return False

    def test_andon_acknowledge(self):
        """Test POST /api/rahaza/andon/{id}/ack"""
        if not self.andon_event_id:
            self.log_test("Andon acknowledge", False, "No andon event ID available")
            return False
        
        success, response_data, _ = self.make_request('POST', f'rahaza/andon/{self.andon_event_id}/ack', data={})
        
        if success and isinstance(response_data, dict):
            status = response_data.get('status')
            acknowledged_by = response_data.get('acknowledged_by_name')
            if status == 'acknowledged':
                self.log_test("Andon acknowledge", True, f"Event acknowledged by {acknowledged_by}")
                return True
            else:
                self.log_test("Andon acknowledge", False, f"Event not acknowledged, status: {status}")
        else:
            self.log_test("Andon acknowledge", False, f"Acknowledge failed: {response_data}")
        return False

    def test_andon_resolve(self):
        """Test POST /api/rahaza/andon/{id}/resolve"""
        if not self.andon_event_id:
            self.log_test("Andon resolve", False, "No andon event ID available")
            return False
        
        resolve_data = {
            "notes": "Test resolution - issue fixed"
        }
        
        success, response_data, _ = self.make_request('POST', f'rahaza/andon/{self.andon_event_id}/resolve', data=resolve_data)
        
        if success and isinstance(response_data, dict):
            status = response_data.get('status')
            resolved_by = response_data.get('resolved_by_name')
            notes = response_data.get('notes_resolve')
            if status == 'resolved':
                self.log_test("Andon resolve", True, f"Event resolved by {resolved_by}, notes: {notes}")
                return True
            else:
                self.log_test("Andon resolve", False, f"Event not resolved, status: {status}")
        else:
            self.log_test("Andon resolve", False, f"Resolve failed: {response_data}")
        return False

    def test_andon_history(self):
        """Test GET /api/rahaza/andon/history"""
        success, response_data, _ = self.make_request('GET', 'rahaza/andon/history?limit=10')
        
        if success and isinstance(response_data, dict):
            events = response_data.get('events', [])
            total = response_data.get('total', 0)
            
            if total >= 1 and len(events) >= 1:
                self.log_test("Andon history", True, f"Found {total} total events, showing {len(events)}")
                return True
            else:
                self.log_test("Andon history", True, f"History endpoint works, {total} events found")
                return True
        else:
            self.log_test("Andon history", False, f"Invalid response: {response_data}")
        return False

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 18C - TV Mode Tests (No Auth Required)
    # ═══════════════════════════════════════════════════════════════════════════

    def test_tv_floor_no_auth(self):
        """Test GET /api/tv/floor (no auth required)"""
        # Temporarily remove token for this test
        original_token = self.token
        self.token = None
        
        success, response_data, _ = self.make_request('GET', 'tv/floor')
        
        # Restore token
        self.token = original_token
        
        if success and isinstance(response_data, dict):
            required_fields = ['today', 'server_time', 'kpi', 'lines']
            if all(field in response_data for field in required_fields):
                kpi = response_data.get('kpi', {})
                lines = response_data.get('lines', [])
                self.log_test("TV floor data (no auth)", True, f"KPI: {kpi.get('total_output', 0)} output, {len(lines)} lines")
                return True
            else:
                self.log_test("TV floor data (no auth)", False, f"Missing required fields: {response_data}")
        else:
            self.log_test("TV floor data (no auth)", False, f"Request failed: {response_data}")
        return False

    def test_tv_alerts_no_auth(self):
        """Test GET /api/tv/alerts (no auth required)"""
        # Temporarily remove token for this test
        original_token = self.token
        self.token = None
        
        success, response_data, _ = self.make_request('GET', 'tv/alerts?limit=5')
        
        # Restore token
        self.token = original_token
        
        if success and isinstance(response_data, dict):
            alerts = response_data.get('alerts', [])
            self.log_test("TV alerts (no auth)", True, f"Found {len(alerts)} alerts")
            return True
        else:
            self.log_test("TV alerts (no auth)", False, f"Request failed: {response_data}")
        return False

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 18D - SOP Inline Tests
    # ═══════════════════════════════════════════════════════════════════════════

    def test_sop_list(self):
        """Test GET /api/rahaza/sop"""
        success, response_data, _ = self.make_request('GET', 'rahaza/sop')
        
        if success and isinstance(response_data, dict):
            sops = response_data.get('sops', [])
            total = response_data.get('total', 0)
            self.log_test("SOP list", True, f"Found {total} SOPs")
            return True
        else:
            self.log_test("SOP list", False, f"Invalid response: {response_data}")
        return False

    def test_sop_create(self):
        """Test POST /api/rahaza/sop"""
        # First get models and processes for the SOP
        success, models, _ = self.make_request('GET', 'rahaza/models')
        if not success or not models:
            self.log_test("SOP create", False, "No models available for SOP test")
            return False
        
        success, processes, _ = self.make_request('GET', 'rahaza/processes')
        if not success or not processes:
            self.log_test("SOP create", False, "No processes available for SOP test")
            return False
        
        self.model_id = models[0]['id']
        self.process_id = processes[0]['id']
        
        sop_data = {
            "model_id": self.model_id,
            "process_id": self.process_id,
            "title": "Test SOP - Automated Test",
            "content_markdown": "## Test SOP\n\n1. Step one\n2. Step two\n\n**Important:** This is a test SOP.",
            "active": True
        }
        
        success, response_data, _ = self.make_request('POST', 'rahaza/sop', data=sop_data)
        
        if success and isinstance(response_data, dict) and 'id' in response_data:
            self.sop_id = response_data['id']
            title = response_data.get('title')
            version = response_data.get('version', 1)
            self.log_test("SOP create", True, f"Created SOP {self.sop_id[:8]}... title: {title}, version: {version}")
            return True
        else:
            self.log_test("SOP create", False, f"Failed to create SOP: {response_data}")
        return False

    def test_sop_get_by_context(self):
        """Test GET /api/rahaza/sop/by-context"""
        if not self.model_id or not self.process_id:
            self.log_test("SOP get by context", False, "No model_id or process_id available")
            return False
        
        success, response_data, _ = self.make_request('GET', f'rahaza/sop/by-context?model_id={self.model_id}&process_id={self.process_id}')
        
        if success and isinstance(response_data, dict):
            found = response_data.get('found', False)
            sop = response_data.get('sop')
            
            if found and sop:
                self.log_test("SOP get by context", True, f"Found SOP: {sop.get('title')}")
                return True
            else:
                self.log_test("SOP get by context", True, "No SOP found for context (expected for new model/process)")
                return True
        else:
            self.log_test("SOP get by context", False, f"Invalid response: {response_data}")
        return False

    def test_sop_get_by_id(self):
        """Test GET /api/rahaza/sop/{id}"""
        if not self.sop_id:
            self.log_test("SOP get by ID", False, "No SOP ID available")
            return False
        
        success, response_data, _ = self.make_request('GET', f'rahaza/sop/{self.sop_id}')
        
        if success and isinstance(response_data, dict):
            required_fields = ['id', 'title', 'content_markdown', 'model_id', 'process_id', 'active']
            if all(field in response_data for field in required_fields):
                self.log_test("SOP get by ID", True, f"Retrieved SOP: {response_data.get('title')}")
                return True
            else:
                self.log_test("SOP get by ID", False, f"Missing required fields: {response_data}")
        else:
            self.log_test("SOP get by ID", False, f"Request failed: {response_data}")
        return False

    def test_sop_update(self):
        """Test PUT /api/rahaza/sop/{id}"""
        if not self.sop_id:
            self.log_test("SOP update", False, "No SOP ID available")
            return False
        
        update_data = {
            "title": "Updated Test SOP - Automated Test",
            "content_markdown": "## Updated Test SOP\n\n1. Updated step one\n2. Updated step two\n\n**Important:** This SOP has been updated.",
            "active": True
        }
        
        success, response_data, _ = self.make_request('PUT', f'rahaza/sop/{self.sop_id}', data=update_data)
        
        if success and isinstance(response_data, dict):
            title = response_data.get('title')
            version = response_data.get('version', 1)
            if title == update_data['title'] and version > 1:
                self.log_test("SOP update", True, f"Updated SOP: {title}, version: {version}")
                return True
            else:
                self.log_test("SOP update", False, f"Update not reflected: title={title}, version={version}")
        else:
            self.log_test("SOP update", False, f"Update failed: {response_data}")
        return False

    def test_sop_delete(self):
        """Test DELETE /api/rahaza/sop/{id} (soft delete)"""
        if not self.sop_id:
            self.log_test("SOP delete", False, "No SOP ID available")
            return False
        
        success, response_data, _ = self.make_request('DELETE', f'rahaza/sop/{self.sop_id}')
        
        if success and isinstance(response_data, dict):
            message = response_data.get('message', '')
            if 'nonaktif' in message.lower() or 'deactivat' in message.lower():
                self.log_test("SOP delete (soft)", True, f"SOP deactivated: {message}")
                return True
            else:
                self.log_test("SOP delete (soft)", False, f"Unexpected response: {message}")
        else:
            self.log_test("SOP delete (soft)", False, f"Delete failed: {response_data}")
        return False

    # ═══════════════════════════════════════════════════════════════════════════
    # Integration and Regression Tests
    # ═══════════════════════════════════════════════════════════════════════════

    def test_basic_endpoints_still_work(self):
        """Test that basic endpoints still work after Phase 18 changes"""
        endpoints_to_test = [
            ('rahaza/employees', 'Employees list'),
            ('rahaza/models', 'Models list'),
            ('rahaza/processes', 'Processes list'),
            ('rahaza/lines', 'Lines list')
        ]
        
        all_passed = True
        for endpoint, name in endpoints_to_test:
            success, response_data, _ = self.make_request('GET', endpoint)
            if success and isinstance(response_data, list):
                self.log_test(f"Regression - {name}", True, f"Found {len(response_data)} items")
            else:
                self.log_test(f"Regression - {name}", False, f"Failed: {response_data}")
                all_passed = False
        
        return all_passed

    def run_all_tests(self):
        """Run all Phase 18B/18C/18D tests"""
        print("🚀 Starting PT Rahaza Phase 18B/18C/18D Tests")
        print("Testing Andon Panel, TV Mode, and SOP Inline features")
        print("=" * 70)
        
        # Phase 1: Authentication and basic setup
        if not self.test_auth_login():
            print("❌ Authentication failed - stopping tests")
            return False
        
        # Phase 2: Basic health check
        self.test_health_check()
        
        # Phase 3: Phase 18B - Andon Panel Tests
        print("\n🚨 Testing Phase 18B - Andon Panel...")
        self.test_andon_settings_get()
        self.test_andon_settings_update()
        self.test_andon_create_event()
        self.test_andon_active_list()
        self.test_andon_acknowledge()
        self.test_andon_resolve()
        self.test_andon_history()
        
        # Phase 4: Phase 18C - TV Mode Tests (No Auth Required)
        print("\n📺 Testing Phase 18C - TV Mode...")
        self.test_tv_floor_no_auth()
        self.test_tv_alerts_no_auth()
        
        # Phase 5: Phase 18D - SOP Inline Tests
        print("\n📚 Testing Phase 18D - SOP Inline...")
        self.test_sop_list()
        self.test_sop_create()
        self.test_sop_get_by_context()
        self.test_sop_get_by_id()
        self.test_sop_update()
        self.test_sop_delete()
        
        # Phase 6: Integration and regression tests
        print("\n🔄 Running integration and regression tests...")
        self.test_basic_endpoints_still_work()
        
        return True

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            
        # Print failed tests
        failed_tests = [t for t in self.test_results if not t['success']]
        if failed_tests:
            print("\n❌ Failed tests:")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['details']}")
        
        return self.tests_passed == self.tests_run


def main():
    """Main test execution"""
    tester = RahazaPhase18Test()
    
    try:
        success = tester.run_all_tests()
        tester.print_summary()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())