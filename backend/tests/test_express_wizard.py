"""
Test Express Affiliation Wizard endpoint: GET /api/hotmart/express-wizard
Returns TOP opportunities by country with pre-filled Hotmart search URLs.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestExpressWizardBasic:
    """Basic tests for GET /api/hotmart/express-wizard"""
    
    def test_express_wizard_returns_ok_status(self):
        """Express wizard returns status:ok"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
    
    def test_express_wizard_returns_total_count(self):
        """Express wizard returns total count"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert isinstance(data["total"], int)
        assert data["total"] <= 10
    
    def test_express_wizard_returns_opportunities_list(self):
        """Express wizard returns opportunities array"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        assert response.status_code == 200
        data = response.json()
        assert "opportunities" in data
        assert isinstance(data["opportunities"], list)
    
    def test_express_wizard_returns_instructions(self):
        """Express wizard returns instructions string"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard")
        assert response.status_code == 200
        data = response.json()
        assert "instructions" in data
        assert isinstance(data["instructions"], str)
        assert len(data["instructions"]) > 0


class TestExpressWizardOpportunityStructure:
    """Tests for opportunity object structure"""
    
    def test_opportunity_has_required_fields(self):
        """Each opportunity has all required fields"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "country_code", "country_name", "keyword", "pain_point",
            "commercial_intent", "priority_score", "hotmart_search_url",
            "hotmart_discovery_url"
        ]
        
        for opp in data["opportunities"]:
            for field in required_fields:
                assert field in opp, f"Missing field: {field}"
    
    def test_opportunity_country_code_is_valid(self):
        """Country codes are from supported countries"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        data = response.json()
        
        valid_codes = {"AR", "CL", "CO", "PE", "BR"}
        for opp in data["opportunities"]:
            assert opp["country_code"] in valid_codes
    
    def test_opportunity_commercial_intent_is_valid(self):
        """Commercial intent is Alta or Media (Baja filtered out)"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        data = response.json()
        
        for opp in data["opportunities"]:
            assert opp["commercial_intent"] in ["Alta", "Media"]
    
    def test_opportunity_priority_score_is_number(self):
        """Priority score is a number between 0-100"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        data = response.json()
        
        for opp in data["opportunities"]:
            assert isinstance(opp["priority_score"], (int, float))
            assert 0 <= opp["priority_score"] <= 100


class TestExpressWizardURLFormatting:
    """Tests for Hotmart URL formatting"""
    
    def test_brazil_uses_pt_br_locale(self):
        """Brazil opportunities use 'pt-br' in discovery URL"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=3&max_total=15")
        data = response.json()
        
        br_opportunities = [o for o in data["opportunities"] if o["country_code"] == "BR"]
        for opp in br_opportunities:
            assert "pt-br" in opp["hotmart_discovery_url"], f"BR should use pt-br: {opp['hotmart_discovery_url']}"
    
    def test_spanish_countries_use_es_locale(self):
        """Spanish-speaking countries use 'es' in discovery URL"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=3&max_total=15")
        data = response.json()
        
        spanish_codes = {"AR", "CL", "CO", "PE"}
        spanish_opportunities = [o for o in data["opportunities"] if o["country_code"] in spanish_codes]
        
        for opp in spanish_opportunities:
            # Should contain /es/ but NOT /pt-br/
            assert "/es/" in opp["hotmart_discovery_url"], f"Spanish country should use /es/: {opp['hotmart_discovery_url']}"
            assert "/pt-br/" not in opp["hotmart_discovery_url"]
    
    def test_urls_contain_keyword_query(self):
        """URLs contain keyword as query parameter"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        data = response.json()
        
        for opp in data["opportunities"]:
            keyword_encoded = opp["keyword"].replace(" ", "+")
            assert f"q={keyword_encoded}" in opp["hotmart_search_url"]
            assert f"q={keyword_encoded}" in opp["hotmart_discovery_url"]
    
    def test_urls_are_valid_hotmart_marketplace(self):
        """URLs point to Hotmart marketplace"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        data = response.json()
        
        for opp in data["opportunities"]:
            assert "hotmart.com" in opp["hotmart_search_url"]
            assert "marketplace" in opp["hotmart_search_url"]
            assert "hotmart.com" in opp["hotmart_discovery_url"]
            assert "marketplace" in opp["hotmart_discovery_url"]


class TestExpressWizardPagination:
    """Tests for per_country and max_total parameters"""
    
    def test_per_country_2_max_total_10(self):
        """per_country=2, max_total=10 returns up to 10 opportunities"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] <= 10
        assert len(data["opportunities"]) <= 10
    
    def test_per_country_3_max_total_15(self):
        """per_country=3, max_total=15 returns up to 15 opportunities"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=3&max_total=15")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] <= 15
        assert len(data["opportunities"]) <= 15
    
    def test_default_parameters(self):
        """Default parameters work (per_country=2, max_total=10)"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard")
        assert response.status_code == 200
        data = response.json()
        
        # Should use defaults
        assert data["total"] <= 10


