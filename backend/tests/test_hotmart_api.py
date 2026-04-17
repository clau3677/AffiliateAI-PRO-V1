"""
Hotmart Super Agent - Module 1 API Tests
Tests for market research endpoints: health, countries, research execution, trends, summary
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoint:
    """Health check endpoint tests"""
    
    def test_health_returns_status_ok(self):
        """GET /api/health → returns status, mongo:true, llm_key_configured:true"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "mongo" in data
        assert data["mongo"] is True
        assert "llm_key_configured" in data
        assert data["llm_key_configured"] is True
        assert "timestamp" in data


class TestCountriesEndpoint:
    """Countries configuration endpoint tests"""
    
    def test_countries_returns_five_countries(self):
        """GET /api/countries → returns 5 countries (AR, CL, CO, PE, BR) with seed_keywords"""
        response = requests.get(f"{BASE_URL}/api/countries")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5
        
        country_codes = [c["code"] for c in data]
        assert set(country_codes) == {"AR", "CL", "CO", "PE", "BR"}
        
        # Verify each country has required fields
        for country in data:
            assert "code" in country
            assert "name" in country
            assert "currency" in country
            assert "language" in country
            assert "seed_keywords" in country
            assert isinstance(country["seed_keywords"], list)
            assert len(country["seed_keywords"]) > 0


