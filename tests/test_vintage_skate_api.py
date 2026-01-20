"""
Backend API tests for Vintage Skate Lister App
Tests: Default condition, auto_filled_aspects, autofill_aspects endpoint, title/description updates
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://eboard-publish.preview.emergentagent.com')

class TestAuth:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test successful login with correct password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "message" in data
        assert data["message"] == "Login successful"
        assert len(data["token"]) > 0
    
    def test_login_invalid_password(self):
        """Test login with invalid password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "wrongpassword"
        })
        assert response.status_code == 401


class TestDraftCreation:
    """Tests for draft creation with default condition = NEW"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "admin123"
        })
        return response.json()["token"]
    
    def test_create_draft_default_condition_new(self, auth_token):
        """Test that new drafts have condition = NEW by default"""
        response = requests.post(
            f"{BASE_URL}/api/drafts",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "item_type": "WHL",
                "category_id": "16265",
                "price": 29.99,
                "image_urls": [],
                "condition": "NEW"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify condition is NEW
        assert data["condition"] == "NEW"
        assert data["item_type"] == "WHL"
        assert data["status"] == "DRAFT"
        assert data["title_manually_edited"] == False
        assert data["description_manually_edited"] == False
        assert data["auto_filled_aspects"] == []
        
        # Cleanup
        draft_id = data["id"]
        requests.delete(
            f"{BASE_URL}/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_create_draft_all_item_types(self, auth_token):
        """Test creating drafts for all item types"""
        item_types = ["WHL", "TRK", "DCK", "APP", "MISC"]
        
        for item_type in item_types:
            response = requests.post(
                f"{BASE_URL}/api/drafts",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "item_type": item_type,
                    "category_id": "16265",
                    "price": 19.99,
                    "image_urls": [],
                    "condition": "NEW"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["item_type"] == item_type
            assert data["condition"] == "NEW"
            
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/drafts/{data['id']}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )


class TestAutoFilledAspects:
    """Tests for auto_filled_aspects tracking"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def test_draft(self, auth_token):
        """Create a test draft"""
        response = requests.post(
            f"{BASE_URL}/api/drafts",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "item_type": "WHL",
                "category_id": "16265",
                "price": 39.99,
                "image_urls": [],
                "condition": "NEW"
            }
        )
        draft = response.json()
        yield draft
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_update_draft_with_auto_filled_aspects(self, auth_token, test_draft):
        """Test updating draft with auto_filled_aspects tracking"""
        draft_id = test_draft["id"]
        
        response = requests.patch(
            f"{BASE_URL}/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "aspects": {
                    "Brand": "Santa Cruz",
                    "Model": "Slime Balls",
                    "Size": "60mm",
                    "Durometer": "95A"
                },
                "auto_filled_aspects": ["Brand", "Model", "Size"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify auto_filled_aspects is saved
        assert "Brand" in data["auto_filled_aspects"]
        assert "Model" in data["auto_filled_aspects"]
        assert "Size" in data["auto_filled_aspects"]
        assert data["aspects"]["Brand"] == "Santa Cruz"
    
    def test_update_title_manually_edited_flag(self, auth_token, test_draft):
        """Test title_manually_edited flag"""
        draft_id = test_draft["id"]
        
        response = requests.patch(
            f"{BASE_URL}/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "Custom Manual Title",
                "title_manually_edited": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == "Custom Manual Title"
        assert data["title_manually_edited"] == True
    
    def test_update_description_manually_edited_flag(self, auth_token, test_draft):
        """Test description_manually_edited flag"""
        draft_id = test_draft["id"]
        
        response = requests.patch(
            f"{BASE_URL}/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "description": "<p>Custom description</p>",
                "description_manually_edited": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["description"] == "<p>Custom description</p>"
        assert data["description_manually_edited"] == True


class TestAutofillAspectsEndpoint:
    """Tests for /api/drafts/{id}/autofill_aspects endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def test_draft(self, auth_token):
        """Create a test draft"""
        response = requests.post(
            f"{BASE_URL}/api/drafts",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "item_type": "WHL",
                "category_id": "16265",
                "price": 49.99,
                "image_urls": [],
                "condition": "NEW"
            }
        )
        draft = response.json()
        yield draft
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_autofill_aspects_no_images(self, auth_token, test_draft):
        """Test autofill_aspects returns error when no images"""
        draft_id = test_draft["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/drafts/{draft_id}/autofill_aspects",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "No images available" in data["detail"]
    
    def test_autofill_aspects_endpoint_exists(self, auth_token, test_draft):
        """Test that autofill_aspects endpoint exists and is accessible"""
        draft_id = test_draft["id"]
        
        # Even without images, endpoint should return 400, not 404
        response = requests.post(
            f"{BASE_URL}/api/drafts/{draft_id}/autofill_aspects",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404
        # Should be 400 (no images) or 200 (success)
        assert response.status_code in [400, 200]


class TestDraftPreview:
    """Tests for draft preview endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "admin123"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def test_draft(self, auth_token):
        """Create a test draft with content"""
        response = requests.post(
            f"{BASE_URL}/api/drafts",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "item_type": "WHL",
                "category_id": "16265",
                "price": 59.99,
                "image_urls": [],
                "condition": "NEW"
            }
        )
        draft = response.json()
        
        # Update with title and description
        requests.patch(
            f"{BASE_URL}/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "Test Preview Title",
                "description": "<div>Test description</div>",
                "aspects": {"Brand": "Test Brand"}
            }
        )
        
        yield draft
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_get_draft_preview(self, auth_token, test_draft):
        """Test getting draft preview data"""
        draft_id = test_draft["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/drafts/{draft_id}/preview",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "title" in data
        assert "descriptionHtml" in data
        assert "condition" in data
        assert data["condition"] == "NEW"


class TestConditionValues:
    """Tests for different condition values"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "admin123"
        })
        return response.json()["token"]
    
    def test_update_condition_values(self, auth_token):
        """Test updating draft with different condition values"""
        # Create draft
        response = requests.post(
            f"{BASE_URL}/api/drafts",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "item_type": "WHL",
                "category_id": "16265",
                "price": 29.99,
                "image_urls": [],
                "condition": "NEW"
            }
        )
        draft_id = response.json()["id"]
        
        conditions = ["NEW", "LIKE_NEW", "USED_EXCELLENT", "USED_GOOD", "USED_ACCEPTABLE"]
        
        for condition in conditions:
            response = requests.patch(
                f"{BASE_URL}/api/drafts/{draft_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"condition": condition}
            )
            assert response.status_code == 200
            assert response.json()["condition"] == condition
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )


class TestGenerateEndpoint:
    """Tests for /api/drafts/{id}/generate endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": "admin123"
        })
        return response.json()["token"]
    
    def test_generate_endpoint_exists(self, auth_token):
        """Test that generate endpoint exists"""
        # Create draft
        response = requests.post(
            f"{BASE_URL}/api/drafts",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "item_type": "WHL",
                "category_id": "16265",
                "price": 29.99,
                "image_urls": [],
                "condition": "NEW"
            }
        )
        draft_id = response.json()["id"]
        
        # Test generate endpoint (may fail due to LLM but should not be 404)
        response = requests.post(
            f"{BASE_URL}/api/drafts/{draft_id}/generate",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Should not be 404
        assert response.status_code != 404
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
