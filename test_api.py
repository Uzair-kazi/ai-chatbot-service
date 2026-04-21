#!/usr/bin/env python3
"""
Test script for Admin AI Chatbot API

Usage:
    python test_api.py                          # Use hardcoded token
    python test_api.py "Your custom question"   # Use hardcoded token with custom question
    python test_api.py --login                  # Use login endpoint to get token
    python test_api.py --login "Your question"  # Login and ask custom question
"""

import sys
import requests
import jwt
from datetime import datetime, timedelta, timezone
import json

# Configuration
API_URL = "http://localhost:8000"
JWT_SECRET = "2kvTRVNZKy5D0fqe6VJJTTKLbTR5QMd"  # From .env file

# Login credentials (only used with --login flag)
LOGIN_EMAIL = "admin@croyanceqs.com"
LOGIN_PASSWORD = "123456"  # Change this to your actual admin password

# Colors for terminal output
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(text, color):
    """Print colored text"""
    print(f"{color}{text}{Colors.NC}")

def login_and_get_token():
    """Login using the /v1/login endpoint and get a JWT token"""
    print_colored("\n=== Logging in via /v1/login ===", Colors.YELLOW)
    
    try:
        response = requests.post(
            f"{API_URL}/v1/login",
            json={
                "email": LOGIN_EMAIL,
                "password": LOGIN_PASSWORD
            }
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_colored(f"✓ Login successful!", Colors.GREEN)
            print(f"  User: {data['user']['name']} ({data['user']['email']})")
            print(f"  Role: {data['user']['role']}")
            return data['token']
        else:
            print_colored(f"✗ Login failed: {response.json().get('detail', 'Unknown error')}", Colors.RED)
            return None
            
    except Exception as e:
        print_colored(f"Error: {e}", Colors.RED)
        return None

def generate_jwt_token():
    """Generate a test JWT token for admin user"""
    payload = {
        "id": "test_user_123",
        "email": "admin@example.com",
        "name": "Test Admin",
        "role_name": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return token

def test_health():
    """Test the health endpoint"""
    print_colored("\n=== Testing Health Endpoint ===", Colors.YELLOW)
    
    try:
        response = requests.get(f"{API_URL}/v1/health")
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print_colored(f"Error: {e}", Colors.RED)
        return False

def test_ask_question(token, question):
    """Test the /v1/ask endpoint"""
    print_colored(f"\n=== Asking Question ===", Colors.YELLOW)
    print_colored(f"Question: {question}", Colors.BLUE)
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "question": question
        }
        
        response = requests.post(
            f"{API_URL}/v1/ask",
            headers=headers,
            json=data
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        # Print rate limit headers
        print_colored("\nRate Limit Headers:", Colors.YELLOW)
        for header in ['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset', 'X-Request-ID']:
            if header in response.headers:
                print(f"  {header}: {response.headers[header]}")
        
        # Print response
        print_colored("\nResponse:", Colors.YELLOW)
        response_data = response.json()
        print(json.dumps(response_data, indent=2))
        
        if response.status_code == 200:
            print_colored(f"\n✓ Answer: {response_data.get('answer', 'N/A')}", Colors.GREEN)
            print_colored(f"✓ SQL: {response_data.get('sql', 'N/A')}", Colors.GREEN)
            print_colored(f"✓ Rows: {response_data.get('rows_count', 0)}", Colors.GREEN)
        
        return response.status_code == 200
    except Exception as e:
        print_colored(f"Error: {e}", Colors.RED)
        return False

def test_metrics():
    """Test the metrics endpoint"""
    print_colored("\n=== Testing Metrics Endpoint ===", Colors.YELLOW)
    
    try:
        response = requests.get(f"{API_URL}/v1/metrics")
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print_colored(f"Error: {e}", Colors.RED)
        return False

def main():
    """Main test function"""
    print_colored("=" * 60, Colors.YELLOW)
    print_colored("  Admin AI Chatbot API - Test Script", Colors.YELLOW)
    print_colored("=" * 60, Colors.YELLOW)
    
    # Check if server is running
    try:
        response = requests.get(API_URL, timeout=2)
        print_colored(f"✓ Server is running at {API_URL}", Colors.GREEN)
    except:
        print_colored(f"✗ Server is not running at {API_URL}", Colors.RED)
        print_colored("  Start the server with: python main.py", Colors.YELLOW)
        return
    
    # Parse command line arguments
    use_login = "--login" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--login"]
    
    # Get JWT token
    if use_login:
        print_colored("\n✓ Using login endpoint to get token...", Colors.GREEN)
        token = login_and_get_token()
        if not token:
            print_colored("\n✗ Failed to get token from login endpoint", Colors.RED)
            return
    else:
        print_colored("\n✓ Generating JWT token...", Colors.GREEN)
        token = generate_jwt_token()
    
    # Run tests
    test_health()
    
    # Get question from command line or use default
    if args:
        question = " ".join(args)
    else:
        question = "How many ISO tanks are in the database?"
    
    test_ask_question(token, question)
    test_metrics()
    
    # Print helpful info
    print_colored("\n" + "=" * 60, Colors.YELLOW)
    print_colored("  Interactive API Documentation:", Colors.YELLOW)
    print_colored(f"    Swagger UI: {API_URL}/docs", Colors.BLUE)
    print_colored(f"    ReDoc:      {API_URL}/redoc", Colors.BLUE)
    print_colored("\n  Usage:", Colors.YELLOW)
    print_colored(f"    python test_api.py                          # Use hardcoded token", Colors.BLUE)
    print_colored(f"    python test_api.py --login                  # Use login endpoint", Colors.BLUE)
    print_colored(f"    python test_api.py \"Your question\"          # Custom question", Colors.BLUE)
    print_colored(f"    python test_api.py --login \"Your question\"  # Login + custom question", Colors.BLUE)
    print_colored("=" * 60, Colors.YELLOW)

if __name__ == "__main__":
    main()