class TestResearchOverview:
    """Research overview endpoint tests"""
    
    def test_overview_returns_five_country_cards(self):
        """GET /api/research/overview → returns 5 country cards with total_trends, avg_priority_score, recommendation_priority"""
        response = requests.get(f"{BASE_URL}/api/research/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5
        
        for country in data:
            assert "code" in country
            assert "name" in country
            assert "total_trends" in country
            assert isinstance(country["total_trends"], int)
            assert "avg_priority_score" in country
            assert isinstance(country["avg_priority_score"], (int, float))
            assert "recommendation_priority" in country
            assert country["recommendation_priority"] in ["HIGH", "MEDIUM", "LOW"]
            # Verify no _id field from MongoDB
            assert "_id" not in country


class TestResearchExecution:
    """Research execution endpoint tests"""
    
    def test_run_research_starts_execution(self):
        """POST /api/research/run with {countries:['CL']} → returns execution_id, status:started"""
        response = requests.post(
            f"{BASE_URL}/api/research/run",
            json={"countries": ["CL"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "execution_id" in data
        assert "status" in data
        assert data["status"] == "started"
        assert "countries" in data
        assert "CL" in data["countries"]
        assert "total_expected" in data
        
        # Store execution_id for next test
        TestResearchExecution.execution_id = data["execution_id"]
    
    def test_get_execution_tracks_progress(self):
        """GET /api/research/executions/{id} → tracks progress until status:completed"""
        execution_id = getattr(TestResearchExecution, 'execution_id', None)
        if not execution_id:
            pytest.skip("No execution_id from previous test")
        
        # Poll for completion (max 120 seconds)
        max_wait = 120
        poll_interval = 5
        elapsed = 0
        final_status = None
        
        while elapsed < max_wait:
            response = requests.get(f"{BASE_URL}/api/research/executions/{execution_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "id" in data
            assert "status" in data
            assert "progress" in data
            assert "_id" not in data  # No MongoDB _id
            
            final_status = data["status"]
            if final_status in ["completed", "failed"]:
                break
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        assert final_status == "completed", f"Execution did not complete in {max_wait}s, status: {final_status}"
    
    def test_run_research_invalid_country(self):
        """POST /api/research/run with invalid country → returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/research/run",
            json={"countries": ["XX"]}
        )
        assert response.status_code == 400


class TestTrendsEndpoint:
    """Trends endpoint tests"""
    
    def test_get_trends_for_researched_country(self):
        """GET /api/research/trends/AR → returns list of trends with required fields"""
        response = requests.get(f"{BASE_URL}/api/research/trends/AR")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            trend = data[0]
            assert "keyword" in trend
            assert "interest_score" in trend
            assert "priority_score" in trend
            assert "commercial_intent" in trend
            assert trend["commercial_intent"] in ["Alta", "Media", "Baja"]
            assert "pain_point" in trend
            assert "suggested_product_type" in trend
            assert "_id" not in trend  # No MongoDB _id
    
    def test_get_trends_invalid_country(self):
        """GET /api/research/trends/XX (invalid country) → returns 400"""
        response = requests.get(f"{BASE_URL}/api/research/trends/XX")
        assert response.status_code == 400
    
    def test_trends_sort_by_priority_score(self):
        """Verify sort_by param works for priority_score"""
        response = requests.get(f"{BASE_URL}/api/research/trends/AR?sort_by=priority_score")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 1:
            # Should be sorted descending by priority_score
            scores = [t["priority_score"] for t in data]
            assert scores == sorted(scores, reverse=True)
    
    def test_trends_sort_by_interest_score(self):
        """Verify sort_by param works for interest_score"""
        response = requests.get(f"{BASE_URL}/api/research/trends/AR?sort_by=interest_score")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 1:
            # Should be sorted descending by interest_score
            scores = [t["interest_score"] for t in data]
            assert scores == sorted(scores, reverse=True)
    
    def test_trends_sort_by_keyword(self):
        """Verify sort_by param works for keyword"""
        response = requests.get(f"{BASE_URL}/api/research/trends/AR?sort_by=keyword")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 1:
            # Should be sorted ascending by keyword
            keywords = [t["keyword"] for t in data]
            assert keywords == sorted(keywords)


class TestSummaryEndpoint:
    """Country summary endpoint tests"""
    
    def test_get_summary_for_researched_country(self):
        """GET /api/research/summary/AR → returns CountrySummary with required fields"""
        response = requests.get(f"{BASE_URL}/api/research/summary/AR")
        assert response.status_code == 200
        
        data = response.json()
        assert "code" in data
        assert data["code"] == "AR"
        assert "name" in data
        assert "total_trends" in data
        assert "top_needs" in data
        assert isinstance(data["top_needs"], list)
        assert "pain_points" in data
        assert isinstance(data["pain_points"], list)
        assert "avg_priority_score" in data
        assert "recommendation_priority" in data
        assert data["recommendation_priority"] in ["HIGH", "MEDIUM", "LOW"]
    
    def test_get_summary_invalid_country(self):
        """GET /api/research/summary/XX (invalid country) → returns 400"""
        response = requests.get(f"{BASE_URL}/api/research/summary/XX")
        assert response.status_code == 400


class TestDeleteTrends:
    """Delete trends endpoint tests"""
    
    def test_delete_trends_for_country(self):
        """DELETE /api/research/trends/CL → deletes trends for that country, returns count"""
        # First ensure CL has been researched (from earlier test)
        response = requests.delete(f"{BASE_URL}/api/research/trends/CL")
        assert response.status_code == 200
        
        data = response.json()
        assert "deleted" in data
        assert isinstance(data["deleted"], int)
        assert "country_code" in data
        assert data["country_code"] == "CL"
    
    def test_delete_trends_invalid_country(self):
        """DELETE /api/research/trends/XX (invalid country) → returns 400"""
        response = requests.delete(f"{BASE_URL}/api/research/trends/XX")
        assert response.status_code == 400


class TestModule2Placeholder:
    """Module 2 placeholder endpoint tests"""
    
    def test_products_match_returns_501(self):
        """POST /api/products/match/AR returns 501 (Module 2 placeholder)"""
        response = requests.post(f"{BASE_URL}/api/products/match/AR")
        assert response.status_code == 501
        
        data = response.json()
        assert "detail" in data


class TestNoMongoIdInResponses:
    """Verify MongoDB _id is never exposed in API responses"""
    
    def test_overview_no_id(self):
        """Overview endpoint should not include _id"""
        response = requests.get(f"{BASE_URL}/api/research/overview")
        data = response.json()
        for item in data:
            assert "_id" not in item
    
    def test_trends_no_id(self):
        """Trends endpoint should not include _id"""
        response = requests.get(f"{BASE_URL}/api/research/trends/AR")
        data = response.json()
        for item in data:
            assert "_id" not in item
    
    def test_executions_no_id(self):
        """Executions endpoint should not include _id"""
        response = requests.get(f"{BASE_URL}/api/research/executions")
        data = response.json()
        for item in data:
            assert "_id" not in item
