"""
Tests for Input Schema Validation.
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interface.schema import InputSchema, InputType

class TestSchema(unittest.TestCase):
    
    def test_yes_no(self):
        schema = InputSchema(InputType.YES_NO, "Confirm?")
        
        valid, val = schema.validate("yes")
        self.assertTrue(valid)
        self.assertTrue(val)
        
        valid, val = schema.validate("n")
        self.assertTrue(valid)
        self.assertFalse(val)
        
        valid, _ = schema.validate("maybe")
        self.assertFalse(valid)

    def test_number(self):
        schema = InputSchema(InputType.NUMBER, "Age?", min_value=0, max_value=120)
        
        valid, val = schema.validate("25")
        self.assertTrue(valid)
        self.assertEqual(val, 25.0)
        
        valid, _ = schema.validate("-1")
        self.assertFalse(valid)
        
        valid, _ = schema.validate("abc")
        self.assertFalse(valid)

    def test_duration(self):
        schema = InputSchema(InputType.DURATION, "How long?")
        
        # Test Chinese
        valid, val = schema.validate("30分钟")
        self.assertTrue(valid)
        self.assertEqual(val["minutes"], 30)
        
        valid, val = schema.validate("1.5小时")
        self.assertTrue(valid)
        self.assertEqual(val["minutes"], 90)
        
        # Test English
        valid, val = schema.validate("45min")
        self.assertTrue(valid)
        self.assertEqual(val["minutes"], 45)
        
        valid, val = schema.validate("2h")
        self.assertTrue(valid)
        self.assertEqual(val["minutes"], 120)

    def test_date(self):
        schema = InputSchema(InputType.DATE, "When?")
        
        # Test relative
        from datetime import datetime, timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        valid, val = schema.validate("明天")
        self.assertTrue(valid)
        self.assertEqual(val, tomorrow)
        
        # Test ISO
        valid, val = schema.validate("2026-05-20")
        self.assertTrue(valid)
        self.assertEqual(val, "2026-05-20")

if __name__ == "__main__":
    unittest.main()
