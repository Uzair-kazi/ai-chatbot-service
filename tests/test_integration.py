"""
Integration Tests for Admin AI Chatbot

These tests validate the complete pipeline with realistic questions.
They require both database and AI provider configuration.

Success Criteria:
- 80%+ SQL accuracy (correct SQL patterns generated)
- 90%+ queries complete in under 5 seconds
- All questions return human-readable answers
"""

import os
import json
import time
import pytest
from pathlib import Path
from services.chatbot_pipeline import ask


# Load realistic questions from fixture
FIXTURES_DIR = Path(__file__).parent / "fixtures"
with open(FIXTURES_DIR / "realistic_questions.json", "r") as f:
    REALISTIC_QUESTIONS = json.load(f)


@pytest.mark.skipif(
    not all([
        os.getenv("DB_URL"),
        os.getenv("AI_API_KEY"),
        os.getenv("AI_MODEL"),
        os.getenv("SDK_TYPE")
    ]),
    reason="Database and AI provider not configured - skipping integration tests"
)
@pytest.mark.integration
class TestRealisticQuestions:
    """Test suite for realistic business questions."""
    
    def test_sql_accuracy(self):
        """Test that 80%+ of questions generate correct SQL patterns."""
        correct_count = 0
        total_count = len(REALISTIC_QUESTIONS)
        
        results = []
        
        for item in REALISTIC_QUESTIONS:
            question = item["question"]
            expected_patterns = item["expected_patterns"]
            
            result = ask(question)
            
            # Check if SQL contains expected patterns
            sql = result["sql"].upper()
            patterns_found = sum(1 for pattern in expected_patterns if pattern.upper() in sql)
            is_correct = patterns_found >= len(expected_patterns) * 0.7  # 70% of patterns must match
            
            if is_correct:
                correct_count += 1
            
            results.append({
                "question": question,
                "sql": result["sql"],
                "is_correct": is_correct,
                "patterns_found": patterns_found,
                "patterns_expected": len(expected_patterns)
            })
        
        accuracy = (correct_count / total_count) * 100
        
        # Log results
        print(f"\n=== SQL Accuracy Test Results ===")
        print(f"Correct: {correct_count}/{total_count} ({accuracy:.1f}%)")
        print(f"\nDetailed Results:")
        for r in results:
            status = "✓" if r["is_correct"] else "✗"
            print(f"{status} {r['question']}")
            print(f"  SQL: {r['sql']}")
            print(f"  Patterns: {r['patterns_found']}/{r['patterns_expected']}")
        
        # Assert 80%+ accuracy
        assert accuracy >= 80, f"SQL accuracy {accuracy:.1f}% is below 80% threshold"
    
    def test_performance(self):
        """Test that 90%+ of queries complete in under 5 seconds."""
        fast_count = 0
        total_count = len(REALISTIC_QUESTIONS)
        
        results = []
        
        for item in REALISTIC_QUESTIONS:
            question = item["question"]
            
            start_time = time.time()
            result = ask(question)
            execution_time = time.time() - start_time
            
            is_fast = execution_time < 5.0
            
            if is_fast:
                fast_count += 1
            
            results.append({
                "question": question,
                "execution_time": execution_time,
                "is_fast": is_fast
            })
        
        performance_rate = (fast_count / total_count) * 100
        
        # Log results
        print(f"\n=== Performance Test Results ===")
        print(f"Fast queries: {fast_count}/{total_count} ({performance_rate:.1f}%)")
        print(f"\nDetailed Results:")
        for r in results:
            status = "✓" if r["is_fast"] else "✗"
            print(f"{status} {r['question']}: {r['execution_time']:.2f}s")
        
        # Assert 90%+ under 5 seconds
        assert performance_rate >= 90, f"Performance rate {performance_rate:.1f}% is below 90% threshold"
    
    def test_answer_quality(self):
        """Test that all questions return human-readable answers."""
        failed_questions = []
        
        for item in REALISTIC_QUESTIONS:
            question = item["question"]
            
            result = ask(question)
            
            # Check answer quality
            answer = result["answer"]
            
            # Answer should be non-empty
            if not answer or len(answer) < 10:
                failed_questions.append({
                    "question": question,
                    "reason": "Answer too short or empty",
                    "answer": answer
                })
                continue
            
            # Answer should not be an error message (status 200)
            if result["status_code"] != 200:
                failed_questions.append({
                    "question": question,
                    "reason": f"Error status {result['status_code']}",
                    "answer": answer
                })
                continue
        
        # Log results
        if failed_questions:
            print(f"\n=== Answer Quality Issues ===")
            for f in failed_questions:
                print(f"Question: {f['question']}")
                print(f"Reason: {f['reason']}")
                print(f"Answer: {f['answer']}\n")
        
        # Assert all questions have good answers
        assert len(failed_questions) == 0, f"{len(failed_questions)} questions failed answer quality check"
    
    def test_sample_questions(self):
        """Test a few sample questions to verify end-to-end functionality."""
        # Test 1: COUNT query
        result = ask("How many ISO tanks are there?")
        assert result["status_code"] == 200
        assert "COUNT" in result["sql"].upper()
        assert len(result["answer"]) > 0
        
        # Test 2: FILTER query
        result = ask("Show me ISO tanks with status 'IN'")
        assert result["status_code"] == 200
        assert "iso_tank_status" in result["sql"].lower()
        assert len(result["answer"]) > 0
        
        # Test 3: DATE query
        result = ask("List ISO tanks created today")
        assert result["status_code"] == 200
        assert "created_at" in result["sql"].lower()
        assert len(result["answer"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
