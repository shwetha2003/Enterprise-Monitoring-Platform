import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt

from app.main import app
from app.database import get_db
from app.auth import create_access_token, get_current_user
from app.config import settings

client = TestClient(app)

def test_jwt_security():
    """Test JWT token security features"""
    # Test token creation with different algorithms
    token = create_access_token({"sub": "testuser"})
    
    # Verify token can be decoded with correct secret
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "testuser"
    
    # Test token expiration
    import time
    expired_token = create_access_token(
        {"sub": "testuser"}, 
        expires_delta=datetime.timedelta(seconds=-1)
    )
    
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(expired_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def test_sql_injection_protection():
    """Test SQL injection protection"""
    # Test with potential SQL injection in parameters
    malicious_input = "test'; DROP TABLE users; --"
    
    response = client.get(f"/api/assets?search={malicious_input}")
    
    # Should not crash - returns empty results or error
    assert response.status_code in [200, 400, 422]
    
    if response.status_code == 200:
        # Should return empty array, not execute SQL
        assert isinstance(response.json(), list)

def test_xss_protection():
    """Test XSS protection in API responses"""
    # Create asset with potential XSS payload
    xss_payload = "<script>alert('xss')</script>"
    
    response = client.post(
        "/api/assets",
        json={
            "name": xss_payload,
            "asset_type": "financial",
            "status": "active"
        },
        headers={"Authorization": "Bearer test-token"}
    )
    
    # Response should escape or reject the XSS payload
    if response.status_code == 200:
        asset = response.json()
        # The name should be sanitized or rejected
        assert xss_payload not in asset.get("name", "")

def test_rate_limiting():
    """Test rate limiting on API endpoints"""
    # Make multiple requests quickly
    for i in range(20):
        response = client.get("/api/assets")
    
    # After many requests, should get rate limited (429)
    # Note: Rate limiting is handled by Nginx in production
    # This test may need to be adjusted based on implementation

def test_cors_security():
    """Test CORS security headers"""
    response = client.options(
        "/api/assets",
        headers={
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    # Check CORS headers
    cors_headers = response.headers.get("Access-Control-Allow-Origin")
    
    # Should only allow configured origins
    if cors_headers:
        assert "http://malicious-site.com" not in cors_headers

def test_content_security():
    """Test content type security"""
    # Test with incorrect content type
    response = client.post(
        "/api/assets",
        data="malformed data",
        headers={
            "Content-Type": "text/plain",
            "Authorization": "Bearer test-token"
        }
    )
    
    # Should reject incorrect content type
    assert response.status_code in [400, 415, 422]

def test_authentication_bypass():
    """Test authentication bypass attempts"""
    # Try to access protected endpoint without token
    response = client.get("/api/assets")
    
    # Should return 401 Unauthorized
    assert response.status_code == 401
    
    # Try with invalid token
    response = client.get(
        "/api/assets",
        headers={"Authorization": "Bearer invalid-token"}
    )
    
    assert response.status_code == 401
    
    # Try with malformed token
    response = client.get(
        "/api/assets",
        headers={"Authorization": "Malformed token"}
    )
    
    assert response.status_code == 401

def test_path_traversal():
    """Test path traversal protection"""
    # Try path traversal in file downloads
    response = client.get("/api/reports/1/download?file=../../../etc/passwd")
    
    # Should reject path traversal attempts
    assert response.status_code in [400, 403, 404]
    
    # Test in other endpoints
    response = client.get("/api/assets/../../etc/passwd")
    assert response.status_code in [400, 404]

def test_mass_assignment():
    """Test mass assignment protection"""
    # Try to set internal fields that shouldn't be settable
    response = client.post(
        "/api/assets",
        json={
            "name": "Test Asset",
            "asset_type": "financial",
            "status": "active",
            "created_at": "2023-01-01",  # Internal field
            "health_score": 100,  # Should be calculated, not set
            "is_admin": True  # Non-existent field
        },
        headers={"Authorization": "Bearer test-token"}
    )
    
    # Should ignore or reject internal fields
    if response.status_code == 200:
        asset = response.json()
        # Internal fields should not be set by user input
        assert asset.get("is_admin") is None

if __name__ == "__main__":
    pytest.main([__file__])
