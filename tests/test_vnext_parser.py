#!/usr/bin/env python3
"""
Test suite for WODCraft vNext parser and grammar
"""

import pytest
import json
from src.wodcraft.core import parse_vnext, ToASTvNext, ModuleRef, InMemoryResolver, FileSystemResolver, WODCraftError
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
        
        with pytest.raises(WODCraftError, match="Syntax error"):
            parse_vnext(source)
            
    def test_parse_empty_file(self):
        """Test parsing empty file returns empty structure"""
        ast = parse_vnext("")
        assert ast == {"modules": [], "sessions": []}

    def test_parse_dual_load(self):
        source = '''
        module wod.dual_load v1 {
          wod AMRAP 10:00 {
            10 Thrusters @95lb/65lb
          }
        }
        '''
        ast = parse_vnext(source)
        module = ast["modules"][0]
        wod = module["body"]["children"][0]["children"][0]
        movement = wod["movements"][0]
        load = movement.get("load")
        assert load["type"] == "LOAD_DUAL"
        assert load["per_gender"]["male"]["raw"] == "95lb"
        assert load["per_gender"]["female"]["raw"] == "65lb"

    def test_parse_dual_calories(self):
        source = '''
        module wod.dual_cal v1 {
          wod AMRAP 5:00 {
            20/16 cal Row
          }
        }
        '''
        ast = parse_vnext(source)
        movement = ast["modules"][0]["body"]["children"][0]["children"][0]["movements"][0]
        quantity = movement.get("quantity")
        assert quantity["kind"] == "calories"
        assert quantity["per_gender"]["male"]["value"] == 20.0
        assert quantity["per_gender"]["female"]["value"] == 16.0

    def test_parse_notes_scopes(self):
        source = '''
        module wod.with.notes v1 {
          notes: {
            stimulus: "Anaerobic sprint",
            coaching: ["Stay long", "Relax grip"]
          }

          wod AMRAP 12:00 {
            notes: ["Stimulus: grip", "Pace breathing"]
            15/12 cal Bike_Erg
            50m Farmer_Carry PROGRESS("+10m/round") @24kg/16kg
            notes: "Coaching: break carries before grip fails"
          }
        }
        '''
        ast = parse_vnext(source)
        module = ast["modules"][0]
        body_children = module["body"].get("children", [])

        module_notes = []
        for body in body_children:
            if not isinstance(body, dict):
                continue
            for child in body.get("children", []):
                if isinstance(child, dict) and child.get("type") == "NOTES":
                    module_notes.append(child)
        assert module_notes, "Module-level notes not captured"
        notes_value = module_notes[0]["value"]
        assert isinstance(notes_value, dict)
        assert notes_value["stimulus"] == "Anaerobic sprint"
        assert notes_value["coaching"][0] == "Stay long"

        wod_node = None
        for body in body_children:
            for child in body.get("children", []):
                if isinstance(child, dict) and child.get("type") == "WOD":
                    wod_node = child
                    break
            if wod_node:
                break
        assert wod_node is not None
        wod_notes = wod_node.get("notes")
        assert isinstance(wod_notes, list)
        assert wod_notes[0] == "Stimulus: grip"
        assert "Coaching: break carries" in wod_notes[-1]

    def test_parse_wod_rest(self):
        source = '''
        module wod.rest.sample v1 {
          wod AMRAP 10:00 {
            10 Burpee
            REST 2:00
            200m Run
          }
        }
        '''
        ast = parse_vnext(source)
        wod = ast["modules"][0]["body"]["children"][0]["children"][0]
        moves = wod["movements"]
        assert len(moves) == 3
        rest = moves[1]
        assert rest["type"] == "REST"
        duration = rest.get("duration", {})
        assert duration.get("kind") == "duration"
        assert duration.get("seconds") == 120
        assert rest.get("raw") in {"2:00", "02:00", "2m"}

    def test_parse_progress_clause(self):
        source = '''
        module wod.progress v1 {
          wod AMRAP 12:00 {
            15m Farmer_Carry PROGRESS("+15m/round")
          }
        }
        '''
        ast = parse_vnext(source)
        movement = ast["modules"][0]["body"]["children"][0]["children"][0]["movements"][0]
        progression = movement.get("progression")
        assert progression["increment"]["value"] == 15.0
        assert progression["increment"]["unit"] == "m"
        assert progression["cadence"] == "round"


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
        assert result == {"version": "v1"}

        # Test major.minor version
        result = transformer.version([2, 1])
        assert result == {"version": "v2.1"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
