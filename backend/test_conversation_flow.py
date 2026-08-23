#!/usr/bin/env python3
"""
Test conversation flow to verify booking state is maintained across turns
"""

import requests
import json
import sys
import time

API_URL = "http://localhost:8000/ai/chat"
SESSION_ID = "test-conv-001"

def test_conversation(message: str, test_name: str):
    """Send a message and return the response"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"Message: {message}")
    print()
    
    payload = {
        "session_id": SESSION_ID,
        "message": message,
        "detected_language": "en"
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print(f"Response:")
        print(f"{data.get('reply', 'No reply')}")
        print()
        
        # Check for issues
        reply_lower = data.get('reply', '').lower()
        return data, reply_lower
        
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to API at {API_URL}")
        print(f"Make sure the server is running!")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        return None, ""

def main():
    print("Starting Conversation Flow Test")
    print(f"API URL: {API_URL}")
    print(f"Session ID: {SESSION_ID}")
    
    # Test 1: Send dates, adults, room type in one message
    data1, reply1 = test_conversation(
        "I want to book a room from December 20, 2027 to December 22, 2027 for 2 adults",
        "Full booking info in one message"
    )
    
    if data1 is None:
        return
    
    # Test 2: Book confirmation - should NOT ask for dates again
    data2, reply2 = test_conversation(
        "Yes, please book that",
        "Confirmation (should NOT repeat date questions)"
    )
    
    # Check if dates were repeated
    repeat_date_keywords = ['what date', 'check-in', 'check in', 'check-out', 'check out', 
                           'when', 'how many', 'which date', 'arrival', 'departure']
    asking_for_dates = any(kw in reply2 for kw in repeat_date_keywords)
    
    print(f"\n{'='*60}")
    print("ANALYSIS")
    print(f"{'='*60}")
    
    if asking_for_dates:
        print("❌ FAILURE: Assistant asked for dates again!")
        print("This indicates booking state is NOT being maintained properly.")
    else:
        print("✅ SUCCESS: No repeat date questions detected!")
        print("Booking state appears to be maintained correctly.")
    
    # Test 3: Check if LLM can use room selection from availability
    print(f"\n{'='*60}")
    print("Additional Status Checks")
    print(f"{'='*60}")
    
    if "booking" in reply2.lower() and "success" in reply2.lower():
        print("✅ Booking appears to have been created successfully")
    elif "available room" in reply2.lower() or "room" in reply2.lower():
        print("⚠ Response mentions rooms - may need room selection or confirmation")
    else:
        print("ℹ Response content indicates: " + reply2[:100] + "...")

if __name__ == "__main__":
    main()
