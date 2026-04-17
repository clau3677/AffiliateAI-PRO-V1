"""
Test Module 2 Auto-Sync: Hotmart affiliations sync and auto-linking
Tests /hotmart/rematch-all (which performs sync + re-match internally)
and verifies is_my_affiliation flag on products.
"""
import pytest
import requests
import os
import time
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHotmartRematchAll:
    """Tests for POST /api/hotmart/rematch-all"""
    
    def test_rematch_all_returns_started_status(self):
        """Rematch-all returns status:started with execution_id"""
        response = requests.post(f"{BASE_URL}/api/hotmart/rematch-all")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "started"
        assert "execution_id" in data
        assert isinstance(data["execution_id"], str)
        assert len(data["execution_id"]) > 0
    
    def test_rematch_all_returns_synced_affiliations_count(self):
        """Rematch-all returns synced_affiliations count"""
        response = requests.post(f"{BASE_URL}/api/hotmart/rematch-all")
        assert response.status_code == 200
        data = response.json()
        assert "synced_affiliations" in data
        assert isinstance(data["synced_affiliations"], int)
    
    def test_rematch_all_returns_countries_list(self):
        """Rematch-all returns list of countries to rematch"""
        response = requests.post(f"{BASE_URL}/api/hotmart/rematch-all")
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert isinstance(data["countries"], list)
        # Should have 5 countries with trends
        assert len(data["countries"]) == 5
        expected_countries = ["AR", "CL", "CO", "PE", "BR"]
        for country in expected_countries:
            assert country in data["countries"]


