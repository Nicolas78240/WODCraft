#!/usr/bin/env python3
import pytest

try:
    from wodc_vnext import TeamRealizedAggregator, parse_vnext, SessionCompiler, InMemoryResolver
except Exception as e:  # pragma: no cover
    pytest.skip(f"wodc_vnext unavailable: {e}", allow_module_level=True)


class TestTeamRealizedAggregator:
    def _compile_min(self, session_source: str):
        ast = parse_vnext(session_source)
        sess = ast["sessions"][0]
        comp = SessionCompiler(InMemoryResolver()).compile_session(sess)
        return sess, comp

    def test_amrap_sum(self):
        src = '''
        session "S" {
          components {}
          scoring {}
          realized {
            scoring: "amrap_reps",
            events: [
              { at: "00:10", athlete: "a1", movement: "row_cal", value: 12 },
              { at: "00:20", athlete: "a2", movement: "row_cal", value: 10 }
            ]
          }
        }
        '''
        s, compiled = self._compile_min(src)
        agg = TeamRealizedAggregator().aggregate(s, compiled["session"])
        assert agg["score"]["type"] == "AMRAP"
        assert agg["score"]["reps"] == 22

    def test_for_time(self):
        src = '''
        session "S" {
          components {}
          scoring {}
          realized {
            scoring: "for_time",
            events: [
              { at: "00:30", athlete: "a1", movement: "w1", value: 1 },
              { at: "01:05", athlete: "a1", movement: "w1", value: 1 }
            ]
          }
        }
        '''
        s, compiled = self._compile_min(src)
        agg = TeamRealizedAggregator().aggregate(s, compiled["session"])
        assert agg["score"]["type"] == "FOR_TIME"
        assert agg["score"]["time_s"] == 65

    def test_max_load(self):
        src = '''
        session "S" {
          components {}
          scoring {}
          realized {
            scoring: "max_load",
            events: [
              { at: "00:30", athlete: "a1", movement: "snatch", load: 60 },
              { at: "01:05", athlete: "a1", movement: "snatch", load: 70 }
            ]
          }
        }
        '''
        s, compiled = self._compile_min(src)
        agg = TeamRealizedAggregator().aggregate(s, compiled["session"])
        assert agg["score"]["type"] == "MAX_LOAD"
        assert agg["score"]["value"] == 70

    def test_relay_policy(self):
        src = '''
        session "S" {
          components {}
          scoring {}
          team {
            policy: { partition: "relay", relay_order: ["a1","a2"] }
          }
          realized {
            scoring: "amrap_reps",
            events: [
              { at: "00:10", athlete: "a1", movement: "m", value: 5 },
              { at: "00:20", athlete: "a2", movement: "m", value: 5 },
              { at: "00:30", athlete: "a2", movement: "m", value: 5 }  // out of turn -> ignored
            ]
          }
        }
        '''
        s, compiled = self._compile_min(src)
        agg = TeamRealizedAggregator().aggregate(s, compiled["session"])
        assert agg["score"]["reps"] == 10
