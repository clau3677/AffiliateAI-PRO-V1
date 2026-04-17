"""
Hotmart Super Agent - Module 2 API Tests
Tests for Hotmart product matching endpoints: status, match, executions, products, affiliate-link, delete
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHotmartStatus:
    """GET /api/hotmart/status endpoint tests"""
    
    def test_hotmart_status_returns_credentials_configured(self):
        """GET /api/hotmart/status → returns credentials_configured:true (creds loaded), scraper:enabled, llm_fallback:enabled"""
        response = requests.get(f"{BASE_URL}/api/hotmart/status")
        assert response.status_code == 200

        data = response.json()
        assert "credentials_configured" in data
        assert data["credentials_configured"] is True
        assert "scraper" in data
        assert data["scraper"] == "enabled"
        assert "llm_fallback" in data
        assert data["llm_fallback"] == "enabled"
        assert "module" in data
        assert "affiliate_api" in data
        assert data["affiliate_api"] == "ready"


class TestProductsMatch:
    """POST /api/products/match endpoint tests"""
    
    def test_match_products_starts_execution(self):
        """POST /api/products/match {country_code:CL, limit:5} → returns execution_id, status:started"""
        response = requests.post(
            f"{BASE_URL}/api/products/match",
            json={"country_code": "CL", "limit": 5}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert data["status"] == "started"
        assert "country_code" in data
        assert data["country_code"] == "CL"
        
        # Store execution_id for next test
        TestProductsMatch.execution_id = data["execution_id"]
    
    def test_match_products_invalid_country(self):
        """POST /api/products/match with invalid country XX → 400"""
        response = requests.post(
            f"{BASE_URL}/api/products/match",
            json={"country_code": "XX", "limit": 5}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
    
    def test_match_products_country_without_trends(self):
        """POST /api/products/match for country without trends → 409 with message to run research first"""
        # First delete trends for PE
        delete_response = requests.delete(f"{BASE_URL}/api/research/trends/PE")
        assert delete_response.status_code == 200
        
        # Now try to match products for PE (should fail with 409)
        response = requests.post(
            f"{BASE_URL}/api/products/match",
            json={"country_code": "PE", "limit": 5}
        )
        assert response.status_code == 409
        
        data = response.json()
        assert "detail" in data
        # Message should indicate to run research first
        assert "tendencias" in data["detail"].lower() or "research" in data["detail"].lower()


class TestProductExecutions:
    """GET /api/products/executions/{id} endpoint tests"""
    
    def test_get_execution_tracks_status(self):
        """GET /api/products/executions/{id} → track status until completed, products_found > 0"""
        execution_id = getattr(TestProductsMatch, 'execution_id', None)
        if not execution_id:
            pytest.skip("No execution_id from previous test")
        
        # Poll for completion (max 90 seconds - matching takes 15-60s)
        max_wait = 90
        poll_interval = 5
        elapsed = 0
        final_status = None
        products_found = 0
        
        while elapsed < max_wait:
            response = requests.get(f"{BASE_URL}/api/products/executions/{execution_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "id" in data
            assert "status" in data
            assert "_id" not in data  # No MongoDB _id
            
            final_status = data["status"]
            products_found = data.get("products_found", 0)
            
            if final_status in ["completed", "failed"]:
                break
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        assert final_status == "completed", f"Execution did not complete in {max_wait}s, status: {final_status}"
        assert products_found > 0, f"Expected products_found > 0, got {products_found}"
    
    def test_get_execution_not_found(self):
        """GET /api/products/executions/{invalid_id} → 404"""
        response = requests.get(f"{BASE_URL}/api/products/executions/nonexistent-id-12345")
        assert response.status_code == 404


class TestGetProducts:
    """GET /api/products/{country_code} endpoint tests"""
    
    def test_get_products_returns_scored_products(self):
        """GET /api/products/CL → returns array of scored products with required fields"""
        response = requests.get(f"{BASE_URL}/api/products/CL")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            product = data[0]
            # Required fields
            assert "hotmart_id" in product
            assert "title" in product
            assert "category" in product
            assert "commission_percent" in product
            assert "rating" in product
            assert "relevance_score" in product
            assert "profitability_score" in product
            assert "matched_pain_points" in product
            assert isinstance(product["matched_pain_points"], list)
            assert "affiliate_status" in product
            # affiliate_status should be credentials_missing or synthetic_product (no creds in .env)
            assert product["affiliate_status"] in ["credentials_missing", "synthetic_product", "pending"]
            assert "country_code" in product
            assert product["country_code"] == "CL"
            # No MongoDB _id
            assert "_id" not in product
    
    def test_get_products_invalid_country(self):
        """GET /api/products/XX (invalid country) → 400"""
        response = requests.get(f"{BASE_URL}/api/products/XX")
        assert response.status_code == 400


class TestAffiliateLink:
    """GET /api/products/{country_code}/{hotmart_id}/affiliate-link endpoint tests"""
    
    def test_affiliate_link_synthetic_product(self):
        """GET /api/products/CL/{hotmart_id}/affiliate-link → for synthetic/fallback products returns status:synthetic_product"""
        # First get products to find a synthetic one (ai_, det_, hm_ prefix)
        products_response = requests.get(f"{BASE_URL}/api/products/CL")
        assert products_response.status_code == 200
        
        products = products_response.json()
        if not products:
            pytest.skip("No products available for CL")
        
        # Find a synthetic product (is_fallback=True or hotmart_id starts with ai_, det_, hm_)
        synthetic_product = None
        for p in products:
            hid = str(p.get("hotmart_id", ""))
            if p.get("is_fallback") or hid.startswith(("ai_", "det_", "hm_")):
                synthetic_product = p
                break
        
        if not synthetic_product:
            pytest.skip("No synthetic products found in CL")
        
        hotmart_id = synthetic_product["hotmart_id"]
        response = requests.get(f"{BASE_URL}/api/products/CL/{hotmart_id}/affiliate-link")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "synthetic_product"
        assert "hotmart_id" in data
        assert data["hotmart_id"] == hotmart_id
    
    def test_affiliate_link_product_not_found(self):
        """GET /api/products/CL/nonexistent-product/affiliate-link → 404"""
        response = requests.get(f"{BASE_URL}/api/products/CL/nonexistent-product-12345/affiliate-link")
        assert response.status_code == 404


class TestDeleteProducts:
    """DELETE /api/products/{country_code} endpoint tests"""
    
    def test_delete_products_returns_count(self):
        """DELETE /api/products/CL → deletes products, returns count"""
        response = requests.delete(f"{BASE_URL}/api/products/CL")
        assert response.status_code == 200
        
        data = response.json()
        assert "deleted" in data
        assert isinstance(data["deleted"], int)
        assert "country_code" in data
        assert data["country_code"] == "CL"
    
    def test_delete_products_invalid_country(self):
        """DELETE /api/products/XX (invalid country) → 400"""
        response = requests.delete(f"{BASE_URL}/api/products/XX")
        assert response.status_code == 400


class TestNoMongoIdInModule2Responses:
    """Verify MongoDB _id is never exposed in Module 2 API responses"""
    
    def test_products_no_id(self):
        """Products endpoint should not include _id"""
        # First run matching for AR (which has trends)
        match_response = requests.post(
            f"{BASE_URL}/api/products/match",
            json={"country_code": "AR", "limit": 3}
        )
        assert match_response.status_code == 200
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
        
        # Now check products
        response = requests.get(f"{BASE_URL}/api/products/AR")
        data = response.json()
        for item in data:
            assert "_id" not in item
    
    def test_product_executions_no_id(self):
        """Product executions endpoint should not include _id"""
        execution_id = getattr(TestProductsMatch, 'execution_id', None)
        if not execution_id:
            pytest.skip("No execution_id available")
        
        response = requests.get(f"{BASE_URL}/api/products/executions/{execution_id}")
        data = response.json()
        assert "_id" not in data


class TestRestorePECountryTrends:
    """Restore PE country trends after test_match_products_country_without_trends"""
    
    def test_restore_pe_trends(self):
        """Run research for PE to restore trends deleted in earlier test"""
        response = requests.post(
            f"{BASE_URL}/api/research/run",
            json={"countries": ["PE"]}
        )
        assert response.status_code == 200
        
        execution_id = response.json()["execution_id"]
        
        # Wait for completion
        max_wait = 120
        elapsed = 0
        while elapsed < max_wait:
            exec_response = requests.get(f"{BASE_URL}/api/research/executions/{execution_id}")
            if exec_response.json().get("status") in ["completed", "failed"]:
                break
            time.sleep(5)
            elapsed += 5
        
        # Verify PE has trends again
        trends_response = requests.get(f"{BASE_URL}/api/research/trends/PE")
        assert trends_response.status_code == 200
        trends = trends_response.json()
        assert len(trends) > 0, "PE should have trends after restoration"
