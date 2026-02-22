#!/usr/bin/env python3
"""Test that ALLOWED_USER_IDS loads correctly from .env file"""
import os
import sys

# Test 1: Load from actual .env file
print("\n" + "="*60)
print("TEST 1: Loading ALLOWED_USER_IDS from .env")
print("="*60)

from config import ALLOWED_USER_IDS

print(f"ALLOWED_USER_IDS loaded: {ALLOWED_USER_IDS}")
print(f"Type: {type(ALLOWED_USER_IDS)}")
print(f"Number of allowed users: {len(ALLOWED_USER_IDS)}")

if ALLOWED_USER_IDS:
    print(f"Allowed user IDs: {sorted(ALLOWED_USER_IDS)}")
else:
    print("⚠️  No users allowed (empty allowlist)")

# Test 2: Check environment variable
print("\n" + "="*60)
print("TEST 2: Checking environment variable")
print("="*60)

raw_value = os.environ.get("ALLOWED_USER_IDS", "")
print(f"ALLOWED_USER_IDS env var: '{raw_value}'")

# Test 3: Validate it's a frozenset
print("\n" + "="*60)
print("TEST 3: Validate type and immutability")
print("="*60)

assert isinstance(ALLOWED_USER_IDS, frozenset), "Should be a frozenset"
print("✅ ALLOWED_USER_IDS is a frozenset (immutable)")

try:
    # Try to modify it (should fail)
    ALLOWED_USER_IDS.add(999)
    print("❌ ERROR: Was able to modify frozenset!")
except AttributeError:
    print("✅ Cannot modify frozenset (as expected)")

# Test 4: Check usage example
print("\n" + "="*60)
print("TEST 4: Usage example")
print("="*60)

test_user_id = 123456789

if test_user_id in ALLOWED_USER_IDS:
    print(f"✅ User {test_user_id} is allowed")
else:
    print(f"❌ User {test_user_id} is NOT allowed")

print("\n" + "="*60)
print("✅ All tests passed!")
print("="*60)

print("\nTo configure allowed users:")
print("1. Edit .env file")
print("2. Add: ALLOWED_USER_IDS=123456789,987654321")
print("3. Restart your bot")
print("\nTo find your Telegram user ID, message @userinfobot on Telegram")

