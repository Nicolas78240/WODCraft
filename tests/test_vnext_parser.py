#!/usr/bin/env python3
"""
Test suite for WODCraft vNext parser and grammar
"""

import pytest
import json
from wodc_vnext import parse_vnext, ToASTvNext, ModuleRef, InMemoryResolver, FileSystemResolver
from pathlib import Path


class TestVNextParser:
    """Test the vNext parser and grammar"""
    
    def test_parse_simple_module(self):
        """Test parsing a simple module"""
        source = '''
        module warmup.test v1 {
          @tag("test", "simple")
          warmup "Test Warmup" {
            block "Movement" {
              10 Air_Squats
              20s Plank
            }
          }
        }
        '''
        ast = parse_vnext(source)
        
        assert "modules" in ast
        assert len(ast["modules"]) == 1
        
        module = ast["modules"][0]
        assert module["type"] == "MODULE"
        assert module["id"] == "warmup.test"
        assert module["version"] == "v1"
        
    def test_parse_module_with_vars(self):
        """Test parsing module with typed variables"""
        source = '''
        module skill.test v1 {
          vars {
            percent_1rm: Load(%1RM) = 60%1RM
            sets: Int = 5
            tempo: Tempo = "31X1"
          }
          
          skill "Test Skill" {
            work {
              sets sets reps 3 @ percent_1rm
            }
            cues {
              "Keep tight core"
              "Breathe"
            }
          }
        }
        '''
        ast = parse_vnext(source)
        
        assert len(ast["modules"]) == 1
        module = ast["modules"][0]
        
        # Check that vars are captured in the body
        assert len(module["body"]) >= 1
        
    def test_parse_simple_session(self):
        """Test parsing a session"""
        source = '''
        session "Test Session" {
          components {
            warmup import warmup.full_body_10m@v1
            wod import wod.test@v2
          }
          
          scoring {
            warmup none
            wod AMRAP rounds+reps
          }
          
          meta {
            track = "RX"
            level = ["Beginner", "Intermediate"]
          }
          
          exports {
            json
            html
          }
        }
        '''
        ast = parse_vnext(source)
        
        assert "sessions" in ast
        assert len(ast["sessions"]) == 1
        
        session = ast["sessions"][0]
        assert session["type"] == "SESSION"
        assert session["title"] == "Test Session"
        assert session["components"] is not None
        assert session["scoring"] is not None
        assert session["meta"] is not None
        assert session["exports"] is not None
        
    def test_parse_session_with_overrides(self):
        """Test parsing session with parameter overrides"""
        source = '''
        session "Override Test" {
          components {
            skill import skill.snatch@v1 override {
              percent_1rm = 70%1RM
              tempo = "32X1"
              sets = 6
            }
          }
          
          scoring {
            skill LoadKg best_of_sets
          }
        }
        '''
        ast = parse_vnext(source)
        
        assert len(ast["sessions"]) == 1
        session = ast["sessions"][0]
        assert "components" in session
        
    def test_parse_multiple_modules_and_sessions(self):
        """Test parsing file with both modules and sessions"""
        source = '''
        module warmup.multi v1 {
          warmup "Multi Test" {
            block "Test" {
              10 Squats
            }
          }
        }
        
        session "Multi Session" {
          components {
            warmup import warmup.multi@v1
          }
          scoring {
            warmup none
          }
        }
        '''
        ast = parse_vnext(source)
        
        assert len(ast["modules"]) == 1
        assert len(ast["sessions"]) == 1
        
    def test_parse_invalid_syntax_raises_error(self):
        """Test that invalid syntax raises appropriate error"""
        source = '''
        session "Broken" {
          components
            # Missing braces
            warmup import test
        '''
        
        with pytest.raises(ValueError, match="Parse error"):
            parse_vnext(source)
            
    def test_parse_empty_file(self):
        """Test parsing empty file returns empty structure"""
        ast = parse_vnext("")
        assert ast == {"modules": [], "sessions": []}


class TestTransformerMethods:
    """Test specific transformer methods"""
    
    def test_qualified_id_transformation(self):
        """Test qualified ID transformation"""
        transformer = ToASTvNext()
        
        # Mock tokens
        class MockToken:
            def __init__(self, value):
                self.value = value
            def __str__(self):
                return self.value
        
        tokens = [MockToken("warmup"), MockToken("full_body"), MockToken("10m")]
        result = transformer.qualified_id(tokens)
        
        assert result == "warmup.full_body.10m"
        
    def test_version_transformation(self):
        """Test version number transformation"""
        transformer = ToASTvNext()
        
        # Test single version
        result = transformer.version([1])
        assert result == "v1"
        
        # Test major.minor version
        result = transformer.version([2, 1])
        assert result == "v2.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])