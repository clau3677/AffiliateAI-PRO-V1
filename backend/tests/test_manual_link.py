"""
Hotmart Super Agent - Module 2 Manual Link API Tests
Tests for PATCH/DELETE /api/products/{country_code}/{hotmart_id}/manual-link endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestManualLinkSave:
    """PATCH /api/products/{country_code}/{hotmart_id}/manual-link endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_product(self):
        """Ensure we have a product to test with by running matching for AR"""
        # Check if AR has products
        response = requests.get(f"{BASE_URL}/api/products/AR")
        if response.status_code == 200 and len(response.json()) > 0:
            self.product = response.json()[0]
            return
        
        # Run matching for AR if no products
        match_response = requests.post(
            f"{BASE_URL}/api/products/match",
            json={"country_code": "AR", "limit": 5}
        )
        if match_response.status_code == 200:
            execution_id = match_response.json()["execution_id"]
            # Wait for completion
            max_wait = 90
            elapsed = 0
            while elapsed < max_wait:
                exec_response = requests.get(f"{BASE_URL}/api/products/executions/{execution_id}")
                if exec_response.json().get("status") in ["completed", "failed"]:
                    break
                time.sleep(5)
                elapsed += 5
        
        # Get products again
        response = requests.get(f"{BASE_URL}/api/products/AR")
        if response.status_code == 200 and len(response.json()) > 0:
            self.product = response.json()[0]
        else:
            self.product = None
    
    def test_save_manual_link_success(self):
        """PATCH /api/products/AR/{hotmart_id}/manual-link with valid link → 200 saved"""
        if not self.product:
            pytest.skip("No product available for testing")
        
        hotmart_id = self.product["hotmart_id"]
        test_link = "https://go.hotmart.com/TEST123456"
        
        response = requests.patch(
            f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link",
            json={"affiliate_link": test_link}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "saved"
        assert "affiliate_link" in data
        assert data["affiliate_link"] == test_link
    
    def test_save_manual_link_updates_product(self):
        """After PATCH, GET /api/products/AR shows affiliate_status:manual and the saved link"""
        if not self.product:
            pytest.skip("No product available for testing")
        
        hotmart_id = self.product["hotmart_id"]
        test_link = "https://go.hotmart.com/VERIFY123"
        
        # Save the link
        patch_response = requests.patch(
            f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link",
            json={"affiliate_link": test_link}
        )
        assert patch_response.status_code == 200
        
        # Verify via GET
        get_response = requests.get(f"{BASE_URL}/api/products/AR")
        assert get_response.status_code == 200
        
        products = get_response.json()
        product = next((p for p in products if p["hotmart_id"] == hotmart_id), None)
        assert product is not None
        assert product["affiliate_link"] == test_link
        assert product["affiliate_status"] == "manual"
    
    def test_save_manual_link_invalid_link_no_hotmart(self):
        """PATCH with link not containing 'hotmart.com' → 400"""
        if not self.product:
            pytest.skip("No product available for testing")
        
        hotmart_id = self.product["hotmart_id"]
        invalid_link = "https://example.com/some-link"
        
        response = requests.patch(
            f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link",
            json={"affiliate_link": invalid_link}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        # Should mention hotmart.com requirement
        assert "hotmart.com" in data["detail"].lower()
    
    def test_save_manual_link_empty_link(self):
        """PATCH with empty affiliate_link → 400"""
        if not self.product:
            pytest.skip("No product available for testing")
        
        hotmart_id = self.product["hotmart_id"]
        
        response = requests.patch(
            f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link",
            json={"affiliate_link": ""}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
    
    def test_save_manual_link_whitespace_only(self):
        """PATCH with whitespace-only affiliate_link → 400"""
        if not self.product:
            pytest.skip("No product available for testing")
        
        hotmart_id = self.product["hotmart_id"]
        
        response = requests.patch(
            f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link",
            json={"affiliate_link": "   "}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
    
    def test_save_manual_link_product_not_found(self):
        """PATCH with non-existent product → 404"""
        response = requests.patch(
            f"{BASE_URL}/api/products/AR/nonexistent-product-xyz/manual-link",
            json={"affiliate_link": "https://go.hotmart.com/TEST"}
        )
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data


class TestManualLinkClear:
    """DELETE /api/products/{country_code}/{hotmart_id}/manual-link endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_product_with_link(self):
        """Ensure we have a product with a saved link to test clearing"""
        # Get products for AR
        response = requests.get(f"{BASE_URL}/api/products/AR")
        if response.status_code != 200 or len(response.json()) == 0:
            pytest.skip("No products available for AR")
        
        self.product = response.json()[0]
        hotmart_id = self.product["hotmart_id"]
        
        # Save a link first
        requests.patch(
            f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link",
            json={"affiliate_link": "https://go.hotmart.com/TOCLEAR123"}
        )
    
    def test_clear_manual_link_success(self):
        """DELETE /api/products/AR/{hotmart_id}/manual-link → clears link, returns status:cleared"""
        hotmart_id = self.product["hotmart_id"]
        
        response = requests.delete(f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "cleared"
    
    def test_clear_manual_link_resets_status(self):
        """After DELETE, GET shows affiliate_status:pending and affiliate_link:null"""
        hotmart_id = self.product["hotmart_id"]
        
        # First save a link
        requests.patch(
            f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link",
            json={"affiliate_link": "https://go.hotmart.com/TOVERIFY456"}
        )
        
        # Clear it
        delete_response = requests.delete(f"{BASE_URL}/api/products/AR/{hotmart_id}/manual-link")
        assert delete_response.status_code == 200
        
        # Verify via GET
        get_response = requests.get(f"{BASE_URL}/api/products/AR")
        assert get_response.status_code == 200
        
        products = get_response.json()
        product = next((p for p in products if p["hotmart_id"] == hotmart_id), None)
        assert product is not None
        assert product["affiliate_link"] is None
        assert product["affiliate_status"] == "pending"
    
    def test_clear_manual_link_product_not_found(self):
        """DELETE with non-existent product → 404"""
        response = requests.delete(f"{BASE_URL}/api/products/AR/nonexistent-product-xyz/manual-link")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data


class TestHotmartTestConnection:
    """POST /api/hotmart/test-connection endpoint tests"""
    
    def test_hotmart_test_connection_responds(self):
        """POST /api/hotmart/test-connection → responds with oauth status (oauth_ok_scopes_missing expected)"""
        response = requests.post(f"{BASE_URL}/api/hotmart/test-connection")
        assert response.status_code == 200
        
        data = response.json()
        # Should have status field
        assert "status" in data
        # With our creds that don't have scopes, expect oauth_ok_scopes_missing or similar
        # The status could be: oauth_ok_scopes_missing, oauth_failed, credentials_missing, etc.
        assert data["status"] in ["oauth_ok_scopes_missing", "oauth_failed", "credentials_missing", "oauth_ok", "error"]


class TestExistingEndpointsStillWork:
    """Verify existing Module 2 endpoints still work after manual-link additions"""
    
    def test_hotmart_status_still_works(self):
        """GET /api/hotmart/status → still returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/hotmart/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "credentials_configured" in data
        assert "module" in data
        assert "scraper" in data
        assert "llm_fallback" in data
    
    def test_products_match_still_works(self):
        """POST /api/products/match → still starts execution"""
        response = requests.post(
            f"{BASE_URL}/api/products/match",
            json={"country_code": "CO", "limit": 3}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert data["status"] == "started"
    
    def test_products_executions_still_works(self):
        """GET /api/products/executions/{id} → still tracks status"""
        # Start a matching
        match_response = requests.post(
            f"{BASE_URL}/api/products/match",
            json={"country_code": "PE", "limit": 2}
        )
        if match_response.status_code != 200:
            pytest.skip("Could not start matching")
        
        execution_id = match_response.json()["execution_id"]
        
        response = requests.get(f"{BASE_URL}/api/products/executions/{execution_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert "status" in data
        assert "_id" not in data
    
    def test_get_products_still_works(self):
        """GET /api/products/{country_code} → still returns products"""
        response = requests.get(f"{BASE_URL}/api/products/AR")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "_id" not in data[0]
            assert "hotmart_id" in data[0]
