#!/usr/bin/env python3
"""
PT Rahaza ERP - Backend API Testing Suite
Focus: Phase 19A APS Gantt Chart endpoints + authentication
"""
import requests
import sys
import json
from datetime import datetime, date, timedelta

class APSBackendTester:
    def __init__(self, base_url="https://garment-erp-aps.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, auth_required=True):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        test_headers = {'Content-Type': 'application/json'}
        
        if auth_required and self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers)
            elif method == 'PATCH':
                response = self.session.patch(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=test_headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}", "PASS")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        # Log key fields for debugging
                        if 'kpis' in response_data:
                            self.log(f"   KPIs: {response_data['kpis']}")
                        if 'lines' in response_data and isinstance(response_data['lines'], list):
                            self.log(f"   Lines count: {len(response_data['lines'])}")
                        if 'work_orders' in response_data and isinstance(response_data['work_orders'], list):
                            self.log(f"   Work Orders count: {len(response_data['work_orders'])}")
                        if 'bars' in response_data and isinstance(response_data['bars'], list):
                            self.log(f"   Bars count: {len(response_data['bars'])}")
                except:
                    pass
                return True, response
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    error_data = response.json()
                    self.log(f"   Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    self.log(f"   Raw response: {response.text[:200]}")
                return False, response

        except Exception as e:
            self.log(f"❌ {name} - Exception: {str(e)}", "FAIL")
            return False, None

    def test_authentication(self):
        """Test login with admin credentials"""
        self.log("=== AUTHENTICATION TESTS ===")
        
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "api/auth/login",
            200,
            data={"email": "admin@garment.com", "password": "Admin@123"},
            auth_required=False
        )
        
        if success and response:
            try:
                data = response.json()
                if 'token' in data:
                    self.token = data['token']
                    self.log(f"✅ Token obtained: {self.token[:20]}...")
                    return True
                else:
                    self.log("❌ No token in response")
            except:
                self.log("❌ Failed to parse login response")
        
        return False

    def test_aps_gantt_endpoint(self):
        """Test main APS Gantt endpoint with various filters"""
        self.log("=== APS GANTT ENDPOINT TESTS ===")
        
        # Test basic gantt endpoint
        today = date.today()
        from_date = (today - timedelta(days=3)).isoformat()
        to_date = (today + timedelta(days=21)).isoformat()
        
        # Basic request
        success, response = self.run_test(
            "APS Gantt - Basic Request",
            "GET",
            f"api/rahaza/aps/gantt?from={from_date}&to={to_date}",
            200
        )
        
        if success and response:
            try:
                data = response.json()
                required_fields = ['meta', 'days', 'lines', 'work_orders', 'bars', 'capacity', 'kpis']
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    self.log(f"❌ Missing required fields: {missing_fields}")
                else:
                    self.log("✅ All required fields present in response")
                    
                    # Validate KPIs structure
                    kpis = data.get('kpis', {})
                    required_kpis = ['total_wo', 'overdue_count', 'at_risk_count', 'load_avg_pct']
                    missing_kpis = [kpi for kpi in required_kpis if kpi not in kpis]
                    if missing_kpis:
                        self.log(f"❌ Missing KPI fields: {missing_kpis}")
                    else:
                        self.log("✅ All required KPI fields present")
                        
            except Exception as e:
                self.log(f"❌ Error parsing gantt response: {e}")
        
        # Test with status filter
        self.run_test(
            "APS Gantt - Status Filter",
            "GET",
            f"api/rahaza/aps/gantt?from={from_date}&to={to_date}&status=released",
            200
        )
        
        # Test with priority filter
        self.run_test(
            "APS Gantt - Priority Filter", 
            "GET",
            f"api/rahaza/aps/gantt?from={from_date}&to={to_date}&priority=high",
            200
        )
        
        # Test with multiple filters
        self.run_test(
            "APS Gantt - Multiple Filters",
            "GET", 
            f"api/rahaza/aps/gantt?from={from_date}&to={to_date}&status=in_production&priority=normal",
            200
        )

    def test_aps_wo_detail_endpoint(self):
        """Test work order detail endpoint"""
        self.log("=== APS WORK ORDER DETAIL TESTS ===")
        
        # First get some work orders from gantt
        today = date.today()
        from_date = (today - timedelta(days=3)).isoformat()
        to_date = (today + timedelta(days=21)).isoformat()
        
        success, response = self.run_test(
            "Get Work Orders for Detail Test",
            "GET",
            f"api/rahaza/aps/gantt?from={from_date}&to={to_date}",
            200
        )
        
        wo_id = None
        if success and response:
            try:
                data = response.json()
                work_orders = data.get('work_orders', [])
                if work_orders:
                    wo_id = work_orders[0].get('id')
                    self.log(f"Found work order ID for testing: {wo_id}")
            except:
                pass
        
        if wo_id:
            # Test work order detail
            success, response = self.run_test(
                "APS Work Order Detail",
                "GET",
                f"api/rahaza/aps/wo/{wo_id}",
                200
            )
            
            if success and response:
                try:
                    data = response.json()
                    required_fields = ['work_order', 'model', 'line', 'progress_breakdown', 'risk']
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        self.log(f"❌ Missing required fields in WO detail: {missing_fields}")
                    else:
                        self.log("✅ All required fields present in WO detail")
                        
                        # Validate risk field
                        risk = data.get('risk')
                        valid_risks = ['on_track', 'at_risk', 'overdue']
                        if risk not in valid_risks:
                            self.log(f"❌ Invalid risk value: {risk}, expected one of {valid_risks}")
                        else:
                            self.log(f"✅ Valid risk value: {risk}")
                            
                except Exception as e:
                    self.log(f"❌ Error parsing WO detail response: {e}")
        else:
            self.log("⚠️ No work orders found to test detail endpoint")
            
        # Test with non-existent work order
        self.run_test(
            "APS Work Order Detail - Not Found",
            "GET",
            "api/rahaza/aps/wo/nonexistent-wo-id",
            404
        )

    def test_aps_reschedule_endpoint(self):
        """Test work order reschedule endpoint"""
        self.log("=== APS RESCHEDULE ENDPOINT TESTS ===")
        
        # Get a work order ID first
        today = date.today()
        from_date = (today - timedelta(days=3)).isoformat()
        to_date = (today + timedelta(days=21)).isoformat()
        
        success, response = self.run_test(
            "Get Work Orders for Reschedule Test",
            "GET",
            f"api/rahaza/aps/gantt?from={from_date}&to={to_date}",
            200
        )
        
        wo_id = None
        if success and response:
            try:
                data = response.json()
                work_orders = data.get('work_orders', [])
                # Find a work order that's not completed or cancelled
                for wo in work_orders:
                    if wo.get('status') not in ['completed', 'cancelled']:
                        wo_id = wo.get('id')
                        break
                if wo_id:
                    self.log(f"Found work order ID for reschedule test: {wo_id}")
            except:
                pass
        
        if wo_id:
            # Test valid reschedule
            new_start = (today + timedelta(days=1)).isoformat()
            new_end = (today + timedelta(days=5)).isoformat()
            
            success, response = self.run_test(
                "APS Reschedule - Valid Request",
                "PATCH",
                f"api/rahaza/aps/wo/{wo_id}/reschedule",
                200,
                data={
                    "target_start_date": new_start,
                    "target_end_date": new_end
                }
            )
            
            if success and response:
                try:
                    data = response.json()
                    if data.get('ok') and 'work_order' in data:
                        self.log("✅ Reschedule successful with proper response structure")
                    else:
                        self.log("❌ Reschedule response missing expected fields")
                except Exception as e:
                    self.log(f"❌ Error parsing reschedule response: {e}")
        else:
            self.log("⚠️ No suitable work orders found to test reschedule")
        
        # Test validation errors
        self.run_test(
            "APS Reschedule - Missing Fields",
            "PATCH",
            f"api/rahaza/aps/wo/{wo_id or 'test-wo'}/reschedule",
            400,
            data={"target_start_date": today.isoformat()}  # Missing end date
        )
        
        self.run_test(
            "APS Reschedule - Invalid Date Order",
            "PATCH", 
            f"api/rahaza/aps/wo/{wo_id or 'test-wo'}/reschedule",
            400,
            data={
                "target_start_date": (today + timedelta(days=5)).isoformat(),
                "target_end_date": today.isoformat()  # End before start
            }
        )
        
        self.run_test(
            "APS Reschedule - Non-existent WO",
            "PATCH",
            "api/rahaza/aps/wo/nonexistent-wo-id/reschedule", 
            404,
            data={
                "target_start_date": today.isoformat(),
                "target_end_date": (today + timedelta(days=2)).isoformat()
            }
        )

    def test_authentication_requirements(self):
        """Test that APS endpoints require authentication"""
        self.log("=== AUTHENTICATION REQUIREMENT TESTS ===")
        
        # Temporarily remove token
        original_token = self.token
        self.token = None
        
        today = date.today()
        from_date = (today - timedelta(days=3)).isoformat()
        to_date = (today + timedelta(days=21)).isoformat()
        
        # Test gantt endpoint without auth
        success, response = self.run_test(
            "APS Gantt - No Auth",
            "GET",
            f"api/rahaza/aps/gantt?from={from_date}&to={to_date}",
            401,  # Should return 401 or 403
            auth_required=False
        )
        
        if not success and response and response.status_code == 403:
            # 403 is also acceptable for auth failure
            self.tests_passed += 1
            self.log("✅ APS Gantt - No Auth (403 Forbidden)", "PASS")
        
        # Test WO detail without auth
        success, response = self.run_test(
            "APS WO Detail - No Auth",
            "GET",
            "api/rahaza/aps/wo/test-wo-id",
            401,
            auth_required=False
        )
        
        if not success and response and response.status_code == 403:
            self.tests_passed += 1
            self.log("✅ APS WO Detail - No Auth (403 Forbidden)", "PASS")
        
        # Test reschedule without auth
        success, response = self.run_test(
            "APS Reschedule - No Auth",
            "PATCH",
            "api/rahaza/aps/wo/test-wo-id/reschedule",
            401,
            data={"target_start_date": today.isoformat(), "target_end_date": (today + timedelta(days=1)).isoformat()},
            auth_required=False
        )
        
        if not success and response and response.status_code == 403:
            self.tests_passed += 1
            self.log("✅ APS Reschedule - No Auth (403 Forbidden)", "PASS")
        
        # Restore token
        self.token = original_token

    def test_server_health(self):
        """Test server health and basic endpoints"""
        self.log("=== SERVER HEALTH TESTS ===")
        
        # Test if server is running
        try:
            response = self.session.get(f"{self.base_url}/api/health", timeout=10)
            if response.status_code == 200:
                self.log("✅ Server health check passed")
            else:
                self.log(f"⚠️ Health endpoint returned {response.status_code}")
        except:
            self.log("⚠️ Health endpoint not available (expected)")
        
        # Test basic endpoints that should work
        self.run_test(
            "Get Employees",
            "GET", 
            "api/rahaza/employees",
            200
        )
        
        self.run_test(
            "Get Lines",
            "GET",
            "api/rahaza/lines", 
            200
        )
        
        self.run_test(
            "Get Work Orders",
            "GET",
            "api/rahaza/work-orders",
            200
        )

    def run_all_tests(self):
        """Run all test suites"""
        self.log("🚀 Starting PT Rahaza ERP Backend Tests - Phase 19A APS Focus")
        self.log(f"Base URL: {self.base_url}")
        
        # Authentication first
        if not self.test_authentication():
            self.log("❌ Authentication failed - stopping tests")
            return False
        
        # Server health
        self.test_server_health()
        
        # APS-specific tests
        self.test_aps_gantt_endpoint()
        self.test_aps_wo_detail_endpoint()
        self.test_aps_reschedule_endpoint()
        self.test_authentication_requirements()
        
        # Summary
        self.log("=" * 50)
        self.log(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            self.log("✅ Backend tests PASSED overall")
            return True
        else:
            self.log("❌ Backend tests FAILED overall")
            return False

def main():
    tester = APSBackendTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())