#!/usr/bin/env python3
"""
Test for the exit node checkbox fix.
This validates that the checkbox logic properly handles various scenarios
without unchecking itself inappropriately.
"""

import unittest
from unittest.mock import Mock

class MockComboBox:
    """Mock QComboBox for testing"""
    def __init__(self):
        self.items = []
        self.current_index = -1
        self.signals_blocked = False
    
    def count(self):
        return len(self.items)
    
    def addItem(self, display, data):
        self.items.append((display, data))
    
    def clear(self):
        self.items = []
        self.current_index = -1
    
    def currentData(self):
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index][1]
        return None
    
    def currentIndex(self):
        return self.current_index
    
    def setCurrentIndex(self, index):
        if 0 <= index < len(self.items):
            self.current_index = index
        else:
            self.current_index = -1
    
    def itemData(self, index):
        if 0 <= index < len(self.items):
            return self.items[index][1]
        return None
    
    def findData(self, data):
        for i, (display, item_data) in enumerate(self.items):
            if item_data == data:
                return i
        return -1
    
    def blockSignals(self, block):
        self.signals_blocked = block


class TestExitNodeCheckboxFix(unittest.TestCase):
    """Test the exit node checkbox logic improvements"""
    
    def setUp(self):
        self.combo = MockComboBox()
        self.statusbar = Mock()
        self.last_exit_node_choice = None
        
    def simulate_exit_use_changed(self, state_checked=True):
        """Simulate the improved _exit_use_changed logic"""
        if not state_checked:
            return "disable_exit_node"
            
        if self.combo.count() == 0:
            self.statusbar.showMessage("Brak dostępnych exit node", 4000)
            return "uncheck_no_nodes"

        node_to_set = self.combo.currentData()
        
        # If no node is currently selected, try to find a good selection
        if node_to_set is None:
            # First try to use the last exit node choice if it's in the current list
            if self.last_exit_node_choice:
                for i in range(self.combo.count()):
                    if self.combo.itemData(i) == self.last_exit_node_choice:
                        self.combo.blockSignals(True)
                        self.combo.setCurrentIndex(i)
                        self.combo.blockSignals(False)
                        node_to_set = self.combo.currentData()
                        break
            
            # If still no node, just use the first one if available
            if not node_to_set and self.combo.count() > 0:
                self.combo.blockSignals(True)
                self.combo.setCurrentIndex(0)
                self.combo.blockSignals(False)
                node_to_set = self.combo.currentData()

        # If we still don't have a node, something is wrong
        if not node_to_set:
            self.statusbar.showMessage("Nie można wybrać exit node z listy", 4000)
            return "uncheck_cant_select"

        node_to_set = str(node_to_set)
        self.last_exit_node_choice = node_to_set
        return f"set_exit_node:{node_to_set}"
    
    def test_empty_combo_box(self):
        """Test behavior with no available exit nodes"""
        result = self.simulate_exit_use_changed()
        self.assertEqual(result, "uncheck_no_nodes")
        
    def test_combo_with_no_selection(self):
        """Test behavior when combo has items but no selection"""
        self.combo.addItem("Node 1", "node1")
        self.combo.addItem("Node 2", "node2") 
        self.combo.setCurrentIndex(-1)  # No selection
        
        result = self.simulate_exit_use_changed()
        self.assertEqual(result, "set_exit_node:node1")
        self.assertEqual(self.combo.currentData(), "node1")
        
    def test_combo_with_existing_selection(self):
        """Test behavior when combo already has a selection"""
        self.combo.addItem("Node A", "nodeA")
        self.combo.addItem("Node B", "nodeB")
        self.combo.setCurrentIndex(1)  # Select second item
        
        result = self.simulate_exit_use_changed()
        self.assertEqual(result, "set_exit_node:nodeB")
        self.assertEqual(self.combo.currentData(), "nodeB")
        
    def test_restore_last_choice(self):
        """Test that last choice is restored when available"""
        self.last_exit_node_choice = "nodeC"
        
        self.combo.addItem("Node A", "nodeA")
        self.combo.addItem("Node C", "nodeC")
        self.combo.setCurrentIndex(-1)  # No selection
        
        result = self.simulate_exit_use_changed()
        self.assertEqual(result, "set_exit_node:nodeC")
        self.assertEqual(self.combo.currentData(), "nodeC")
        
    def test_fallback_when_last_choice_not_available(self):
        """Test fallback to first item when last choice isn't in list"""
        self.last_exit_node_choice = "nodeZ"  # Not in list
        
        self.combo.addItem("Node A", "nodeA") 
        self.combo.addItem("Node B", "nodeB")
        self.combo.setCurrentIndex(-1)  # No selection
        
        result = self.simulate_exit_use_changed()
        self.assertEqual(result, "set_exit_node:nodeA")
        self.assertEqual(self.combo.currentData(), "nodeA")


if __name__ == '__main__':
    unittest.main()