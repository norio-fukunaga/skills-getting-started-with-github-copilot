"""
Tests for the Mergington High School API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        if name in activities:
            activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root path redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that GET /activities returns all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        
        # Check structure of one activity
        first_activity = list(data.values())[0]
        assert "description" in first_activity
        assert "schedule" in first_activity
        assert "max_participants" in first_activity
        assert "participants" in first_activity
    
    def test_get_activities_includes_specific_activities(self, client):
        """Test that specific activities are present"""
        response = client.get("/activities")
        data = response.json()
        
        assert "Chess Club" in data
        assert "Programming Class" in data
        assert "Soccer Team" in data


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_for_existing_activity(self, client):
        """Test successful signup for an existing activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_for_nonexistent_activity(self, client):
        """Test signup for activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Activity/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_duplicate_signup_fails(self, client):
        """Test that signing up twice for same activity fails"""
        email = "test@mergington.edu"
        activity = "Chess Club"
        
        # First signup should succeed
        response1 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response2.status_code == 400
        assert "already signed up" in response2.json()["detail"]
    
    def test_signup_with_special_characters_in_activity_name(self, client):
        """Test signup with URL-encoded activity name"""
        response = client.post(
            "/activities/Soccer%20Team/signup?email=player@mergington.edu"
        )
        assert response.status_code == 200


class TestUnregisterFromActivity:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant(self, client):
        """Test successful unregistration of an existing participant"""
        # First, sign up a student
        email = "testremove@mergington.edu"
        activity = "Chess Club"
        client.post(f"/activities/{activity}/signup?email={email}")
        
        # Then unregister them
        response = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity in data["message"]
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data[activity]["participants"]
    
    def test_unregister_from_nonexistent_activity(self, client):
        """Test unregister from activity that doesn't exist"""
        response = client.delete(
            "/activities/Nonexistent Activity/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_unregister_participant_not_signed_up(self, client):
        """Test unregistering a participant who isn't signed up"""
        response = client.delete(
            "/activities/Chess Club/unregister?email=notsignedup@mergington.edu"
        )
        assert response.status_code == 400
        assert "not signed up" in response.json()["detail"]
    
    def test_unregister_original_participant(self, client):
        """Test unregistering an originally enrolled participant"""
        # Chess Club has "michael@mergington.edu" and "daniel@mergington.edu"
        response = client.delete(
            "/activities/Chess Club/unregister?email=michael@mergington.edu"
        )
        assert response.status_code == 200
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "michael@mergington.edu" not in activities_data["Chess Club"]["participants"]


class TestActivityWorkflow:
    """Integration tests for complete workflows"""
    
    def test_signup_and_unregister_workflow(self, client):
        """Test complete workflow of signing up and unregistering"""
        email = "workflow@mergington.edu"
        activity = "Drama Club"
        
        # Get initial participant count
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()[activity]["participants"])
        
        # Sign up
        signup_response = client.post(f"/activities/{activity}/signup?email={email}")
        assert signup_response.status_code == 200
        
        # Verify count increased
        after_signup = client.get("/activities")
        assert len(after_signup.json()[activity]["participants"]) == initial_count + 1
        
        # Unregister
        unregister_response = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert unregister_response.status_code == 200
        
        # Verify count returned to original
        after_unregister = client.get("/activities")
        assert len(after_unregister.json()[activity]["participants"]) == initial_count
    
    def test_multiple_participants_same_activity(self, client):
        """Test multiple participants can sign up for the same activity"""
        activity = "Programming Class"
        emails = [
            "student1@mergington.edu",
            "student2@mergington.edu",
            "student3@mergington.edu"
        ]
        
        for email in emails:
            response = client.post(f"/activities/{activity}/signup?email={email}")
            assert response.status_code == 200
        
        # Verify all are in the activity
        activities_response = client.get("/activities")
        participants = activities_response.json()[activity]["participants"]
        for email in emails:
            assert email in participants
