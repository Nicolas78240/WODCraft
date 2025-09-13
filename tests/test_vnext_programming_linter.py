#!/usr/bin/env python3
import pytest

try:
    from wodc_vnext import ProgrammingLinter, parse_vnext
except Exception as e:  # pragma: no cover
    pytest.skip(f"wodc_vnext unavailable: {e}", allow_module_level=True)


class TestProgrammingLinter:
    def test_linter_flags_missing_heavy_and_ratio(self):
        source = '''
        programming {
          macrocycle: { name: "Test" },
          microcycles: [
            {
              week: 1,
              sessions: [
                { day: 1, focus: "G", design: { workout: "couplet", domain: "short" } },
                { day: 2, focus: "W", design: { workout: "oly_technique", domain: "medium" } },
                { day: 3, focus: "M", design: { workout: "emom_skill", domain: "short" } }
              ]
            }
          ]
        }
        '''
        ast = parse_vnext(source)
        prog = ast.get("programming", [])[0]["data"]
        issues = ProgrammingLinter().lint(prog)
        # Missing heavy day
        assert any(i["code"] == "P101" for i in issues)
        # No long domain
        assert any(i["code"] == "P103" for i in issues)

    def test_linter_pass_with_heavy_and_ratio(self):
        source = '''
        programming {
          macrocycle: { name: "Test2" },
          microcycles: [
            {
              week: 1,
              sessions: [
                { day: 1, focus: "W", design: { workout: "heavy_day" } },
                { day: 2, focus: "M", design: { workout: "couplet", domain: "long" } },
                { day: 3, focus: "G", design: { workout: "triplet", domain: "short" } }
              ]
            }
          ]
        }
        '''
        ast = parse_vnext(source)
        prog = ast.get("programming", [])[0]["data"]
        issues = ProgrammingLinter().lint(prog)
        # heavy day present, ratio >= 0.66, has a long
        assert not any(i["code"] == "P101" for i in issues)
        assert not any(i["code"] == "P102" for i in issues)
        assert not any(i["code"] == "P103" for i in issues)
