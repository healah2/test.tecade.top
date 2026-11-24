from django.test import TestCase
from .views import parse_expectations, _group_expectations_by_parent


class LearningExpectationsParsingTests(TestCase):
    def test_nested_numbered_hierarchy_bolds_parents_keeps_all(self):
        """Test that parent items are bolded and all items including parents are kept."""
        raw = """1.1 Ergonomics risk factors
1.2 Creation of computerized word document
1.2.1 Introduction to word document
1.2.2 Types of word processors
1.2.3 Creating word document
1.2.4 Editing and formatting word document
1.2.5 Word document editing features
1.2.5.1 Text editing
1.2.5.2 Paragraph editing
1.2.5.3 Document editing
1.2.6 Word document formatting features
1.2.6.1 Text formatting
1.2.6.2 Paragraph formatting
1.2.6.3 Document formatting
1.2.7 Enhancing productivity
1.2.7.1 Set basic options/ preferences
1.2.7.2 Help resources
1.2.7.3 Use magnification/zoom tools
1.2.7.4 Display, hide built-in tool bar
1.3 Creation and manipulation of tables
1.3.1 Inserting tables
1.3.2 Working with tables
1.4 Mail merge
1.5 Inserting word processing objects
1.5.1 Picture
1.5.2 Shapes
1.5.3 Table
1.5.4 Charts
1.6 Generating list of figures and table of content
1.6.1 List of figures
1.6.2 Table of content
1.7 Printing of computerized word document
1.7.1 Print setup
1.7.2 Printing"""
        
        result = parse_expectations(raw)
        
        # 1.1 is a leaf (no 1.1.x), so it's unbolded
        self.assertIn("1.1 Ergonomics risk factors", result)
        self.assertNotIn("<strong>1.1 Ergonomics risk factors</strong>", result)
        
        # 1.2 has children (1.2.1, etc), so it's bolded but still included
        self.assertIn("<strong>1.2 Creation of computerized word document</strong>", result)
        
        # 1.2.1 has no children, so it's unbolded
        self.assertIn("1.2.1 Introduction to word document", result)
        self.assertNotIn("<strong>1.2.1 Introduction to word document</strong>", result)
        
        # 1.2.5 has children (1.2.5.1, etc), so it's bolded
        self.assertIn("<strong>1.2.5 Word document editing features</strong>", result)
        
        # 1.2.5.1 has no children, so it's unbolded
        self.assertIn("1.2.5.1 Text editing", result)
        self.assertNotIn("<strong>1.2.5.1 Text editing</strong>", result)
        
        # 1.4 has no children, so it's unbolded
        self.assertIn("1.4 Mail merge", result)
        self.assertNotIn("<strong>1.4 Mail merge</strong>", result)
        
        # 1.5 has children (1.5.1, etc), so it's bolded
        self.assertIn("<strong>1.5 Inserting word processing objects</strong>", result)

    def test_parent_sentence_continuation_is_fully_bolded(self):
        """Test that parent items with continued lines are fully bolded."""
        raw = """2.1.2 Elements of
spreadsheet window
2.1.2.1 Worksheet"""
        result = parse_expectations(raw)
        self.assertIn("<strong>2.1.2 Elements of spreadsheet window</strong>", result)
        self.assertIn("2.1.2.1 Worksheet", result)

    def test_single_numbered_item_is_unbolded(self):
        """Test that a numbered item without children is unbolded."""
        raw = "1.1 Ergonomics risk factors"
        result = parse_expectations(raw)
        self.assertEqual(result, ["1.1 Ergonomics risk factors"])
        self.assertNotIn("<strong>1.1 Ergonomics risk factors</strong>", result)

    def test_parent_heading_starts_new_group(self):
        """Parent headings should start a new grouped session boundary."""
        flat_expectations = [
            {"title": "Outcome 1", "expectation": "1.1 First leaf"},
            {"title": "Outcome 1", "expectation": "<strong>1.2 Parent heading</strong>"},
            {"title": "Outcome 1", "expectation": "1.2.1 Child one"},
            {"title": "Outcome 1", "expectation": "1.2.2 Child two"},
            {"title": "Outcome 1", "expectation": "<strong>1.3 Next parent</strong>"},
            {"title": "Outcome 1", "expectation": "1.3.1 Child three"},
        ]
        groups = _group_expectations_by_parent(flat_expectations)

        self.assertEqual(len(groups), 3)
        self.assertEqual([item["expectation"] for item in groups[0]], ["1.1 First leaf"])
        self.assertEqual([item["expectation"] for item in groups[1]], [
            "<strong>1.2 Parent heading</strong>",
            "1.2.1 Child one",
            "1.2.2 Child two",
        ])
        self.assertEqual([item["expectation"] for item in groups[2]], [
            "<strong>1.3 Next parent</strong>",
            "1.3.1 Child three",
        ])
