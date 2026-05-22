#!/usr/bin/env python3
"""
Debug script to test which AI model is being used and how it responds.
Run this to verify your AI provider configuration and see actual responses.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.ai_provider import ai_client, model_name, provider_name, SDK_TYPE
from services.schema import get_database_schema
import json

def test_model_info():
    """Test which model is actually being used."""
    print("=" * 60)
    print("AI MODEL CONFIGURATION TEST")
    print("=" * 60)
    print(f"Provider: {provider_name}")
    print(f"Model: {model_name}")
    print(f"SDK Type: {SDK_TYPE}")
    print(f"Client Type: {type(ai_client)}")
    print()

def test_simple_question():
    """Test a simple question to see if the model responds correctly."""
    print("=" * 60)
    print("SIMPLE AI RESPONSE TEST")
    print("=" * 60)
    
    test_question = "What is 2 + 2?"
    print(f"Question: {test_question}")
    
    try:
        if SDK_TYPE == "openai_compatible":
            response = ai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Answer briefly."},
                    {"role": "user", "content": test_question}
                ],
                temperature=0.1,
                max_tokens=100
            )
            answer = response.choices[0].message.content.strip()
            
            # Log token usage if available
            if hasattr(response, 'usage'):
                print(f"Token usage: {response.usage.prompt_tokens} prompt + {response.usage.completion_tokens} completion = {response.usage.total_tokens} total")
            
        elif SDK_TYPE == "anthropic":
            response = ai_client.messages.create(
                model=model_name,
                max_tokens=100,
                temperature=0.1,
                system="You are a helpful assistant. Answer briefly.",
                messages=[
                    {"role": "user", "content": test_question}
                ]
            )
            answer = response.content[0].text.strip()
            
            # Log token usage if available
            if hasattr(response, 'usage'):
                print(f"Token usage: {response.usage.input_tokens} input + {response.usage.output_tokens} output")
        
        print(f"Answer: {answer}")
        print("✅ AI model is responding correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error calling AI model: {e}")
        return False

def test_sql_generation():
    """Test SQL generation with a simple question."""
    print("=" * 60)
    print("SQL GENERATION TEST")
    print("=" * 60)
    
    # Get schema
    try:
        schema = get_database_schema()
        print(f"Schema loaded: {len(schema)} characters")
        print("First 200 characters of schema:")
        print(schema[:200] + "...")
        print()
    except Exception as e:
        print(f"❌ Error loading schema: {e}")
        return False
    
    # Test SQL generation
    test_question = "How many ISO tanks are there?"
    print(f"Question: {test_question}")
    
    system_prompt = f"""You are a SQL query generator for a PostgreSQL database.

{schema[:2000]}  # Truncated for testing

RULES:
- Return ONLY the SQL query, no markdown, no explanation
- Always use SELECT queries only
- Always include LIMIT 100
- Use proper table and column names from the schema

USER QUESTION:
"""
    
    try:
        if SDK_TYPE == "openai_compatible":
            response = ai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": test_question}
                ],
                temperature=0.1,
                max_tokens=200
            )
            sql = response.choices[0].message.content.strip()
            
        elif SDK_TYPE == "anthropic":
            response = ai_client.messages.create(
                model=model_name,
                max_tokens=200,
                temperature=0.1,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": test_question}
                ]
            )
            sql = response.content[0].text.strip()
        
        print(f"Generated SQL: {sql}")
        
        # Basic validation
        if "SELECT" in sql.upper() and "iso_tank" in sql.lower():
            print("✅ SQL looks reasonable!")
            return True
        else:
            print("❌ SQL doesn't look right - might be hallucinating table names")
            return False
            
    except Exception as e:
        print(f"❌ Error generating SQL: {e}")
        return False

def main():
    """Run all tests."""
    print("🔍 DEBUGGING AI MODEL CONFIGURATION")
    print()
    
    # Test 1: Model info
    test_model_info()
    
    # Test 2: Simple response
    if not test_simple_question():
        print("\n❌ Basic AI test failed. Check your API key and configuration.")
        return
    
    print()
    
    # Test 3: SQL generation
    if not test_sql_generation():
        print("\n❌ SQL generation test failed. This might be why your chatbot isn't working.")
        return
    
    print()
    print("=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("Your AI model is working. The issue might be in the multi-agent pipeline.")
    print("=" * 60)

if __name__ == "__main__":
    main()