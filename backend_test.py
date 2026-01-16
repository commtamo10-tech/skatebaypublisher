#!/usr/bin/env python3

import requests
import sys
import json
import time
from datetime import datetime
from pathlib import Path
import tempfile
from PIL import Image
import io

class SkateBAYAPITester:
    def __init__(self, base_url="https://skatebay-manager.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.session = requests.Session()
        self.batch_id = None
        self.job_id = None
        self.group_ids = []

    def log_result(self, test_name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            self.failed_tests.append({"test": test_name, "details": details})
            print(f"❌ {test_name} - {details}")

    def test_login(self):
        """Test admin login"""
        print("\n🔐 Testing Authentication...")
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json={"password": "admin123"},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "token" in data:
                    self.token = data["token"]
                    self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                    self.log_result("Login with admin123", True)
                    return True
                else:
                    self.log_result("Login with admin123", False, "No token in response")
            else:
                self.log_result("Login with admin123", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Login with admin123", False, f"Exception: {str(e)}")
        
        return False

    def test_auth_me(self):
        """Test /auth/me endpoint"""
        if not self.token:
            self.log_result("GET /auth/me", False, "No token available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/auth/me")
            
            if response.status_code == 200:
                data = response.json()
                if "user" in data and data["user"] == "admin":
                    self.log_result("GET /auth/me", True)
                    return True
                else:
                    self.log_result("GET /auth/me", False, f"Unexpected response: {data}")
            else:
                self.log_result("GET /auth/me", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /auth/me", False, f"Exception: {str(e)}")
        
        return False

    def test_stats(self):
        """Test dashboard stats endpoint"""
        print("\n📊 Testing Stats...")
        
        if not self.token:
            self.log_result("GET /stats", False, "No token available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/stats")
            
            if response.status_code == 200:
                data = response.json()
                expected_keys = ["DRAFT", "READY", "PUBLISHED", "ERROR", "total"]
                if all(key in data for key in expected_keys):
                    self.log_result("GET /stats", True)
                    return True
                else:
                    self.log_result("GET /stats", False, f"Missing keys in response: {data}")
            else:
                self.log_result("GET /stats", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /stats", False, f"Exception: {str(e)}")
        
        return False

    def test_drafts_list(self):
        """Test list drafts endpoint"""
        print("\n📝 Testing Drafts...")
        
        if not self.token:
            self.log_result("GET /drafts", False, "No token available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/drafts")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result("GET /drafts", True)
                    return True
                else:
                    self.log_result("GET /drafts", False, f"Expected list, got: {type(data)}")
            else:
                self.log_result("GET /drafts", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /drafts", False, f"Exception: {str(e)}")
        
        return False

    def test_create_draft(self):
        """Test creating a new draft"""
        if not self.token:
            self.log_result("POST /drafts", False, "No token available")
            return None
            
        try:
            draft_data = {
                "item_type": "WHL",
                "category_id": "16265",
                "price": 25.99,
                "image_urls": []
            }
            
            response = self.session.post(
                f"{self.base_url}/api/drafts",
                json=draft_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and "sku" in data:
                    self.log_result("POST /drafts", True)
                    return data["id"]
                else:
                    self.log_result("POST /drafts", False, f"Missing id/sku in response: {data}")
            else:
                self.log_result("POST /drafts", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("POST /drafts", False, f"Exception: {str(e)}")
        
        return None

    def test_create_app_draft(self):
        """Test creating a new APP (Apparel) draft"""
        print("\n👕 Testing APP Item Type Creation...")
        
        if not self.token:
            self.log_result("POST /drafts (APP type)", False, "No token available")
            return None
            
        try:
            draft_data = {
                "item_type": "APP",
                "category_id": "155184",  # Skateboard apparel category
                "price": 45.99,
                "image_urls": []
            }
            
            response = self.session.post(
                f"{self.base_url}/api/drafts",
                json=draft_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and "sku" in data and data.get("item_type") == "APP":
                    self.log_result("POST /drafts (APP type)", True)
                    return data["id"]
                else:
                    self.log_result("POST /drafts (APP type)", False, f"Missing fields or wrong type: {data}")
            else:
                self.log_result("POST /drafts (APP type)", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("POST /drafts (APP type)", False, f"Exception: {str(e)}")
        
        return None

    def test_get_draft(self, draft_id):
        """Test getting a specific draft"""
        if not self.token or not draft_id:
            self.log_result("GET /drafts/{id}", False, "No token or draft_id available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/drafts/{draft_id}")
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and data["id"] == draft_id:
                    self.log_result("GET /drafts/{id}", True)
                    return True
                else:
                    self.log_result("GET /drafts/{id}", False, f"ID mismatch: {data}")
            else:
                self.log_result("GET /drafts/{id}", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /drafts/{id}", False, f"Exception: {str(e)}")
        
        return False

    def test_llm_generation(self, draft_id):
        """Test LLM content generation"""
        print("\n🤖 Testing LLM Generation...")
        
        if not self.token or not draft_id:
            self.log_result("POST /drafts/{id}/generate", False, "No token or draft_id available")
            return False
            
        try:
            response = self.session.post(f"{self.base_url}/api/drafts/{draft_id}/generate")
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "draft" in data:
                    self.log_result("POST /drafts/{id}/generate", True)
                    return True
                else:
                    self.log_result("POST /drafts/{id}/generate", False, f"Unexpected response: {data}")
            else:
                self.log_result("POST /drafts/{id}/generate", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("POST /drafts/{id}/generate", False, f"Exception: {str(e)}")
        
        return False

    def test_settings(self):
        """Test settings endpoints"""
        print("\n⚙️ Testing Settings...")
        
        if not self.token:
            self.log_result("GET /settings", False, "No token available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/settings")
            
            if response.status_code == 200:
                data = response.json()
                if "ebay_connected" in data:
                    self.log_result("GET /settings", True)
                    return True
                else:
                    self.log_result("GET /settings", False, f"Missing ebay_connected: {data}")
            else:
                self.log_result("GET /settings", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /settings", False, f"Exception: {str(e)}")
        
        return False

    def test_ebay_status(self):
        """Test eBay connection status"""
        if not self.token:
            self.log_result("GET /ebay/status", False, "No token available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/ebay/status")
            
            if response.status_code == 200:
                data = response.json()
                if "connected" in data:
                    self.log_result("GET /ebay/status", True)
                    return True
                else:
                    self.log_result("GET /ebay/status", False, f"Missing connected field: {data}")
            else:
                self.log_result("GET /ebay/status", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /ebay/status", False, f"Exception: {str(e)}")
        
        return False

    def test_draft_preview(self, draft_id):
        """Test draft preview endpoint with HTML sanitization"""
        print("\n👁️ Testing Draft Preview...")
        
        if not self.token or not draft_id:
            self.log_result("GET /drafts/{id}/preview", False, "No token or draft_id available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/drafts/{draft_id}/preview")
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "sku", "title", "price", "categoryId", "condition", 
                                 "images", "aspects", "descriptionHtml", "descriptionRaw", "status", "itemType"]
                
                if all(field in data for field in required_fields):
                    # Test HTML sanitization - check that dangerous tags are removed
                    html_content = data.get("descriptionHtml", "")
                    raw_content = data.get("descriptionRaw", "")
                    
                    # Check that script, iframe, style tags are not in sanitized HTML
                    dangerous_tags = ["<script", "<iframe", "<style", "javascript:", "onclick="]
                    has_dangerous_content = any(tag.lower() in html_content.lower() for tag in dangerous_tags)
                    
                    if has_dangerous_content:
                        self.log_result("GET /drafts/{id}/preview", False, "HTML sanitization failed - dangerous tags found")
                        return False
                    
                    self.log_result("GET /drafts/{id}/preview", True)
                    return True
                else:
                    missing_fields = [field for field in required_fields if field not in data]
                    self.log_result("GET /drafts/{id}/preview", False, f"Missing fields: {missing_fields}")
            else:
                self.log_result("GET /drafts/{id}/preview", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /drafts/{id}/preview", False, f"Exception: {str(e)}")
        
        return False

    def test_title_manually_edited_field(self, draft_id):
        """Test that draft loads with title_manually_edited field"""
        print("\n🏷️ Testing Title Manually Edited Field...")
        
        if not self.token or not draft_id:
            self.log_result("Draft has title_manually_edited field", False, "No token or draft_id available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/drafts/{draft_id}")
            
            if response.status_code == 200:
                data = response.json()
                if "title_manually_edited" in data:
                    # Should default to False for new drafts
                    if data["title_manually_edited"] == False:
                        self.log_result("Draft has title_manually_edited field", True)
                        return True
                    else:
                        self.log_result("Draft has title_manually_edited field", False, f"Expected False, got {data['title_manually_edited']}")
                else:
                    self.log_result("Draft has title_manually_edited field", False, "Field missing from response")
            else:
                self.log_result("Draft has title_manually_edited field", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Draft has title_manually_edited field", False, f"Exception: {str(e)}")
        
        return False

    def test_description_manually_edited_field(self, draft_id):
        """Test that draft loads with description_manually_edited field"""
        print("\n📝 Testing Description Manually Edited Field...")
        
        if not self.token or not draft_id:
            self.log_result("Draft has description_manually_edited field", False, "No token or draft_id available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/drafts/{draft_id}")
            
            if response.status_code == 200:
                data = response.json()
                if "description_manually_edited" in data:
                    # Should default to False for new drafts
                    if data["description_manually_edited"] == False:
                        self.log_result("Draft has description_manually_edited field", True)
                        return True
                    else:
                        self.log_result("Draft has description_manually_edited field", False, f"Expected False, got {data['description_manually_edited']}")
                else:
                    self.log_result("Draft has description_manually_edited field", False, "Field missing from response")
            else:
                self.log_result("Draft has description_manually_edited field", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Draft has description_manually_edited field", False, f"Exception: {str(e)}")
        
        return False

    def test_patch_title_manually_edited(self, draft_id):
        """Test PATCH /api/drafts/{id} updates title_manually_edited field"""
        print("\n✏️ Testing PATCH title_manually_edited...")
        
        if not self.token or not draft_id:
            self.log_result("PATCH title_manually_edited", False, "No token or draft_id available")
            return False
            
        try:
            # Test updating title_manually_edited to True
            update_data = {
                "title_manually_edited": True,
                "title": "Manual Test Title"
            }
            
            response = self.session.patch(
                f"{self.base_url}/api/drafts/{draft_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("title_manually_edited") == True and data.get("title") == "Manual Test Title":
                    self.log_result("PATCH title_manually_edited", True)
                    return True
                else:
                    self.log_result("PATCH title_manually_edited", False, f"Update failed: {data}")
            else:
                self.log_result("PATCH title_manually_edited", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("PATCH title_manually_edited", False, f"Exception: {str(e)}")
        
        return False

    def test_patch_description_manually_edited(self, draft_id):
        """Test PATCH /api/drafts/{id} updates description_manually_edited field"""
        print("\n📝 Testing PATCH description_manually_edited...")
        
        if not self.token or not draft_id:
            self.log_result("PATCH description_manually_edited", False, "No token or draft_id available")
            return False
            
        try:
            # Test updating description_manually_edited to True
            update_data = {
                "description_manually_edited": True,
                "description": "Manual Test Description"
            }
            
            response = self.session.patch(
                f"{self.base_url}/api/drafts/{draft_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("description_manually_edited") == True and data.get("description") == "Manual Test Description":
                    self.log_result("PATCH description_manually_edited", True)
                    return True
                else:
                    self.log_result("PATCH description_manually_edited", False, f"Update failed: {data}")
            else:
                self.log_result("PATCH description_manually_edited", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("PATCH description_manually_edited", False, f"Exception: {str(e)}")
        
        return False

    def test_title_no_unknown_values(self, draft_id):
        """Test that title never contains 'Unknown' or 'N/A'"""
        print("\n🚫 Testing Title Excludes Unknown Values...")
        
        if not self.token or not draft_id:
            self.log_result("Title excludes Unknown/N/A", False, "No token or draft_id available")
            return False
            
        try:
            # Update draft with aspects containing Unknown values
            aspects_with_unknown = {
                "Brand": "Powell Peralta",
                "Model": "Unknown",
                "Size": "N/A",
                "Era": "1980s",
                "Color": "Red"
            }
            
            update_data = {
                "aspects": aspects_with_unknown,
                "title_manually_edited": False  # Allow auto-generation
            }
            
            response = self.session.patch(
                f"{self.base_url}/api/drafts/{draft_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                title = data.get("title", "")
                
                # Check that title doesn't contain Unknown or N/A
                forbidden_words = ["Unknown", "N/A", "(Unknown)", "undefined", "null"]
                has_forbidden = any(word.lower() in title.lower() for word in forbidden_words)
                
                if not has_forbidden:
                    self.log_result("Title excludes Unknown/N/A", True)
                    return True
                else:
                    self.log_result("Title excludes Unknown/N/A", False, f"Title contains forbidden words: {title}")
            else:
                self.log_result("Title excludes Unknown/N/A", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Title excludes Unknown/N/A", False, f"Exception: {str(e)}")
        
        return False

    def test_preview_cache_busting(self, draft_id):
        """Test that preview fetches fresh data (no cache)"""
        print("\n🔄 Testing Preview Cache Busting...")
        
        if not self.token or not draft_id:
            self.log_result("Preview fetches fresh data", False, "No token or draft_id available")
            return False
            
        try:
            # Make first preview request
            response1 = self.session.get(f"{self.base_url}/api/drafts/{draft_id}/preview")
            
            if response1.status_code != 200:
                self.log_result("Preview fetches fresh data", False, f"First request failed: {response1.status_code}")
                return False
            
            # Update the draft
            update_data = {
                "title": f"Updated Title {datetime.now().strftime('%H%M%S')}"
            }
            
            update_response = self.session.patch(
                f"{self.base_url}/api/drafts/{draft_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            if update_response.status_code != 200:
                self.log_result("Preview fetches fresh data", False, "Failed to update draft")
                return False
            
            # Make second preview request with cache-busting headers
            response2 = self.session.get(
                f"{self.base_url}/api/drafts/{draft_id}/preview",
                headers={
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                },
                params={'_t': datetime.now().timestamp()}
            )
            
            if response2.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                
                # Check that the title was updated
                if data1.get("title") != data2.get("title"):
                    self.log_result("Preview fetches fresh data", True)
                    return True
                else:
                    self.log_result("Preview fetches fresh data", False, "Title not updated in preview")
            else:
                self.log_result("Preview fetches fresh data", False, f"Second request failed: {response2.status_code}")
                
        except Exception as e:
            self.log_result("Preview fetches fresh data", False, f"Exception: {str(e)}")
        
        return False

    def create_test_image(self, filename="test_image.jpg"):
        """Create a test image file"""
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        return img_bytes

    def test_create_batch(self):
        """Test creating a new batch"""
        print("\n📦 Testing Batch Creation...")
        
        if not self.token:
            self.log_result("POST /batches", False, "No token available")
            return False
            
        try:
            response = self.session.post(
                f"{self.base_url}/api/batches",
                json={"name": "Test Batch Upload"},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data:
                    self.batch_id = data["id"]
                    self.log_result("POST /batches", True)
                    return True
                else:
                    self.log_result("POST /batches", False, f"No ID in response: {data}")
            else:
                self.log_result("POST /batches", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("POST /batches", False, f"Exception: {str(e)}")
        
        return False

    def test_upload_batch_images(self):
        """Test uploading multiple images to batch"""
        print("\n📸 Testing Batch Image Upload...")
        
        if not self.token or not self.batch_id:
            self.log_result("POST /batches/{id}/upload", False, "No token or batch_id available")
            return False
            
        try:
            # Create test images
            files = []
            for i in range(3):
                img_data = self.create_test_image(f"test_{i}.jpg")
                files.append(('files', (f'test_{i}.jpg', img_data, 'image/jpeg')))

            # Remove Content-Type header for multipart upload
            headers = {"Authorization": f"Bearer {self.token}"}
            
            response = requests.post(
                f"{self.base_url}/api/batches/{self.batch_id}/upload",
                files=files,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if "uploaded" in data and len(data["uploaded"]) > 0:
                    self.log_result("POST /batches/{id}/upload", True)
                    return True
                else:
                    self.log_result("POST /batches/{id}/upload", False, f"No uploads in response: {data}")
            else:
                self.log_result("POST /batches/{id}/upload", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("POST /batches/{id}/upload", False, f"Exception: {str(e)}")
        
        return False

    def test_list_batches(self):
        """Test listing all batches"""
        print("\n📋 Testing List Batches...")
        
        if not self.token:
            self.log_result("GET /batches", False, "No token available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/batches")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result("GET /batches", True)
                    return True
                else:
                    self.log_result("GET /batches", False, f"Expected list, got: {type(data)}")
            else:
                self.log_result("GET /batches", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /batches", False, f"Exception: {str(e)}")
        
        return False

    def test_get_batch_details(self):
        """Test getting batch details"""
        print("\n🔍 Testing Get Batch Details...")
        
        if not self.token or not self.batch_id:
            self.log_result("GET /batches/{id}", False, "No token or batch_id available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/batches/{self.batch_id}")
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and "status" in data:
                    self.log_result("GET /batches/{id}", True)
                    return True
                else:
                    self.log_result("GET /batches/{id}", False, f"Missing required fields: {data}")
            else:
                self.log_result("GET /batches/{id}", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /batches/{id}", False, f"Exception: {str(e)}")
        
        return False

    def test_get_batch_images(self):
        """Test getting batch images"""
        print("\n🖼️ Testing Get Batch Images...")
        
        if not self.token or not self.batch_id:
            self.log_result("GET /batches/{id}/images", False, "No token or batch_id available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/batches/{self.batch_id}/images")
            
            if response.status_code == 200:
                data = response.json()
                if "images" in data and isinstance(data["images"], list):
                    self.log_result("GET /batches/{id}/images", True)
                    return True
                else:
                    self.log_result("GET /batches/{id}/images", False, f"Invalid response format: {data}")
            else:
                self.log_result("GET /batches/{id}/images", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /batches/{id}/images", False, f"Exception: {str(e)}")
        
        return False

    def test_auto_group_batch(self):
        """Test starting auto-grouping job"""
        print("\n🤖 Testing Auto-Group Batch...")
        
        if not self.token or not self.batch_id:
            self.log_result("POST /batches/{id}/auto_group", False, "No token or batch_id available")
            return False
            
        try:
            response = self.session.post(f"{self.base_url}/api/batches/{self.batch_id}/auto_group")
            
            if response.status_code == 200:
                data = response.json()
                if "job_id" in data:
                    self.job_id = data["job_id"]
                    self.log_result("POST /batches/{id}/auto_group", True)
                    return True
                else:
                    self.log_result("POST /batches/{id}/auto_group", False, f"No job_id in response: {data}")
            else:
                self.log_result("POST /batches/{id}/auto_group", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("POST /batches/{id}/auto_group", False, f"Exception: {str(e)}")
        
        return False

    def test_job_progress(self):
        """Test getting job progress"""
        print("\n⏳ Testing Job Progress...")
        
        if not self.token or not self.job_id:
            self.log_result("GET /jobs/{id}", False, "No token or job_id available")
            return False
            
        try:
            # Poll job status for up to 30 seconds
            for i in range(30):
                response = self.session.get(f"{self.base_url}/api/jobs/{self.job_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'UNKNOWN')
                    progress = data.get('progress', 0)
                    
                    if status == 'COMPLETED':
                        self.log_result("GET /jobs/{id}", True)
                        return True
                    elif status == 'ERROR':
                        self.log_result("GET /jobs/{id}", False, f"Job failed: {data.get('error', 'Unknown error')}")
                        return False
                    
                    # Continue polling
                    time.sleep(1)
                else:
                    self.log_result("GET /jobs/{id}", False, f"Status {response.status_code}: {response.text}")
                    return False
            
            self.log_result("GET /jobs/{id}", False, "Job did not complete within 30 seconds")
                
        except Exception as e:
            self.log_result("GET /jobs/{id}", False, f"Exception: {str(e)}")
        
        return False

    def test_get_batch_groups(self):
        """Test getting batch groups after auto-grouping"""
        print("\n👥 Testing Get Batch Groups...")
        
        if not self.token or not self.batch_id:
            self.log_result("GET /batches/{id}/groups", False, "No token or batch_id available")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/api/batches/{self.batch_id}/groups")
            
            if response.status_code == 200:
                data = response.json()
                if "groups" in data and isinstance(data["groups"], list):
                    groups = data["groups"]
                    if groups:
                        self.group_ids = [g['id'] for g in groups]
                    self.log_result("GET /batches/{id}/groups", True)
                    return True
                else:
                    self.log_result("GET /batches/{id}/groups", False, f"Invalid response format: {data}")
            else:
                self.log_result("GET /batches/{id}/groups", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("GET /batches/{id}/groups", False, f"Exception: {str(e)}")
        
        return False

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting SkateBay API Tests...")
        print(f"Testing against: {self.base_url}")
        
        # Authentication tests
        if not self.test_login():
            print("\n❌ Login failed - stopping tests")
            return False
            
        self.test_auth_me()
        
        # Core functionality tests
        self.test_stats()
        self.test_drafts_list()
        
        # Create and test draft
        draft_id = self.test_create_draft()
        if draft_id:
            self.test_get_draft(draft_id)
            
            # Title generation tests
            self.test_title_manually_edited_field(draft_id)
            self.test_patch_title_manually_edited(draft_id)
            self.test_title_no_unknown_values(draft_id)
            self.test_preview_cache_busting(draft_id)
            
            # LLM and preview tests
            self.test_llm_generation(draft_id)
            self.test_draft_preview(draft_id)
        
        # Batch Upload Tests
        print("\n" + "="*50)
        print("🔥 TESTING BATCH UPLOAD FEATURE")
        print("="*50)
        
        if self.test_create_batch():
            self.test_upload_batch_images()
            self.test_list_batches()
            self.test_get_batch_details()
            self.test_get_batch_images()
            
            # Auto-grouping workflow
            if self.test_auto_group_batch():
                self.test_job_progress()
                self.test_get_batch_groups()
        
        # Settings tests
        self.test_settings()
        self.test_ebay_status()
        
        # Print summary
        print(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"  - {failure['test']}: {failure['details']}")
        
        return len(self.failed_tests) == 0

def main():
    tester = SkateBAYAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())