class TestExpressWizardSorting:
    """Tests for priority_score sorting"""
    
    def test_sorted_by_priority_score_descending(self):
        """Opportunities are sorted by priority_score DESC"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=3&max_total=15")
        assert response.status_code == 200
        data = response.json()
        
        scores = [o["priority_score"] for o in data["opportunities"]]
        assert scores == sorted(scores, reverse=True), "Should be sorted by priority_score DESC"
    
    def test_highest_priority_first(self):
        """First opportunity has highest priority score"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=3&max_total=15")
        data = response.json()
        
        if len(data["opportunities"]) > 1:
            first_score = data["opportunities"][0]["priority_score"]
            last_score = data["opportunities"][-1]["priority_score"]
            assert first_score >= last_score


class TestExpressWizardEdgeCases:
    """Edge case tests"""
    
    def test_handles_empty_trends_gracefully(self):
        """Returns fewer items if some countries have no trends"""
        # This test verifies the endpoint doesn't crash
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=10&max_total=100")
        assert response.status_code == 200
        data = response.json()
        
        # Should return whatever is available
        assert data["status"] == "ok"
        assert isinstance(data["opportunities"], list)
    
    def test_no_mongodb_id_in_response(self):
        """No _id field from MongoDB in response"""
        response = requests.get(f"{BASE_URL}/api/hotmart/express-wizard?per_country=2&max_total=10")
        data = response.json()
        
        assert "_id" not in data
        for opp in data["opportunities"]:
            assert "_id" not in opp


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work after adding express-wizard"""
    
    def test_health_endpoint(self):
        """GET /api/health still works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_countries_endpoint(self):
        """GET /api/countries still works"""
        response = requests.get(f"{BASE_URL}/api/countries")
        assert response.status_code == 200
        assert len(response.json()) == 5
    
    def test_research_overview_endpoint(self):
        """GET /api/research/overview still works"""
        response = requests.get(f"{BASE_URL}/api/research/overview")
        assert response.status_code == 200
        assert len(response.json()) == 5
    
    def test_hotmart_status_endpoint(self):
        """GET /api/hotmart/status still works"""
        response = requests.get(f"{BASE_URL}/api/hotmart/status")
        assert response.status_code == 200
        assert response.json()["credentials_configured"] == True
    
    def test_hotmart_test_connection_endpoint(self):
        """POST /api/hotmart/test-connection still works"""
        response = requests.post(f"{BASE_URL}/api/hotmart/test-connection")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_hotmart_my_affiliations_endpoint(self):
        """GET /api/hotmart/my-affiliations still works"""
        response = requests.get(f"{BASE_URL}/api/hotmart/my-affiliations")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_hotmart_sync_affiliations_endpoint(self):
        """POST /api/hotmart/sync-affiliations still works"""
        response = requests.post(f"{BASE_URL}/api/hotmart/sync-affiliations")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_hotmart_rematch_all_endpoint(self):
        """POST /api/hotmart/rematch-all still works"""
        response = requests.post(f"{BASE_URL}/api/hotmart/rematch-all")
        assert response.status_code == 200
        assert response.json()["status"] == "started"
    
    def test_products_endpoint(self):
        """GET /api/products/{country_code} still works"""
        response = requests.get(f"{BASE_URL}/api/products/AR?limit=5")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_research_trends_endpoint(self):
        """GET /api/research/trends/{country_code} still works"""
        response = requests.get(f"{BASE_URL}/api/research/trends/AR")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
