import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import test modules
from test_event_sourcing import TestEventSourcing
from test_planner import TestSteward
from test_schema import TestSchema

if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    
    suite.addTests(loader.loadTestsFromTestCase(TestEventSourcing))
    suite.addTests(loader.loadTestsFromTestCase(TestSteward))
    suite.addTests(loader.loadTestsFromTestCase(TestSchema))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    sys.exit(not result.wasSuccessful())