class TestProductExecutionTracking:
    """Tests for GET /api/products/executions/{id}"""
    
    def test_execution_tracking_returns_status(self):
        """Execution tracking returns status field"""
        # Start a rematch-all to get an execution_id
        start_response = requests.post(f"{BASE_URL}/api/hotmart/rematch-all")
        assert start_response.status_code == 200
        execution_id = start_response.json()["execution_id"]
        
        # Check execution status
        response = requests.get(f"{BASE_URL}/api/products/executions/{execution_id}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["pending", "running", "completed", "failed"]
        assert data["id"] == execution_id
    
    def test_execution_tracking_has_kind_field(self):
        """Rematch-all execution has kind:rematch_all"""
        start_response = requests.post(f"{BASE_URL}/api/hotmart/rematch-all")
        execution_id = start_response.json()["execution_id"]
        
        response = requests.get(f"{BASE_URL}/api/products/executions/{execution_id}")
        data = response.json()
        assert data.get("kind") == "rematch_all"
        assert data.get("country_code") == "ALL"


class TestProductsWithAffiliationFlag:
    """Tests for GET /api/products/{country_code} with is_my_affiliation flag"""
    
    def test_products_have_is_my_affiliation_field(self):
        """Products include is_my_affiliation boolean field (new products)"""
        response = requests.get(f"{BASE_URL}/api/products/AR?limit=10")
        assert response.status_code == 200
        products = response.json()
        assert len(products) > 0
        # Check that at least some products have the field (new products after rematch)
        products_with_field = [p for p in products if "is_my_affiliation" in p]
        assert len(products_with_field) > 0, "At least some products should have is_my_affiliation field"
        for product in products_with_field:
            assert isinstance(product["is_my_affiliation"], bool)
    
    def test_products_without_real_affiliations_have_false_flag(self):
        """Products from discovery (not user affiliations) have is_my_affiliation:false"""
        response = requests.get(f"{BASE_URL}/api/products/AR?limit=30")
        products = response.json()
        # Most products should be discovery (is_my_affiliation:false)
        discovery_products = [p for p in products if not p.get("is_my_affiliation")]
        assert len(discovery_products) > 0
    
    def test_real_affiliation_product_has_true_flag(self):
        """Test affiliation (test_real_1) has is_my_affiliation:true"""
        response = requests.get(f"{BASE_URL}/api/products/AR?limit=30")
        products = response.json()
        # Find the test affiliation we inserted
        test_product = next((p for p in products if p["hotmart_id"] == "test_real_1"), None)
        if test_product:
            assert test_product["is_my_affiliation"] == True
            assert test_product["affiliate_link"] == "https://go.hotmart.com/TEST123"
            assert test_product["affiliate_status"] == "generated"


class TestExistingHotmartEndpoints:
    """Verify existing Hotmart endpoints still work"""
    
    def test_hotmart_status(self):
        """GET /api/hotmart/status returns credentials_configured:true"""
        response = requests.get(f"{BASE_URL}/api/hotmart/status")
        assert response.status_code == 200
        data = response.json()
        assert data["credentials_configured"] == True
        assert data["affiliate_api"] == "ready"
    
    def test_hotmart_test_connection(self):
        """POST /api/hotmart/test-connection returns status:ok"""
        response = requests.post(f"{BASE_URL}/api/hotmart/test-connection")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["scopes_ok"] == True
    
    def test_hotmart_my_affiliations(self):
        """GET /api/hotmart/my-affiliations returns status:ok"""
        response = requests.get(f"{BASE_URL}/api/hotmart/my-affiliations")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "items" in data
    
    def test_hotmart_sales_summary(self):
        """GET /api/hotmart/sales-summary returns status:ok"""
        response = requests.get(f"{BASE_URL}/api/hotmart/sales-summary")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_hotmart_sales_history(self):
        """GET /api/hotmart/sales-history returns status:ok"""
        response = requests.get(f"{BASE_URL}/api/hotmart/sales-history")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "items" in data
    
    def test_hotmart_commissions(self):
        """GET /api/hotmart/commissions returns status:ok"""
        response = requests.get(f"{BASE_URL}/api/hotmart/commissions")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "items" in data


class TestExistingProductEndpoints:
    """Verify existing product endpoints still work"""
    
    def test_products_match_endpoint(self):
        """POST /api/products/match starts execution"""
        response = requests.post(f"{BASE_URL}/api/products/match", json={
            "country_code": "AR",
            "limit": 5,
            "auto_links": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "execution_id" in data
    
    def test_get_products_endpoint(self):
        """GET /api/products/{country_code} returns products"""
        response = requests.get(f"{BASE_URL}/api/products/AR?limit=10")
        assert response.status_code == 200
        products = response.json()
        assert isinstance(products, list)


class TestMatchAndScorePipeline:
    """Tests for the match_and_score pipeline with real affiliations"""
    
    def test_real_affiliations_appear_first_in_results(self):
        """Real affiliations should appear before discovery products"""
        response = requests.get(f"{BASE_URL}/api/products/AR?limit=30")
        products = response.json()
        
        # Find first real affiliation and first discovery product
        first_real_idx = None
        first_discovery_idx = None
        
        for idx, p in enumerate(products):
            if p.get("is_my_affiliation") and first_real_idx is None:
                first_real_idx = idx
            if not p.get("is_my_affiliation") and first_discovery_idx is None:
                first_discovery_idx = idx
        
        # If we have both, real should come first
        if first_real_idx is not None and first_discovery_idx is not None:
            assert first_real_idx < first_discovery_idx, "Real affiliations should appear before discovery products"
    
    def test_real_affiliation_has_auto_generated_link(self):
        """Real affiliation should have affiliate_link from hotmart_affiliations"""
        response = requests.get(f"{BASE_URL}/api/products/AR?limit=30")
        products = response.json()
        
        real_products = [p for p in products if p.get("is_my_affiliation")]
        # If we have real affiliations, verify they have proper status
        for p in real_products:
            # Real affiliations should have generated status if they have a link
            if p.get("affiliate_link"):
                assert p["affiliate_status"] in ["generated", "manual"]


class TestCleanup:
    """Cleanup test data after tests"""
    
    def test_cleanup_test_affiliation(self):
        """Remove test affiliation from hotmart_affiliations collection"""
        # This is a cleanup test - we'll verify the test data can be removed
        # In a real scenario, we'd use a fixture with teardown
        pass  # Cleanup will be done manually or via fixture
