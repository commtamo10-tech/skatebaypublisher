"""
Test suite for republish_draft Content-Language header fix
Tests that the republish endpoint uses correct Content-Language headers for each marketplace

Bug context: The 'Ripubblica' (republish) function was only updating ebay.com listings
because the Content-Language header was missing for EU/AU marketplaces.
"""

import pytest
import requests
import os
import sys

# Add backend to path for importing config
sys.path.insert(0, '/app/backend')
from ebay_config import MARKETPLACE_CONFIG

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_PASSWORD = "admin123"


class TestMarketplaceConfig:
    """Test that MARKETPLACE_CONFIG has correct language mappings"""
    
    def test_marketplace_config_has_language_key(self):
        """Verify MARKETPLACE_CONFIG uses 'language' key (not 'content_language')"""
        expected_languages = {
            "EBAY_US": "en-US",
            "EBAY_DE": "de-DE",
            "EBAY_ES": "es-ES",
            "EBAY_AU": "en-AU"
        }
        
        for mp_id, expected_lang in expected_languages.items():
            config = MARKETPLACE_CONFIG.get(mp_id, {})
            assert "language" in config, f"MARKETPLACE_CONFIG[{mp_id}] missing 'language' key"
            assert config["language"] == expected_lang, f"MARKETPLACE_CONFIG[{mp_id}]['language'] should be {expected_lang}, got {config.get('language')}"
            print(f"✅ {mp_id}: language = {config['language']}")
    
    def test_marketplace_config_no_content_language_key(self):
        """Verify MARKETPLACE_CONFIG does NOT have 'content_language' key (it uses 'language')"""
        for mp_id, config in MARKETPLACE_CONFIG.items():
            # The key should be 'language', not 'content_language'
            assert "content_language" not in config, f"MARKETPLACE_CONFIG[{mp_id}] should use 'language' not 'content_language'"
            print(f"✅ {mp_id}: correctly uses 'language' key")


class TestRepublishCodeReview:
    """Code review tests to verify the fix is correctly implemented"""
    
    def test_republish_uses_correct_language_key(self):
        """
        CRITICAL: Verify republish_draft uses mp_config.get('language', ...) 
        NOT mp_config.get('content_language', ...)
        
        Bug: Line 1688 was using 'content_language' which doesn't exist in MARKETPLACE_CONFIG,
        causing all marketplaces to fall back to 'en-US'
        """
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find the republish_draft function
        republish_start = content.find('async def republish_draft')
        assert republish_start != -1, "republish_draft function not found"
        
        # Find the next function definition to get the end of republish_draft
        next_func = content.find('\nasync def ', republish_start + 1)
        if next_func == -1:
            next_func = content.find('\n@api_router', republish_start + 1)
        
        republish_code = content[republish_start:next_func]
        
        # Check for the bug: using 'content_language' instead of 'language'
        if 'mp_config.get("content_language"' in republish_code or "mp_config.get('content_language'" in republish_code:
            pytest.fail(
                "BUG FOUND: republish_draft uses mp_config.get('content_language', ...) "
                "but MARKETPLACE_CONFIG uses 'language' key. "
                "This causes all marketplaces to fall back to 'en-US'. "
                "Fix: Change to mp_config.get('language', 'en-US')"
            )
        
        # Verify the correct key is used
        assert 'mp_config.get("language"' in republish_code or "mp_config.get('language'" in republish_code, \
            "republish_draft should use mp_config.get('language', ...) to get Content-Language"
        
        print("✅ republish_draft correctly uses mp_config.get('language', ...)")
    
    def test_republish_has_content_language_in_publish_headers(self):
        """Verify Content-Language header is included in publishOffer call"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find the republish_draft function
        republish_start = content.find('async def republish_draft')
        next_func = content.find('\nasync def ', republish_start + 1)
        if next_func == -1:
            next_func = content.find('\n@api_router', republish_start + 1)
        
        republish_code = content[republish_start:next_func]
        
        # Check that Content-Language is in publish_headers
        assert '"Content-Language"' in republish_code or "'Content-Language'" in republish_code, \
            "republish_draft should include Content-Language header"
        
        # Check for the publish_headers dict with Content-Language
        assert 'publish_headers' in republish_code, "republish_draft should have publish_headers dict"
        
        print("✅ republish_draft includes Content-Language in publish headers")


class TestAPIEndpoints:
    """Test API endpoints are accessible"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": TEST_PASSWORD}
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        self.session.close()
    
    def test_health_endpoint(self):
        """Verify API is running"""
        resp = self.session.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        print("✅ API health check passed")
    
    def test_auth_login(self):
        """Verify authentication works"""
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": TEST_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 200, f"Login failed: {resp.status_code}"
        data = resp.json()
        assert "token" in data, "Login response should contain token"
        print("✅ Authentication working")
    
    def test_drafts_list(self):
        """Verify drafts endpoint is accessible"""
        resp = self.session.get(f"{BASE_URL}/api/drafts")
        assert resp.status_code == 200, f"Drafts list failed: {resp.status_code}"
        print(f"✅ Drafts endpoint accessible, found {len(resp.json())} drafts")
    
    def test_republish_endpoint_exists(self):
        """Verify republish endpoint exists (will return 404 for non-existent draft)"""
        # Use a fake draft ID - we expect 404 (not found) not 405 (method not allowed)
        resp = self.session.post(f"{BASE_URL}/api/drafts/fake-draft-id/republish")
        # 404 means endpoint exists but draft not found
        # 405 would mean endpoint doesn't exist
        assert resp.status_code in [404, 400, 401], \
            f"Republish endpoint should exist. Got: {resp.status_code}"
        print(f"✅ Republish endpoint exists (returned {resp.status_code} for fake draft)")


class TestRepublishWithPublishedDraft:
    """Test republish functionality with actual published drafts (if any exist)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"password": TEST_PASSWORD}
        )
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        self.session.close()
    
    def test_find_published_drafts(self):
        """Find any published drafts that could be used for republish testing"""
        resp = self.session.get(f"{BASE_URL}/api/drafts?status=PUBLISHED")
        assert resp.status_code == 200
        
        drafts = resp.json()
        published_count = len(drafts)
        
        if published_count == 0:
            print("ℹ️ No published drafts found - republish testing requires published drafts")
            pytest.skip("No published drafts available for testing")
        
        print(f"✅ Found {published_count} published draft(s)")
        
        # Check if any have marketplace_listings
        for draft in drafts[:3]:  # Check first 3
            mp_listings = draft.get("marketplace_listings", {})
            if mp_listings:
                print(f"  Draft {draft['id'][:8]}... has marketplaces: {list(mp_listings.keys())}")
    
    def test_republish_requires_published_status(self):
        """Verify republish returns error for non-published drafts"""
        # Get any draft
        resp = self.session.get(f"{BASE_URL}/api/drafts")
        drafts = resp.json()
        
        # Find a non-published draft
        non_published = [d for d in drafts if d.get("status") != "PUBLISHED"]
        
        if not non_published:
            pytest.skip("All drafts are published - cannot test non-published error")
        
        draft_id = non_published[0]["id"]
        resp = self.session.post(f"{BASE_URL}/api/drafts/{draft_id}/republish")
        
        # Should return 400 because draft is not published
        assert resp.status_code == 400, f"Expected 400 for non-published draft, got {resp.status_code}"
        assert "not published" in resp.json().get("detail", "").lower()
        print(f"✅ Republish correctly rejects non-published drafts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
